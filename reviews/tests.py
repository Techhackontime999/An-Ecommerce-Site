from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from shop.models import Category, Product

from .models import ProductReview, ReviewReport, SellerReview


class ReviewBaseTestCase(TestCase):
    def setUp(self):
        # Throttle counters live in the Django cache, which is NOT cleared
        # between tests; reset it so a POST in one test can never 429 another.
        cache.clear()
        self.buyer = User.objects.create_user(username='buyer1', password='pass1234')
        self.other = User.objects.create_user(username='other1', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category,
            name='Nimbus Headphones',
            slug='nimbus-headphones',
            description='<p>Great sound.</p>',
            price=Decimal('49.99'),
        )

    def _make_review(self, user=None, status=ProductReview.Status.APPROVED, **kwargs):
        defaults = {
            'overall_rating': 4,
            'performance': 4,
            'value': 3,
            'quality': 5,
            'recommendation_rating': 80,
            'review_text': 'Solid pair of headphones.',
            'status': status,
        }
        defaults.update(kwargs)
        return ProductReview.objects.create(
            product=self.product,
            reviewer=user or self.buyer,
            **defaults,
        )

    def _make_paid_purchase(self, user=None):
        buyer = user or self.buyer
        order = buyer.orders.create(
            first_name='Mira', last_name='Sharma', email='m@example.com',
            address='1 Test St', postal_code='10001', city='NYC', paid=True,
        )
        order.items.create(product=self.product, price=self.product.price)
        return order


class ProductReviewModelTests(ReviewBaseTestCase):
    def test_subscores_default_to_overall(self):
        review = ProductReview.objects.create(
            product=self.product,
            reviewer=self.buyer,
            overall_rating=3,
        )
        self.assertEqual(review.performance, 3)
        self.assertEqual(review.value, 3)
        self.assertEqual(review.quality, 3)

    def test_verified_purchase_auto_detected(self):
        self._make_paid_purchase()
        review = self._make_review()
        self.assertTrue(review.verified_purchase)

    def test_not_verified_purchase_without_paid_order(self):
        review = self._make_review()
        self.assertFalse(review.verified_purchase)

    def test_unique_reviewer_per_product(self):
        self._make_review()
        with self.assertRaises(Exception):
            self._make_review()


class ProductReviewViewTests(ReviewBaseTestCase):
    def test_list_shows_only_approved(self):
        approved = self._make_review()
        self._make_review(user=self.other, status=ProductReview.Status.PENDING)
        url = reverse('reviews:product_review_list', args=[self.product.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, approved.review_text)
        self.assertEqual(len(response.context['reviews']), 1)

    def test_create_requires_login(self):
        url = reverse('reviews:create_product_review', args=[self.product.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_create_review_as_authenticated(self):
        self._make_paid_purchase()
        self.client.login(username='buyer1', password='pass1234')
        url = reverse('reviews:create_product_review', args=[self.product.pk])
        response = self.client.post(url, {
            'overall_rating': 4,
            'recommendation_rating': 70,
            'pros': 'Bass',
            'cons': 'Weight',
            'review_text': 'Great sound, a bit heavy.',
        })
        review = ProductReview.objects.get(product=self.product, reviewer=self.buyer)
        self.assertTrue(review.verified_purchase)
        self.assertRedirects(response, reverse('reviews:product_review_detail', args=[review.pk]))

    def test_create_review_existing_redirects_to_own(self):
        self._make_paid_purchase()
        review = self._make_review()
        self.client.login(username='buyer1', password='pass1234')
        url = reverse('reviews:create_product_review', args=[self.product.pk])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('reviews:product_review_detail', args=[review.pk]))

    def test_detail_renders(self):
        review = self._make_review()
        url = reverse('reviews:product_review_detail', args=[review.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Solid pair of headphones.')

    def test_helpful_toggle(self):
        review = self._make_review()
        self.client.login(username='other1', password='pass1234')
        url = reverse('reviews:toggle_review_helpful', args=[review.pk])
        self.client.post(url)
        self.assertEqual(review.helpful_votes.count(), 1)
        self.client.post(url)
        self.assertEqual(review.helpful_votes.count(), 0)

    def test_report_review(self):
        review = self._make_review()
        self.client.login(username='other1', password='pass1234')
        url = reverse('reviews:report_review', args=[review.pk])
        response = self.client.post(url, {'reason': 'fake', 'details': 'Seems paid.'})
        self.assertRedirects(response, reverse('reviews:product_review_detail', args=[review.pk]))
        report = ReviewReport.objects.get(review=review)
        self.assertEqual(report.reason, 'fake')
        self.assertEqual(report.reporter, self.other)


class SellerRatingSyncTests(ReviewBaseTestCase):
    def setUp(self):
        super().setUp()
        self.seller_user = User.objects.create_user(username='seller', password='pass1234')
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Acme Audio',
            bank_account='1234567890',
            phone='9876543210',
            address='1 Shop St',
        )
        self.seller_product = Product.objects.create(
            category=self.product.category,
            name='Seller Headphones',
            slug='seller-headphones',
            price=Decimal('99.99'),
            seller=self.seller,
        )
        CustomerProfile.objects.create(
            user=self.buyer, phone='9999999999', address='5 Test St',
        )

    def test_product_review_updates_seller_rating(self):
        ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=3, recommendation_rating=50,
            status=ProductReview.Status.APPROVED,
        )
        sr = SellerReview.objects.get(seller_profile=self.seller, customer__user=self.buyer)
        self.assertEqual(sr.rating, 3)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 3.0)

    def test_editing_product_review_updates_seller_rating(self):
        review = ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=2, recommendation_rating=40,
            status=ProductReview.Status.APPROVED,
        )
        review.overall_rating = 5
        review.save()
        sr = SellerReview.objects.get(seller_profile=self.seller, customer__user=self.buyer)
        self.assertEqual(sr.rating, 5)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 5.0)

    def test_two_customers_average_the_seller_rating(self):
        other_buyer = User.objects.create_user(username='buyer2', password='pass1234')
        CustomerProfile.objects.create(
            user=other_buyer, phone='8888888888', address='6 Test St',
        )
        ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=80,
            status=ProductReview.Status.APPROVED,
        )
        ProductReview.objects.create(
            product=self.seller_product, reviewer=other_buyer,
            overall_rating=2, recommendation_rating=30,
            status=ProductReview.Status.APPROVED,
        )
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 3.0)
        self.assertEqual(self.seller.reviews_count(), 2)

    def test_product_review_on_sellerless_product_does_not_crash(self):
        ProductReview.objects.create(
            product=self.product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=80,
            status=ProductReview.Status.APPROVED,
        )
        self.assertEqual(SellerReview.objects.count(), 0)

    def test_product_review_without_customer_profile_does_not_crash(self):
        CustomerProfile.objects.filter(user=self.buyer).delete()
        ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=80,
            status=ProductReview.Status.APPROVED,
        )
        self.assertEqual(SellerReview.objects.count(), 0)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 0.0)

    def test_product_review_updates_seller_rating(self):
        ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=5, recommendation_rating=90,
            status=ProductReview.Status.APPROVED,
        )
        sr = SellerReview.objects.get(seller_profile=self.seller, customer__user=self.buyer)
        self.assertEqual(sr.rating, 5)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 5.0)

    def test_product_review_on_sellerless_product_does_not_crash(self):
        ProductReview.objects.create(
            product=self.product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=70,
            status=ProductReview.Status.APPROVED,
        )
        self.assertEqual(SellerReview.objects.count(), 0)


class ProductReviewModerationTests(ReviewBaseTestCase):
    """Compliance: new reviews start PENDING and only approved reviews are public."""

    def setUp(self):
        super().setUp()
        self.seller_user = User.objects.create_user(username='seller2', password='pass1234')
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Acme Moderation',
            bank_account='1234567890',
            phone='9876543210',
            address='1 Shop St',
        )
        self.seller_product = Product.objects.create(
            category=self.product.category,
            name='Moderated Headphones',
            slug='moderated-headphones',
            price=Decimal('99.99'),
            seller=self.seller,
        )
        CustomerProfile.objects.create(
            user=self.buyer, phone='9999999999', address='5 Test St',
        )

    def test_new_reviews_default_to_pending(self):
        review = ProductReview.objects.create(
            product=self.product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=70,
        )
        self.assertEqual(review.status, ProductReview.Status.PENDING)
        self.assertFalse(review.is_approved)

    def test_pending_review_does_not_update_seller_rating(self):
        ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=1, recommendation_rating=10,
        )
        self.assertEqual(SellerReview.objects.count(), 0)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 0.0)

    def test_pending_review_hidden_from_public_list(self):
        review = ProductReview.objects.create(
            product=self.product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=70,
            review_text='Pending review should stay hidden.',
        )
        self.assertFalse(review.is_approved)
        url = reverse('reviews:product_review_list', args=[self.product.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'Pending review should stay hidden.')

    def test_rejecting_approved_review_removes_seller_rating(self):
        review = ProductReview.objects.create(
            product=self.seller_product, reviewer=self.buyer,
            overall_rating=4, recommendation_rating=70,
            status=ProductReview.Status.APPROVED,
        )
        self.assertEqual(SellerReview.objects.count(), 1)
        review.status = ProductReview.Status.REJECTED
        review.save()
        self.assertEqual(SellerReview.objects.count(), 0)
        self.seller.refresh_from_db()
        self.assertEqual(float(self.seller.rating), 0.0)

    def test_create_review_is_throttled(self):
        from django.core.cache import cache
        cache.clear()
        self._make_paid_purchase()
        self.client.login(username='buyer1', password='pass1234')
        url = reverse('reviews:create_product_review', args=[self.product.pk])
        payload = {
            'overall_rating': 4,
            'recommendation_rating': 70,
            'review_text': 'Throttle test.',
        }
        for _ in range(5):
            response = self.client.post(url, payload)
            self.assertNotEqual(response.status_code, 429)
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 429)


class ProductRatingPropertyTests(ReviewBaseTestCase):
    def test_average_rating_counts_only_approved_reviews(self):
        self._make_review(overall_rating=5)
        self._make_review(user=self.other, overall_rating=1, status=ProductReview.Status.PENDING)
        self.assertEqual(self.product.average_rating, 5.0)
        self.assertEqual(self.product.rating_count, 1)

    def test_no_reviews_means_zero(self):
        self.assertEqual(self.product.average_rating, 0)
        self.assertEqual(self.product.rating_count, 0)

    def test_rejected_reviews_excluded(self):
        self._make_review(overall_rating=5)
        self._make_review(user=self.other, overall_rating=2, status=ProductReview.Status.REJECTED)
        self.assertEqual(self.product.average_rating, 5.0)
        self.assertEqual(self.product.rating_count, 1)

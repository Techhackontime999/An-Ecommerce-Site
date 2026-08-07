from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from shop.models import Category, Product

from .models import ProductReview, ReviewReport


class ReviewBaseTestCase(TestCase):
    def setUp(self):
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

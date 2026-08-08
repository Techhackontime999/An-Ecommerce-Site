from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from shop.models import Category, Product

class CategoryTest(TestCase):

    def create_category(self, name="test"):
        return Category.objects.create(name=name)

    def test_category_creation(self):
        c = self.create_category()
        self.assertTrue(isinstance(c, Category))
        self.assertEqual(c.__str__(), c.name)

class ProductTest(TestCase):
    
    def setUp(self):
        self.category = Category.objects.create(name='fastfood', slug='fastfood',)
    
    def create_product(self, name="product", price=20):
        return Product.objects.create(category=self.category, name=name, price=price, created=timezone.now(), updated=timezone.now())

    def test_product_creation(self):
        p = self.create_product()
        self.assertTrue(isinstance(p, Product))
        self.assertEqual(p.__str__(), p.name)


class ProductQuerySetHelpersTest(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from reviews.models import ProductReview

        self.category = Category.objects.create(name='gadgets', slug='gadgets')
        self.product = Product.objects.create(
            category=self.category, name='Widget', slug='widget', price=10,
        )
        self.reviewer = User.objects.create_user(username='rev', password='x1234567')
        ProductReview.objects.create(
            reviewer=self.reviewer,
            product=self.product,
            overall_rating=4,
            status=ProductReview.Status.APPROVED,
        )
        ProductReview.objects.create(
            reviewer=User.objects.create_user(username='rev2', password='x1234567'),
            product=self.product,
            overall_rating=5,
            status=ProductReview.Status.APPROVED,
        )
        ProductReview.objects.create(
            reviewer=User.objects.create_user(username='rev3', password='x1234567'),
            product=self.product,
            overall_rating=1,
            status=ProductReview.Status.REJECTED,
        )

    def test_with_rating_annotates_average_and_count(self):
        p = Product.objects.with_rating().get(pk=self.product.pk)
        self.assertEqual(p.average_rating, 4.5)
        self.assertEqual(p.rating_count, 2)

    def test_with_rating_product_without_reviews_is_zero(self):
        empty = Product.objects.create(category=self.category, name='Empty', slug='empty', price=5)
        p = Product.objects.with_rating().get(pk=empty.pk)
        self.assertEqual(p.average_rating, 0)
        self.assertEqual(p.rating_count, 0)

    def test_with_deal_price_prefetches_active_deal(self):
        from deals.models import Deal

        now = timezone.now()
        Deal.objects.create(
            product=self.product, deal_price=7,
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )
        p = Product.objects.with_deal_price().get(pk=self.product.pk)
        self.assertEqual(p.current_price, 7)

    def test_with_deal_price_no_deal_falls_back_to_price(self):
        p = Product.objects.with_deal_price().get(pk=self.product.pk)
        self.assertEqual(p.current_price, 10)

    def test_properties_fallback_when_helpers_not_used(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as ctx:
            p = Product.objects.get(pk=self.product.pk)
            self.assertEqual(p.average_rating, 4.5)
            self.assertEqual(p.rating_count, 2)
            self.assertEqual(p.current_price, 10)
        # Plain access still works (property fallback path).
        self.assertGreater(len(ctx.captured_queries), 0)
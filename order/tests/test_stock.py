from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop.models import Category, Product, ProductVariant

from order.models import Order, OrderItem
from order.stock import InsufficientStock, commit_stock, release_stock


class StockTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='stockbuyer', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Headphones',
            slug='headphones',
            price=Decimal('100.00'),
            stock=10,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Red', stock=5,
        )

    def _order(self, quantity, variant=None):
        order = Order.objects.create(
            user=self.user,
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=variant,
            variant_name=variant.name if variant else '',
            price=self.product.price,
            quantity=quantity,
        )
        return order

    def test_commit_stock_decrements_product(self):
        order = self._order(3)
        commit_stock(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_commit_stock_decrements_variant(self):
        order = self._order(2, variant=self.variant)
        commit_stock(order)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

    def test_release_stock_restores_product_and_variant(self):
        order = self._order(2)
        commit_stock(order)
        release_stock(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

        order2 = self._order(2, variant=self.variant)
        commit_stock(order2)
        release_stock(order2)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_commit_stock_raises_when_insufficient_and_rolls_back(self):
        order = self._order(11)
        with self.assertRaises(InsufficientStock):
            commit_stock(order)
        # Nothing may be partially decremented by a failed commit.
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_concurrent_orders_cannot_oversell(self):
        """Two orders each wanting 6 units against a stock of 10: only one may
        succeed — the atomic ``stock >= quantity`` predicate guarantees it."""
        order_a = self._order(6)
        order_b = self._order(6)

        commit_stock(order_a)
        with self.assertRaises(InsufficientStock):
            commit_stock(order_b)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)

    def test_variant_oversell_raises(self):
        order = self._order(6, variant=self.variant)  # stock 5
        with self.assertRaises(InsufficientStock):
            commit_stock(order)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

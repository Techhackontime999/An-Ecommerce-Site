from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from shop.models import Category, Product
from order.models import Order, OrderItem


class OrderItemStrTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category, name='Wireless Mouse', slug='wireless-mouse',
            price=Decimal('499.00'), stock=50,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Jane', last_name='Doe',
            email='jane@example.com', address='123 Main St',
            postal_code='560001', city='Bangalore',
        )

    def test_str_shows_product_name_and_quantity(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('499.00'), quantity=3,
        )
        self.assertEqual(str(item), 'Wireless Mouse x3')

    def test_str_quantity_one(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('499.00'), quantity=1,
        )
        self.assertEqual(str(item), 'Wireless Mouse x1')

    def test_str_large_quantity(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('499.00'), quantity=999,
        )
        self.assertEqual(str(item), 'Wireless Mouse x999')


class OrderItemGetCostTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Electronics', slug='electronics')
        self.product = Product.objects.create(
            category=self.category, name='USB Cable', slug='usb-cable',
            price=Decimal('149.00'), stock=100,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Jane', last_name='Doe',
            email='jane@example.com', address='123 Main St',
            postal_code='560001', city='Bangalore',
        )

    def test_get_cost_single_item(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('149.00'), quantity=1,
        )
        self.assertEqual(item.get_cost(), Decimal('149.00'))

    def test_get_cost_multiple_items(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('149.00'), quantity=5,
        )
        self.assertEqual(item.get_cost(), Decimal('745.00'))

    def test_get_cost_zero_quantity_edge(self):
        item = OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('149.00'), quantity=0,
        )
        self.assertEqual(item.get_cost(), Decimal('0'))

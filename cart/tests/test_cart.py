from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from coupons.models import Coupon
from shop.models import Category, Product, ProductVariant

from cart.cart import Cart
from cart.models import CartItem


class CartTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='shopper', password='test12345', email='shopper@example.com'
        )
        self.category = Category.objects.create(name='Gadgets', slug='gadgets')
        self.product = Product.objects.create(
            category=self.category,
            name='Widget',
            slug='widget',
            price=Decimal('99.00'),
            stock=10,
        )

    def _request(self, user=None):
        request = self.factory.get('/cart/')
        request.session = SessionStore()
        request.session.create()
        request.user = user if user is not None else self.user
        return request

    def _make_cart(self, user=None):
        request = self._request(user)
        cart = Cart(request)
        cart.add(product=self.product, quantity=2)
        return cart

    def test_add_persists_to_database_for_signed_in_user(self):
        cart = self._make_cart(self.user)
        self.assertEqual(len(cart), 2)
        self.assertTrue(CartItem.objects.filter(user=self.user, product=self.product).exists())
        db_item = CartItem.objects.get(user=self.user, product=self.product)
        self.assertEqual(db_item.quantity, 2)

    def test_clear_removes_session_and_database_entries(self):
        cart = self._make_cart(self.user)
        cart.clear()
        self.assertEqual(len(cart), 0)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())
        self.assertEqual(cart.session.get(settings.CART_SESSION_ID), {})
        self.assertEqual(cart.session.get('coupon_id'), None)

    def test_clear_prevents_purchased_products_reappearing(self):
        """The core regression: after checkout the cart must stay empty on the
        next request — the DB rows must not be resurrected."""
        cart = self._make_cart(self.user)
        cart.clear()

        # A brand new request/session backed by the same DB must see an empty cart.
        cart2 = Cart(self._request(self.user))
        self.assertEqual(len(cart2), 0)
        self.assertEqual(list(cart2), [])
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_hydrate_from_db_after_new_request(self):
        cart = self._make_cart(self.user)
        cart2 = Cart(self._request(self.user))
        self.assertEqual(len(cart2), 2)
        self.assertEqual(cart2.cart[str(self.product.id)]['quantity'], 2)

    def test_remove_updates_database(self):
        cart = self._make_cart(self.user)
        cart.remove(self.product)
        self.assertEqual(len(cart), 0)
        self.assertFalse(CartItem.objects.filter(user=self.user, product=self.product).exists())

    def test_coupon_property_returns_none_for_invalid_coupon(self):
        expired = Coupon.objects.create(
            code='EXPIRED',
            discount=10,
            valid_from=timezone.now() - timezone.timedelta(days=10),
            valid_to=timezone.now() - timezone.timedelta(days=5),
            active=True,
        )
        cart = self._make_cart(self.user)
        cart.coupon_id = expired.id
        self.assertIsNone(cart.coupon)

    def test_coupon_property_returns_valid_coupon(self):
        valid = Coupon.objects.create(
            code='SAVE10',
            discount=10,
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_to=timezone.now() + timezone.timedelta(days=1),
            active=True,
        )
        cart = self._make_cart(self.user)
        cart.coupon_id = valid.id
        self.assertEqual(cart.coupon, valid)

    def test_variant_add_and_remove(self):
        variant = ProductVariant.objects.create(
            product=self.product, name='Red', price=Decimal('109.00'), stock=5,
        )
        request = self._request(self.user)
        cart = Cart(request)
        cart.add(product=self.product, quantity=1, variant_id=variant.id, price=variant.effective_price)
        self.assertEqual(len(cart), 1)
        cart.remove(self.product, variant_id=variant.id)
        self.assertEqual(len(cart), 0)
        self.assertFalse(CartItem.objects.filter(user=self.user, key=f'{self.product.id}:{variant.id}').exists())


class CartTemplateI18nTests(TestCase):
    def setUp(self):
        self.client = Client(SERVER_NAME='localhost')
        self.category = Category.objects.create(name='Gadgets', slug='gadgets')
        self.product = Product.objects.create(
            category=self.category,
            name='Widget',
            slug='widget',
            price=Decimal('99.00'),
            stock=10,
        )

    def test_cart_detail_renders_translated_strings_empty(self):
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your cart is empty')
        self.assertContains(response, 'Browse products')

    def test_cart_detail_renders_translated_strings_with_items(self):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        response = self.client.get('/cart/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Items in your cart')
        self.assertContains(response, 'Order summary')
        self.assertContains(response, 'Proceed to checkout')

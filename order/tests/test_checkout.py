from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cart.models import CartItem
from coupons.models import Coupon
from shop.models import Category, Product

from order.models import Order


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='checkoutuser', password='pass1234', email='buyer@example.com'
        )
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Earbuds',
            slug='earbuds',
            price=Decimal('100.00'),
            stock=10,
        )
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)

    def _seed_cart(self, quantity=2, coupon_id=None):
        CartItem.objects.create(
            user=self.user, product=self.product, key=str(self.product.id), quantity=quantity,
        )
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': quantity,
                'price': '100.00',
                'variant_id': None,
            },
        }
        if coupon_id is not None:
            session['coupon_id'] = coupon_id
        session.save()

    def _order_post(self, token='token-abc', **overrides):
        data = {
            'checkout_token': token,
            'first_name': 'Ada',
            'last_name': 'Lovelace',
            'email': 'ada@example.com',
            'address': '5 Analytical Way',
            'postal_code': '560001',
            'city': 'Bangalore',
            'phone': '9999999999',
            'state': 'Karnataka',
            'country': 'India',
        }
        data.update(overrides)
        return self.client.post(reverse('order:order_create'), data)

    def test_creates_order_and_clears_cart(self):
        self._seed_cart()
        response = self._order_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user, checkout_token='token-abc')
        self.assertEqual(order.items.count(), 1)
        # Session cart cleared…
        session = self.client.session
        self.assertEqual(session.get('cart'), {})
        self.assertIsNone(session.get('coupon_id'))
        # …and the persisted DB cart is gone too.
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_double_submit_creates_single_order(self):
        self._seed_cart()
        first = self._order_post()
        second = self._order_post()
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        orders = Order.objects.filter(user=self.user, checkout_token='token-abc')
        self.assertEqual(orders.count(), 1)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)

    def test_resubmitting_existing_token_reuses_order(self):
        self._seed_cart()
        existing = Order.objects.create(
            user=self.user,
            checkout_token='premade-token',
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
        )
        response = self._order_post(token='premade-token')
        self.assertRedirects(
            response,
            reverse('shipping:shipping_select', args=[existing.id]),
            fetch_redirect_response=False,
        )
        self.assertEqual(Order.objects.filter(user=self.user, checkout_token='premade-token').count(), 1)

    def test_expired_coupon_is_revalidated_at_checkout(self):
        coupon = Coupon.objects.create(
            code='EXPIRED5',
            discount=5,
            valid_from=timezone.now() - timezone.timedelta(days=10),
            valid_to=timezone.now() - timezone.timedelta(days=1),
            active=True,
        )
        self._seed_cart(coupon_id=coupon.id)
        response = self._order_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user, checkout_token='token-abc')
        self.assertIsNone(order.coupon)
        self.assertEqual(order.discount, Decimal('0.00'))

    def test_valid_coupon_is_applied(self):
        coupon = Coupon.objects.create(
            code='SAVE10',
            discount=10,
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_to=timezone.now() + timezone.timedelta(days=1),
            active=True,
        )
        self._seed_cart(coupon_id=coupon.id)
        response = self._order_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user, checkout_token='token-abc')
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.discount, Decimal('20.00'))

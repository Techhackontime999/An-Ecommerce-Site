from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Category, Product

from order.models import Order
from order.access import GUEST_ORDERS_SESSION_KEY


class GuestCheckoutTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Earbuds',
            slug='earbuds',
            price=Decimal('100.00'),
            stock=10,
        )
        self.client = Client(SERVER_NAME='localhost')

    def _seed_session_cart(self, quantity=2):
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {
                'quantity': quantity,
                'price': '100.00',
                'variant_id': None,
            },
        }
        session.save()

    def _order_post(self, token='token-guest'):
        return self.client.post(reverse('order:order_create'), {
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
        })

    def test_guest_places_order_without_account(self):
        self._seed_session_cart()
        response = self._order_post()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(checkout_token='token-guest')
        self.assertIsNone(order.user)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.email, 'ada@example.com')

    def test_guest_gains_session_access_and_can_reach_shipping(self):
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        session = self.client.session
        self.assertIn(order.id, session.get(GUEST_ORDERS_SESSION_KEY, []))
        response = self.client.get(reverse('shipping:shipping_select', args=[order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment method')

    def test_guest_can_view_own_order_detail(self):
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        response = self.client.get(reverse('order:order_detail', args=[order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Earbuds')

    def test_other_guest_session_cannot_see_order(self):
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        # A different browser/session has no access.
        other = Client(SERVER_NAME='localhost')
        response = other.get(reverse('order:order_detail', args=[order.id]))
        self.assertEqual(response.status_code, 404)

    def test_signed_in_guest_order_is_not_visible_to_other_users(self):
        from django.contrib.auth import get_user_model
        stranger = get_user_model().objects.create_user(username='stranger', password='pass1234')
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        other = Client(SERVER_NAME='localhost')
        other.force_login(stranger)
        response = other.get(reverse('order:order_detail', args=[order.id]))
        self.assertEqual(response.status_code, 404)

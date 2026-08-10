from decimal import Decimal
import time
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

import django.core.signing as django_signing

from payments.models import Payment
from shop.models import Category, Product

from order.models import Order
from order.access import GUEST_ORDERS_SESSION_KEY
from order.access import GUEST_ACCESS_TOKEN_MAX_AGE
from order.access import make_guest_access_token, order_id_from_guest_token


class GuestCheckoutTests(TestCase):
    def setUp(self):
        cache.clear()
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

    def test_guest_my_orders_lists_session_orders_without_login(self):
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        response = self.client.get(reverse('order:my_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)

    def test_anonymous_my_orders_without_session_is_200_not_login(self):
        fresh = Client(SERVER_NAME='localhost')
        response = fresh.get(reverse('order:my_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'You are viewing guest orders')

    def test_guest_my_orders_does_not_show_other_sessions_orders(self):
        self._seed_session_cart()
        self._order_post()
        order = Order.objects.get(checkout_token='token-guest')
        fresh = Client(SERVER_NAME='localhost')
        response = fresh.get(reverse('order:my_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, order.order_number)


class GuestEmailLinkTests(TestCase):
    """The signed link in the guest order-confirmation email.

    Guests have no account, so the email must open the order from any browser
    without a login. A signed, expiring token bound to the order id + email
    proves the clicker is the guest who placed the order.
    """

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Earbuds',
            slug='earbuds',
            price=Decimal('100.00'),
            stock=10,
        )
        self.guest = Client(SERVER_NAME='localhost')
        self.fresh = Client(SERVER_NAME='localhost')

    def _place_guest_order(self):
        session = self.guest.session
        session['cart'] = {
            str(self.product.id): {'quantity': 1, 'price': '100.00', 'variant_id': None},
        }
        session.save()
        self.guest.post(reverse('order:order_create'), {
            'checkout_token': 'token-email-link',
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
        return Order.objects.get(checkout_token='token-email-link')

    def test_token_opens_tracking_from_fresh_browser(self):
        order = self._place_guest_order()
        token = make_guest_access_token(order)
        # Brand-new client: no session access, no login.
        response = self.fresh.get(
            reverse('shipping:order_tracking', args=[order.id]) + f'?token={token}'
        )
        self.assertEqual(response.status_code, 200)

    def test_token_opens_detail_and_invoice_from_fresh_browser(self):
        order = self._place_guest_order()
        token = make_guest_access_token(order)
        detail = self.fresh.get(
            reverse('order:order_detail', args=[order.id]) + f'?token={token}'
        )
        self.assertEqual(detail.status_code, 200)
        invoice = self.fresh.get(
            reverse('order:order_invoice', args=[order.id]) + f'?token={token}'
        )
        self.assertEqual(invoice.status_code, 200)

    def test_missing_or_forged_token_is_rejected(self):
        order = self._place_guest_order()
        self.assertEqual(
            self.fresh.get(reverse('shipping:order_tracking', args=[order.id])).status_code,
            404,
        )
        self.assertEqual(
            self.fresh.get(
                reverse('shipping:order_tracking', args=[order.id]) + '?token=forged'
            ).status_code,
            404,
        )

    def test_tampered_token_is_rejected(self):
        order = self._place_guest_order()
        token = make_guest_access_token(order)
        last = 'a' if token[-1] != 'a' else 'b'
        tampered = token[:-1] + last
        response = self.fresh.get(
            reverse('shipping:order_tracking', args=[order.id]) + f'?token={tampered}'
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_token_is_rejected(self):
        order = self._place_guest_order()
        # Sign the token as if it were created 30 days + 1 minute ago.
        expired_ts = time.time() - GUEST_ACCESS_TOKEN_MAX_AGE - 60
        with mock.patch.object(django_signing.time, 'time', return_value=expired_ts):
            token = TimestampSigner().sign('{}:{}'.format(order.id, order.email))
        self.assertIsNone(order_id_from_guest_token(token))
        response = self.fresh.get(
            reverse('shipping:order_tracking', args=[order.id]) + f'?token={token}'
        )
        self.assertEqual(response.status_code, 404)

    def test_token_grants_no_access_to_orders_with_an_account(self):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username='owner', password='pass1234')
        order = Order.objects.create(
            user=user,
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
            phone='9999999999',
        )
        token = make_guest_access_token(order)
        response = self.fresh.get(
            reverse('shipping:order_tracking', args=[order.id]) + f'?token={token}'
        )
        self.assertEqual(response.status_code, 404)

    def test_email_links_to_my_orders_for_accounts(self):
        from django.contrib.auth import get_user_model
        from notifications.emails import _order_track_url
        user = get_user_model().objects.create_user(username='owner2', password='pass1234')
        order = Order.objects.create(
            user=user,
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
            phone='9999999999',
        )
        self.assertEqual(
            _order_track_url(order),
            '{}/order/my-orders/'.format(settings.SITE_URL),
        )

    def test_email_links_to_signed_tracking_page_for_guests(self):
        from notifications.emails import _order_track_url
        order = self._place_guest_order()
        url = _order_track_url(order)
        self.assertIn('/shipping/tracking/{}/'.format(order.id), url)
        self.assertIn('?token=', url)
        token = url.split('?token=', 1)[1]
        self.assertEqual(order_id_from_guest_token(token), (order.id, 'ada@example.com'))


class GuestAbuseProtectionTests(TestCase):
    """Loss-protection rules for guest orders (no account to trace)."""

    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Earbuds',
            slug='earbuds',
            price=Decimal('100.00'),
            stock=10,
        )
        self.client = Client(SERVER_NAME='localhost')

    def _seed_session_cart(self):
        session = self.client.session
        session['cart'] = {
            str(self.product.id): {'quantity': 1, 'price': '100.00', 'variant_id': None},
        }
        session.save()

    def _order_post(self, token):
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

    def test_paid_guest_order_cannot_be_cancelled(self):
        self._seed_session_cart()
        self._order_post('token-paid-guest')
        order = Order.objects.get(checkout_token='token-paid-guest')
        Payment.objects.create(
            order=order, razorpay_order_id='ord_guest_paid',
            amount=Decimal('236.00'), status='captured',
        )
        response = self.client.post(
            reverse('order:order_cancel', args=[order.id]), follow=True,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(order.refunds.exists())
        self.assertContains(response, 'Paid guest orders cannot be cancelled online')

    def test_unpaid_guest_order_can_be_cancelled(self):
        self._seed_session_cart()
        self._order_post('token-unpaid-guest')
        order = Order.objects.get(checkout_token='token-unpaid-guest')
        response = self.client.post(reverse('order:order_cancel', args=[order.id]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertRedirects(response, reverse('order:order_detail', args=[order.id]))

    def test_customer_cancel_allowed_matches_guard(self):
        self._seed_session_cart()
        self._order_post('token-flag-guest')
        order = Order.objects.get(checkout_token='token-flag-guest')
        self.assertTrue(order.customer_cancel_allowed)
        Payment.objects.create(
            order=order, razorpay_order_id='ord_guest_flag',
            amount=Decimal('100.00'), status='captured',
        )
        order.refresh_from_db()
        self.assertFalse(order.customer_cancel_allowed)

        from django.contrib.auth import get_user_model
        user = get_user_model().objects.create_user(username='acctowner', password='pass1234')
        acct = Order.objects.create(
            user=user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Way', postal_code='560001', city='Bangalore', phone='9999999999',
        )
        self.assertTrue(acct.customer_cancel_allowed)
        Payment.objects.create(
            order=acct, razorpay_order_id='ord_acct_flag',
            amount=Decimal('100.00'), status='captured',
        )
        acct.refresh_from_db()
        self.assertTrue(acct.customer_cancel_allowed)

    def test_throttle_blocks_after_five_guest_orders(self):
        from core.throttle import throttle_allows
        request = RequestFactory().post('/order/create/')
        request.META['REMOTE_ADDR'] = '203.0.113.99'
        for _ in range(5):
            self.assertTrue(throttle_allows(
                'guest-order-create', request, max_requests=5, window_seconds=3600,
            ))
        self.assertFalse(throttle_allows(
            'guest-order-create', request, max_requests=5, window_seconds=3600,
        ))
        get_request = RequestFactory().get('/order/create/')
        get_request.META['REMOTE_ADDR'] = '203.0.113.99'
        self.assertTrue(throttle_allows(
            'guest-order-create', get_request, max_requests=5, window_seconds=3600,
        ))

    def test_guest_order_create_view_throttled_per_ip(self):
        ip = '203.0.113.9'
        for i in range(5):
            self._seed_session_cart()
            response = self.client.post(
                reverse('order:order_create'),
                {
                    'checkout_token': f'throttle-{i}',
                    'first_name': 'Ada', 'last_name': 'Lovelace',
                    'email': 'ada@example.com', 'address': '5 Way',
                    'postal_code': '560001', 'city': 'Bangalore',
                    'phone': '9999999999', 'state': 'Karnataka', 'country': 'India',
                },
                HTTP_X_FORWARDED_FOR=ip,
            )
            self.assertEqual(response.status_code, 302)
            self.assertTrue(Order.objects.filter(checkout_token=f'throttle-{i}').exists())

        self._seed_session_cart()
        response = self.client.post(
            reverse('order:order_create'),
            {
                'checkout_token': 'throttle-over',
                'first_name': 'Ada', 'last_name': 'Lovelace',
                'email': 'ada@example.com', 'address': '5 Way',
                'postal_code': '560001', 'city': 'Bangalore',
                'phone': '9999999999', 'state': 'Karnataka', 'country': 'India',
            },
            HTTP_X_FORWARDED_FOR=ip,
            follow=True,
        )
        self.assertFalse(Order.objects.filter(checkout_token='throttle-over').exists())
        self.assertContains(response, 'Too many guest orders')

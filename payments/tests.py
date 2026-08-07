import hashlib
import hmac
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from order.models import Order, OrderItem
from shop.models import Category, Product

from .models import Payment, PaymentAuditLog
from .services import (
    finalize_payment,
    verify_callback_signature,
    verify_webhook_signature,
)


def _callback_sig(order_id, payment_id):
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f'{order_id}|{payment_id}'.encode(),
        hashlib.sha256,
    ).hexdigest()
    return expected


class FinalizePaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='payer', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('50.00'), quantity=2)
        self.payment = Payment.objects.create(
            order=self.order, razorpay_order_id='ord_pay1', amount=Decimal('100.00'),
            currency='INR', status='created',
        )

    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_finalize_marks_paid_decrements_stock_and_audits(self, side_effects):
        ok = finalize_payment(self.payment, 'pay_1', 'sig', source='webhook')
        self.assertTrue(ok)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.payment.status, 'captured')
        self.assertTrue(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(
            PaymentAuditLog.objects.filter(payment=self.payment, new_status='captured').count(), 1,
        )

    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_finalize_is_idempotent(self, side_effects):
        self.assertTrue(finalize_payment(self.payment, 'pay_1', source='webhook'))
        self.assertFalse(finalize_payment(self.payment, 'pay_1', source='webhook'))
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.payment.status, 'captured')
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(
            PaymentAuditLog.objects.filter(payment=self.payment, new_status='captured').count(), 1,
        )

    @mock.patch('payments.services.get_razorpay_client')
    def test_finalize_rejects_cancelled_order(self, fake_client):
        fake_client.return_value.payment.refund.return_value = {'id': 'rfnd_1'}
        self.order.status = Order.Status.CANCELLED
        self.order.save()
        ok = finalize_payment(self.payment, 'pay_1', source='webhook')
        self.assertFalse(ok)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.payment.status, 'refunded')
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock, 5)

    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):
            finalize_payment(self.payment, 'pay_1', source='attacker')


class SignatureTests(TestCase):
    def test_callback_signature_verify(self):
        self.assertTrue(verify_callback_signature('ord_1', 'pay_1', _callback_sig('ord_1', 'pay_1')))
        self.assertFalse(verify_callback_signature('ord_1', 'pay_1', 'deadbeef'))

    @override_settings(DEBUG=False, RAZORPAY_WEBHOOK_SECRET='')
    def test_webhook_signature_rejects_when_no_secret_configured(self):
        self.assertFalse(verify_webhook_signature('{"a":1}', ''))

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_webhook_signature_verify(self):
        body = '{"event":"payment.captured"}'
        sig = hmac.new(b'webhook-secret', body.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, sig))
        self.assertFalse(verify_webhook_signature(body, 'bad'))

    @override_settings(DEBUG=True, RAZORPAY_WEBHOOK_SECRET='')
    def test_webhook_signature_falls_back_to_key_secret_in_debug(self):
        body = '{"event":"payment.captured"}'
        sig = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, sig))


class PaymentEndpointTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='payer2', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('50.00'), quantity=1)
        self.payment = Payment.objects.create(
            order=self.order, razorpay_order_id='ord_cb1', amount=Decimal('50.00'),
            currency='INR', status='created',
        )
        self.client = Client(SERVER_NAME='localhost')

    def test_callback_rejects_get(self):
        response = self.client.get(reverse('payments:callback'))
        self.assertEqual(response.status_code, 405)

    def test_webhook_rejects_get(self):
        response = self.client.get(reverse('payments:webhook'))
        self.assertEqual(response.status_code, 405)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_webhook_rejects_bad_signature(self):
        response = self.client.post(
            reverse('payments:webhook'),
            data='{"event":"payment.captured"}',
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='forged',
        )
        self.assertEqual(response.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'created')

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_webhook_with_valid_signature_captures(self, side_effects):
        body = '{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_wh1","order_id":"ord_cb1"}}}}'
        sig = hmac.new(b'webhook-secret', body.encode(), hashlib.sha256).hexdigest()
        response = self.client.post(
            reverse('payments:webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.product.stock, 4)

    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_callback_with_valid_signature_captures(self, side_effects):
        response = self.client.post(
            reverse('payments:callback'),
            {
                'razorpay_order_id': 'ord_cb1',
                'razorpay_payment_id': 'pay_cb1',
                'razorpay_signature': _callback_sig('ord_cb1', 'pay_cb1'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.product.stock, 4)

    @mock.patch('payments.views.get_razorpay_client')
    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_verify_rejects_get(self, side_effects, fake_client):
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:verify', args=[self.order.id]))
        self.assertEqual(response.status_code, 405)

    @mock.patch('payments.views.get_razorpay_client')
    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_verify_checks_gateway_then_captures(self, side_effects, fake_client):
        fake_client.return_value.payment.fetch.return_value = {'id': 'pay_v1', 'status': 'captured'}
        self.payment.razorpay_payment_id = 'pay_v1'
        self.payment.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('payments:verify', args=[self.order.id]))
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.paid)

    def test_success_page_redirects_unpaid_orders(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('payments:success', args=[self.order.id]))
        self.assertRedirects(response, reverse('payments:checkout', args=[self.order.id]), fetch_redirect_response=False)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'created')

import hashlib
import hmac
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from order.models import Order, OrderItem
from shop.models import Category, Product

from .models import Payment, PaymentAuditLog
from .services import (
    _fail_and_refund_captured,
    finalize_payment,
    gateway_charge,
    refund_captured_payment,
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

    @mock.patch('payments.services.refund_payment', return_value=(True, 'rfnd_stock'))
    @mock.patch('payments.services.notify', autospec=True)
    def test_finalize_refunds_and_fails_when_stock_is_insufficient(self, notify, refund):
        self.product.stock = 1
        self.product.save()
        ok = finalize_payment(self.payment, 'pay_short', 'sig', source='webhook')
        self.assertFalse(ok)
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.payment.status, 'failed')
        self.assertEqual(self.payment.razorpay_payment_id, 'pay_short')
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        self.assertEqual(self.product.stock, 1)
        refund.assert_called_once()
        notify.assert_called()
        self.assertEqual(
            PaymentAuditLog.objects.filter(payment=self.payment, new_status='failed').count(), 1,
        )

    def test_invalid_source_rejected(self):
        with self.assertRaises(ValueError):
            finalize_payment(self.payment, 'pay_1', source='attacker')

    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_finalize_keeps_payment_id_on_reentry(self, side_effects):
        self.payment.status = 'captured'
        self.payment.save(update_fields=['status'])
        self.assertFalse(finalize_payment(self.payment, 'pay_late', 'sig', source='webhook'))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'captured')
        self.assertEqual(self.payment.razorpay_payment_id, 'pay_late')
        self.assertEqual(self.payment.razorpay_signature, 'sig')


class GatewayChargeTests(TestCase):
    @mock.patch('payments.services.get_rates', return_value={'INR': 1.0})
    def test_inr_is_charged_directly_in_minor_units(self, rates):
        amount, currency, minor = gateway_charge(Decimal('1234.56'))
        self.assertEqual(currency, 'INR')
        self.assertEqual(amount, Decimal('1234.56'))
        self.assertEqual(minor, 123456)

    @mock.patch('payments.services.get_rates', return_value={'INR': 1.0, 'USD': 0.0114})
    def test_converts_base_inr_to_charge_currency(self, rates):
        with self.settings(PAYMENTS_CURRENCY='USD'):
            amount, currency, minor = gateway_charge(Decimal('1234.56'))
        self.assertEqual(currency, 'USD')
        self.assertEqual(amount, Decimal('14.07'))
        self.assertEqual(minor, 1407)


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

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    def test_webhook_returns_5xx_for_unknown_order(self):
        body = '{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_x1","order_id":"ord_missing"}}}}'
        sig = hmac.new(b'webhook-secret', body.encode(), hashlib.sha256).hexdigest()
        response = self.client.post(
            reverse('payments:webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, 500)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook-secret')
    @mock.patch('payments.views.finalize_payment', side_effect=Exception('boom'))
    def test_webhook_returns_5xx_when_processing_fails(self, finalize):
        body = '{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_wh2","order_id":"ord_cb1"}}}}'
        sig = hmac.new(b'webhook-secret', body.encode(), hashlib.sha256).hexdigest()
        response = self.client.post(
            reverse('payments:webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )
        self.assertEqual(response.status_code, 500)
        finalize.assert_called_once()

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


class CollectCodCashTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cod', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=10,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('50.00'), quantity=2)
        from logistics.models import Shipment
        self.shipment = Shipment.objects.create(
            order=self.order, shipment_number='SSD-COD-1', destination_pincode='560001',
            payment_mode='cod', cod_amount=Decimal('100.00'), currency='INR',
        )

    def test_records_cash_collection(self):
        from payments.services import collect_cod_cash
        ok = collect_cod_cash(self.shipment)
        self.assertTrue(ok)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.status, 'captured')
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.razorpay_order_id, 'cod-SSD-COD-1')
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(
            PaymentAuditLog.objects.filter(payment=payment, new_status='captured').count(), 1,
        )

    def test_is_idempotent(self):
        from payments.services import collect_cod_cash
        self.assertTrue(collect_cod_cash(self.shipment))
        self.assertFalse(collect_cod_cash(self.shipment))
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.product.stock, 8)

    def test_prepaid_shipment_is_noop(self):
        from logistics.models import Shipment
        from payments.services import collect_cod_cash
        prepaid = Shipment.objects.create(
            order=self.order, shipment_number='SSD-PRE-1', destination_pincode='560001',
        )
        self.assertFalse(collect_cod_cash(prepaid))
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

    def test_insufficient_stock_rolls_back_collection(self):
        from logistics.models import Shipment
        from payments.services import collect_cod_cash
        Shipment.objects.create(
            order=self.order, shipment_number='SSD-COD-2', destination_pincode='560001',
            payment_mode='cod', cod_amount=Decimal('100.00'),
        )
        self.product.stock = 1
        self.product.save()
        self.assertFalse(collect_cod_cash(self.shipment))
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertFalse(Payment.objects.filter(order=self.order).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)


def _link_sig(payment_link_id, reference_id, status, payment_id):
    return hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f'{payment_link_id}|{reference_id}|{status}|{payment_id}'.encode(),
        hashlib.sha256,
    ).hexdigest()


class CheckoutViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='shopper', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('50.00'), quantity=2)
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)

    @mock.patch('payments.views.create_razorpay_order', return_value='ord_rzp1')
    @mock.patch('payments.views.create_payment_link', return_value=('plink_1', 'https://rzp.test/plink_1'))
    def test_first_visit_creates_payment_and_renders_link(self, create_link, create_order):
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        create_order.assert_called_once()
        create_link.assert_called_once()
        payment = Payment.objects.get(order=self.order)
        self.assertEqual(payment.razorpay_order_id, 'ord_rzp1')
        self.assertEqual(payment.razorpay_payment_link_id, 'plink_1')
        self.assertEqual(payment.razorpay_payment_link_url, 'https://rzp.test/plink_1')
        self.assertEqual(response.context['payment_link_url'], 'https://rzp.test/plink_1')
        self.assertEqual(response.context['razorpay_order_id'], 'ord_rzp1')
        self.assertContains(response, 'https://rzp.test/plink_1')
        self.assertContains(response, 'https://checkout.razorpay.com/v1/checkout.js')
        self.assertContains(response, 'ord_rzp1')

    @mock.patch('payments.views.create_razorpay_order', return_value='ord_rzp2')
    @mock.patch('payments.views.create_payment_link', return_value=('plink_2', 'https://rzp.test/plink_2'))
    def test_existing_created_payment_gets_fresh_gateway_objects(self, create_link, create_order):
        Payment.objects.create(
            order=self.order, razorpay_payment_link_id='plink_1',
            razorpay_payment_link_url='https://rzp.test/plink_1',
            amount=Decimal('100.00'), currency='INR', status='created',
        )
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        create_order.assert_called_once()
        create_link.assert_called_once()
        self.assertEqual(response.context['payment_link_url'], 'https://rzp.test/plink_2')
        self.payment = Payment.objects.get(order=self.order)
        self.assertEqual(self.payment.razorpay_order_id, 'ord_rzp2')
        self.assertEqual(self.payment.razorpay_payment_link_id, 'plink_2')
        self.assertEqual(self.payment.razorpay_payment_link_url, 'https://rzp.test/plink_2')
        self.assertEqual(self.payment.status, 'created')
        self.assertEqual(Payment.objects.filter(order=self.order).count(), 1)

    @mock.patch('payments.views.create_razorpay_order', return_value='ord_rzp_new')
    @mock.patch('payments.views.create_payment_link', return_value=('plink_new', 'https://rzp.test/plink_new'))
    def test_failed_payment_gets_fresh_gateway_objects(self, create_link, create_order):
        Payment.objects.create(
            order=self.order, razorpay_payment_link_id='plink_dead',
            razorpay_payment_link_url='https://rzp.test/plink_dead',
            amount=Decimal('100.00'), currency='INR', status='failed',
        )
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        create_order.assert_called_once()
        create_link.assert_called_once()
        self.assertEqual(response.context['payment_link_url'], 'https://rzp.test/plink_new')
        self.payment = Payment.objects.get(order=self.order)
        self.assertEqual(self.payment.razorpay_order_id, 'ord_rzp_new')
        self.assertEqual(self.payment.status, 'created')

    @mock.patch('payments.views.create_razorpay_order', side_effect=Exception('gateway down'))
    @mock.patch('payments.views.create_payment_link', side_effect=Exception('gateway down'))
    def test_gateway_failure_renders_error_page(self, create_link, create_order):
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payments/error.html')
        self.assertTrue(response.context['gateway_error'])

    @mock.patch('payments.views.create_razorpay_order', side_effect=Exception('order api down'))
    @mock.patch('payments.views.create_payment_link', return_value=('plink_fb', 'https://rzp.test/plink_fb'))
    def test_renders_hosted_link_when_embedded_order_fails(self, create_link, create_order):
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['razorpay_order_id'], '')
        self.assertEqual(response.context['payment_link_url'], 'https://rzp.test/plink_fb')
        self.assertContains(response, 'https://rzp.test/plink_fb')
        self.assertNotContains(response, 'https://checkout.razorpay.com/v1/checkout.js')

    def test_paid_order_redirects_to_success(self):
        self.order.paid = True
        self.order.save()
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertRedirects(response, reverse('payments:success', args=[self.order.id]), fetch_redirect_response=False)


class CodCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='codshopper', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=5,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('50.00'), quantity=2)
        self.client = Client(SERVER_NAME='localhost')
        self.client.force_login(self.user)

    def test_cod_order_renders_confirmation_without_gateway(self):
        self.order.payment_method = Order.PaymentMethod.COD
        self.order.save()
        response = self.client.get(reverse('payments:checkout', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['cod_mode'])
        self.assertContains(response, 'Confirm Cash on Delivery order')
        # No gateway objects are created for COD orders.
        self.assertNotContains(response, 'checkout.razorpay.com/v1/checkout.js')
        self.assertIsNone(response.context.get('razorpay_order_id'))

    def test_confirming_cod_places_order_and_queues_fulfilment(self):
        self.order.payment_method = Order.PaymentMethod.COD
        self.order.save()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('payments:checkout', args=[self.order.id]), {
                'payment_method': 'cod',
                'confirm': '1',
            })
        self.assertRedirects(response, reverse('payments:success', args=[self.order.id]), fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        from jobs.models import Job
        job = Job.objects.filter(kind='fulfil_order').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.payload['order_id'], self.order.pk)

    def test_cod_confirm_is_idempotent(self):
        self.order.payment_method = Order.PaymentMethod.COD
        self.order.save()
        from jobs.models import Job
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('payments:checkout', args=[self.order.id]), {
                'payment_method': 'cod', 'confirm': '1',
            })
            # Already processing → no-op, no second fulfilment kick.
            self.order.status = Order.Status.PROCESSING
            self.order.save()
            self.client.post(reverse('payments:checkout', args=[self.order.id]), {
                'payment_method': 'cod', 'confirm': '1',
            })
        self.assertEqual(Job.objects.filter(kind='fulfil_order').count(), 1)

    def test_switching_from_cod_back_to_online(self):
        self.order.payment_method = Order.PaymentMethod.COD
        self.order.save()
        with mock.patch('payments.views.create_razorpay_order', return_value='ord_online1'):
            with mock.patch('payments.views.create_payment_link', return_value=('plink_1', 'https://rzp.test/plink_1')):
                response = self.client.post(reverse('payments:checkout', args=[self.order.id]), {
                    'payment_method': 'online',
                })
                self.assertRedirects(response, reverse('payments:checkout', args=[self.order.id]), fetch_redirect_response=False)
                self.order.refresh_from_db()
                self.assertEqual(self.order.payment_method, Order.PaymentMethod.ONLINE)
                follow = self.client.get(response.url)
                self.assertEqual(follow.status_code, 200)
                self.assertIsNone(follow.context.get('cod_mode'))


class PaymentLinkCallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='linkuser', password='pass1234')
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
            order=self.order, razorpay_payment_link_id='plink_cb1',
            razorpay_payment_link_url='https://rzp.test/plink_cb1',
            amount=Decimal('100.00'), currency='INR', status='created',
        )
        self.client = Client(SERVER_NAME='localhost')

    @mock.patch('payments.services._post_capture_side_effects', autospec=True)
    def test_valid_signature_captures_and_redirects(self, side_effects):
        response = self.client.get(reverse('payments:link_callback'), {
            'razorpay_payment_link_id': 'plink_cb1',
            'razorpay_payment_link_reference_id': 'ref_cb1',
            'razorpay_payment_link_status': 'paid',
            'razorpay_payment_id': 'pay_link1',
            'razorpay_signature': _link_sig('plink_cb1', 'ref_cb1', 'paid', 'pay_link1'),
        })
        self.assertRedirects(response, reverse('payments:success', args=[self.order.id]), fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.product.stock, 3)

    def test_bad_signature_marks_failed_and_redirects_to_error(self):
        response = self.client.get(reverse('payments:link_callback'), {
            'razorpay_payment_link_id': 'plink_cb1',
            'razorpay_payment_link_reference_id': 'ref_cb1',
            'razorpay_payment_link_status': 'paid',
            'razorpay_payment_id': 'pay_link1',
            'razorpay_signature': 'forged',
        })
        self.assertRedirects(response, reverse('payments:error', args=[self.order.id]), fetch_redirect_response=False)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'failed')
        self.assertFalse(self.order.paid)

    def test_failed_status_redirects_to_error(self):
        response = self.client.get(reverse('payments:link_callback'), {
            'razorpay_payment_link_id': 'plink_cb1',
            'razorpay_payment_link_reference_id': 'ref_cb1',
            'razorpay_payment_link_status': 'failed',
            'razorpay_payment_id': 'pay_link1',
            'razorpay_signature': _link_sig('plink_cb1', 'ref_cb1', 'failed', 'pay_link1'),
        })
        self.assertRedirects(response, reverse('payments:error', args=[self.order.id]), fetch_redirect_response=False)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'failed')

    def test_unknown_link_is_bad_request(self):
        response = self.client.get(reverse('payments:link_callback'), {
            'razorpay_payment_link_id': 'plink_missing',
            'razorpay_payment_link_reference_id': 'ref_cb1',
            'razorpay_payment_link_status': 'paid',
            'razorpay_payment_id': 'pay_link1',
            'razorpay_signature': _link_sig('plink_missing', 'ref_cb1', 'paid', 'pay_link1'),
        })
        self.assertEqual(response.status_code, 400)


class RefundDurabilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='refundee', password='pass1234')
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
            order=self.order, razorpay_order_id='ord_ref', razorpay_payment_id='pay_ref1',
            amount=Decimal('59.00'), currency='INR', status='captured',
        )

    @mock.patch('payments.services.refund_payment', return_value=(False, 'gateway down'))
    def test_refund_captured_payment_enqueues_retry_job_on_failure(self, refund):
        from jobs.models import Job
        ok, detail = refund_captured_payment(self.payment, note='test')
        self.assertFalse(ok)
        self.assertEqual(detail, 'gateway down')
        job = Job.objects.filter(kind='refund_payment').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.payload['payment_id'], self.payment.pk)
        self.assertEqual(job.dedupe_key, f'refund-payment:{self.payment.pk}')

    @mock.patch('payments.services.refund_payment', return_value=(True, 'rfnd_ok'))
    def test_refund_captured_payment_skips_enqueue_on_success(self, refund):
        from jobs.models import Job
        ok, detail = refund_captured_payment(self.payment, note='test')
        self.assertTrue(ok)
        self.assertEqual(detail, 'rfnd_ok')
        self.assertFalse(Job.objects.filter(kind='refund_payment').exists())

    @mock.patch('payments.services.refund_payment', return_value=(False, 'gateway down'))
    def test_fail_and_refund_captured_queues_retry(self, refund):
        from jobs.models import Job
        self.payment.status = 'failed'
        self.payment.save()
        _fail_and_refund_captured(self.payment, 'pay_ref1', 'out of stock')
        job = Job.objects.filter(kind='refund_payment').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.payload['payment_id'], self.payment.pk)
        self.assertIn('out of stock', job.payload['note'])

    @mock.patch('payments.services.refund_payment')
    def test_refund_job_handler_refunds_and_succeeds(self, refund):
        refund.return_value = (True, 'rfnd_job')
        from jobs.models import Job
        from jobs.services import enqueue
        job = enqueue('refund_payment', {'payment_id': self.payment.pk, 'note': 'reconcile'})
        from jobs.management.commands.run_worker import Command
        Command(stdout=__import__('io').StringIO()).handle(once=True, poll=0, limit=10, max_runtime=0)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.SUCCEEDED)
        refund.assert_called_once()


class ReconcileRefundTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='recon', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, name='Pod', slug='pod', price=Decimal('50.00'), stock=5,
        )

    def _order_and_payment(self, **payment_overrides):
        order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=order, product=self.product, price=Decimal('50.00'), quantity=1)
        defaults = dict(
            order=order, razorpay_order_id=f'ord_{order.id}', razorpay_payment_id='pay_recon1',
            amount=Decimal('59.00'), currency='INR', status='captured',
        )
        defaults.update(payment_overrides)
        return order, Payment.objects.create(**defaults)

    def test_captured_cancelled_order_is_reconciled(self):
        from jobs.models import Job
        order, _ = self._order_and_payment()
        order.status = Order.Status.CANCELLED
        order.save()
        call_command('reconcile_refunds')
        job = Job.objects.filter(kind='refund_payment').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.payload['payment_id'], Payment.objects.get(order=order).pk)

    def test_failed_payment_with_gateway_id_is_reconciled(self):
        from jobs.models import Job
        _, payment = self._order_and_payment(status='failed')
        call_command('reconcile_refunds')
        job = Job.objects.filter(kind='refund_payment').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.payload['payment_id'], payment.pk)

    def test_already_refunded_is_skipped(self):
        from jobs.models import Job
        self._order_and_payment(status='refunded')
        call_command('reconcile_refunds')
        self.assertFalse(Job.objects.filter(kind='refund_payment').exists())

    def test_cod_reference_is_skipped(self):
        from jobs.models import Job
        order, _ = self._order_and_payment(
            razorpay_payment_id='cod-SSD-1', status='captured',
        )
        order.status = Order.Status.CANCELLED
        order.save()
        call_command('reconcile_refunds')
        self.assertFalse(Job.objects.filter(kind='refund_payment').exists())

    def test_order_with_admin_refund_row_is_skipped(self):
        from jobs.models import Job
        from order.models import Refund
        order, _ = self._order_and_payment()
        order.status = Order.Status.CANCELLED
        order.save()
        Refund.objects.create(
            order=order, amount=Decimal('59.00'),
            method=Refund.Method.ORIGINAL_PAYMENT, status=Refund.Status.COMPLETED,
        )
        call_command('reconcile_refunds')
        self.assertFalse(Job.objects.filter(kind='refund_payment').exists())

    def test_dry_run_does_not_enqueue(self):
        from jobs.models import Job
        order, _ = self._order_and_payment()
        order.status = Order.Status.CANCELLED
        order.save()
        call_command('reconcile_refunds', dry_run=True)
        self.assertFalse(Job.objects.filter(kind='refund_payment').exists())

    def test_enqueued_refund_job_is_deduped(self):
        from jobs.models import Job
        from payments.services import refund_captured_payment
        order, payment = self._order_and_payment()
        order.status = Order.Status.CANCELLED
        order.save()
        with mock.patch('payments.services.refund_payment', return_value=(False, 'down')):
            refund_captured_payment(payment, note='inline retry')
        call_command('reconcile_refunds')
        self.assertEqual(Job.objects.filter(kind='refund_payment').count(), 1)

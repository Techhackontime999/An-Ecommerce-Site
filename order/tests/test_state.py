from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from payments.models import Payment
from shop.models import Category, Product

from order.models import Order, OrderAuditLog, OrderItem, Refund, ReturnRequest
from order.services import cancel_order
from order.state import set_order_status


def make_order(user, **overrides):
    defaults = {
        'user': user,
        'first_name': 'Ada',
        'last_name': 'Lovelace',
        'email': 'ada@example.com',
        'address': '5 Way',
        'postal_code': '560001',
        'city': 'Bangalore',
        'phone': '9999999999',
        'state': 'Karnataka',
        'country': 'India',
    }
    defaults.update(overrides)
    return Order.objects.create(**defaults)


class OrderStateMachineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.actor = get_user_model().objects.create_user(username='staff1', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds',
            price=Decimal('100.00'), stock=10,
        )
        self.order = make_order(self.user)
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)

    def _set(self, status, **kw):
        return set_order_status(self.order, status, actor=self.actor, **kw)

    def test_forward_transitions_allowed(self):
        self.assertTrue(self._set(Order.Status.PROCESSING)[0])
        self.assertTrue(self._set(Order.Status.SHIPPED)[0])
        self.assertTrue(self._set(Order.Status.DELIVERED)[0])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.DELIVERED)

    def test_illegal_backward_transition_rejected(self):
        self._set(Order.Status.PROCESSING)
        self._set(Order.Status.SHIPPED)
        ok, reason = self._set(Order.Status.PROCESSING)
        self.assertFalse(ok)
        self.assertIn('Cannot move', reason)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)

    def test_cancelled_order_can_never_be_delivered(self):
        """Regression: a late courier webhook must not resurrect a cancelled order."""
        self._set(Order.Status.CANCELLED)
        ok, _ = self._set(Order.Status.DELIVERED)
        self.assertFalse(ok)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_refunded_is_terminal(self):
        self._set(Order.Status.PROCESSING)
        self._set(Order.Status.DELIVERED)
        self.assertTrue(self._set(Order.Status.REFUNDED)[0])
        ok, _ = self._set(Order.Status.PROCESSING)
        self.assertFalse(ok)

    def test_audit_log_written_for_every_transition(self):
        self._set(Order.Status.PROCESSING, note='Payment captured.')
        self._set(Order.Status.SHIPPED)
        entries = list(self.order.audit_logs.all())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].from_status, Order.Status.PENDING)
        self.assertEqual(entries[0].to_status, Order.Status.PROCESSING)
        self.assertEqual(entries[0].actor, self.actor)
        self.assertEqual(entries[0].note, 'Payment captured.')

    def test_force_correction_is_logged_as_forced(self):
        self._set(Order.Status.PROCESSING)
        self._set(Order.Status.SHIPPED)
        ok, _ = self._set(Order.Status.PROCESSING, force=True)
        self.assertTrue(ok)
        entry = self.order.audit_logs.latest('created_at')
        self.assertEqual(entry.action, 'status_change_forced')
        self.assertEqual(entry.to_status, Order.Status.PROCESSING)

    def test_cancel_service_writes_audit(self):
        ok, _ = cancel_order(self.order, actor=self.user, reason='Changed my mind')
        self.assertTrue(ok)
        entry = self.order.audit_logs.latest('created_at')
        self.assertEqual(entry.from_status, Order.Status.PENDING)
        self.assertEqual(entry.to_status, Order.Status.CANCELLED)
        self.assertEqual(entry.actor, self.user)


class RefundOverPaymentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds-2',
            price=Decimal('100.00'), stock=10,
        )
        self.order = make_order(self.user)
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)
        self.payment = Payment.objects.create(
            order=self.order, razorpay_order_id='ord_paid',
            amount=Decimal('236.00'), status='captured',
        )

    def _refund(self, amount):
        return Refund(order=self.order, amount=Decimal(amount))

    def test_refund_cannot_exceed_paid_amount(self):
        refund = self._refund('237.00')
        with self.assertRaises(ValidationError):
            refund.full_clean()

    def test_full_refund_allowed(self):
        refund = self._refund('236.00')
        refund.full_clean()

    def test_partial_refund_then_over_refund_rejected(self):
        first = self._refund('100.00')
        first.save()
        second = self._refund('137.00')  # 100 + 137 = 237 > 236
        with self.assertRaises(ValidationError):
            second.full_clean()
        ok = self._refund('136.00')  # exactly the remainder
        ok.full_clean()

    def test_failed_refunds_do_not_count(self):
        first = self._refund('100.00')
        first.status = Refund.Status.FAILED
        first.save()
        ok = self._refund('136.00')
        ok.full_clean()

    def test_refund_on_unpaid_order_rejected(self):
        self.payment.status = 'created'
        self.payment.save()
        refund = self._refund('10.00')
        with self.assertRaises(ValidationError):
            refund.full_clean()


class ReturnRequestFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds-3',
            price=Decimal('100.00'), stock=10,
        )
        self.order = make_order(self.user)
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)
        self.client = self.client_class()
        self.client.force_login(self.user)

    def _return_url(self):
        return reverse('order:request_return', args=[self.order.pk])

    def test_return_only_allowed_after_delivery(self):
        response = self.client.post(self._return_url(), {'reason': 'defective', 'details': 'Does not switch on'})
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))
        self.assertFalse(ReturnRequest.objects.filter(order=self.order).exists())

    def test_return_request_created_for_delivered_order(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save()
        response = self.client.post(self._return_url(), {'reason': 'defective', 'details': 'Does not switch on'})
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))
        ret = ReturnRequest.objects.get(order=self.order)
        self.assertEqual(ret.status, ReturnRequest.Status.PENDING)
        self.assertEqual(ret.reason, 'defective')
        self.assertEqual(ret.user, self.user)

    def test_second_open_return_blocked(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save()
        ReturnRequest.objects.create(order=self.order, user=self.user, reason='defective')
        response = self.client.post(self._return_url(), {'reason': 'damaged'})
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))
        self.assertEqual(ReturnRequest.objects.filter(order=self.order).count(), 1)

    def test_invalid_reason_rejected(self):
        self.order.status = Order.Status.DELIVERED
        self.order.save()
        response = self.client.post(self._return_url(), {'reason': 'made_up_reason'})
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))
        self.assertFalse(ReturnRequest.objects.filter(order=self.order).exists())

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from payments.models import Payment
from shop.models import Category, Product

from order.models import Order, OrderItem, Refund
from order.services import create_refund


class CreateRefundServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds-x',
            price=Decimal('100.00'), stock=10,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace',
            email='ada@example.com', address='5 Analytical Way',
            postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)
        self.payment = Payment.objects.create(
            order=self.order, razorpay_order_id='ord_refund',
            amount=Decimal('236.00'), status='captured',
        )

    def test_create_refund_backed_by_captured_payment(self):
        refund = create_refund(self.order, amount=Decimal('100.00'))
        self.assertEqual(refund.status, Refund.Status.PENDING)
        self.assertEqual(refund.order_id, self.order.id)

    def test_create_refund_rejects_over_refund(self):
        with self.assertRaises(ValidationError):
            create_refund(self.order, amount=Decimal('237.00'))

    def test_create_refund_rejects_unpaid_order(self):
        self.payment.status = 'created'
        self.payment.save()
        with self.assertRaises(ValidationError):
            create_refund(self.order, amount=Decimal('10.00'))

    def test_create_refund_accumulates_against_existing(self):
        create_refund(self.order, amount=Decimal('200.00'))
        with self.assertRaises(ValidationError):
            create_refund(self.order, amount=Decimal('37.00'))
        create_refund(self.order, amount=Decimal('36.00'))


class AdminMarkPaidTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='admin', password='pass1234', is_staff=True, is_superuser=True,
        )
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds-a',
            price=Decimal('100.00'), stock=10,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace',
            email='ada@example.com', address='5 Analytical Way',
            postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)
        self.client.force_login(self.staff)
        self.changelist = reverse('admin:order_order_changelist')

    def _run_action(self, action):
        return self.client.post(self.changelist, {
            'action': action,
            '_selected_action': [str(self.order.pk)],
        }, follow=True)

    def test_mark_as_paid_creates_captured_payment_row(self):
        self._run_action('mark_as_paid')
        self.order.refresh_from_db()
        payment = Payment.objects.get(order=self.order)
        self.assertTrue(self.order.paid)
        self.assertEqual(payment.status, 'captured')
        self.assertEqual(payment.amount, self.order.get_total_cost())
        self.assertTrue(payment.razorpay_order_id.startswith('manual-'))

    def test_mark_as_paid_writes_audit_log(self):
        from payments.models import PaymentAuditLog
        self._run_action('mark_as_paid')
        payment = Payment.objects.get(order=self.order)
        self.assertTrue(
            PaymentAuditLog.objects.filter(payment=payment, new_status='captured', source='admin').exists(),
        )


class AdminRefundStatusTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='admin2', password='pass1234', is_staff=True, is_superuser=True,
        )
        self.user = get_user_model().objects.create_user(username='buyer2', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category, name='Buds', slug='buds-b',
            price=Decimal('100.00'), stock=10,
        )
        self.order = Order.objects.create(
            user=self.user, first_name='Ada', last_name='Lovelace',
            email='ada@example.com', address='5 Analytical Way',
            postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=1)
        Payment.objects.create(
            order=self.order, razorpay_order_id='ord_ref2',
            amount=Decimal('236.00'), status='captured',
        )
        self.refund = Refund.objects.create(order=self.order, amount=Decimal('236.00'))
        self.client.force_login(self.staff)
        self.changelist = reverse('admin:order_refund_changelist')

    def _run_action(self, action):
        return self.client.post(self.changelist, {
            'action': action,
            '_selected_action': [str(self.refund.pk)],
        }, follow=True)

    def test_mark_completed_updates_status(self):
        self._run_action('mark_as_completed')
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, Refund.Status.COMPLETED)
        self.assertIsNotNone(self.refund.processed_at)

    def test_over_refund_blocked_by_full_clean(self):
        Refund.objects.create(order=self.order, amount=Decimal('200.00'), status=Refund.Status.COMPLETED)
        self.refund.amount = Decimal('100.00')
        self.refund.save()
        response = self._run_action('mark_as_completed')
        self.assertContains(response, 'would exceed')
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, Refund.Status.PENDING)

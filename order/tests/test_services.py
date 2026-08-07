from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from payments.models import Payment
from shop.models import Category, Product

from order.models import Order, OrderItem
from order.services import cancel_order, invoice_number, invoice_totals


class OrderViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='pass1234')
        self.other = get_user_model().objects.create_user(username='stranger', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Nimbus Headphones',
            slug='nimbus-headphones',
            price=Decimal('100.00'),
            stock=10,
        )
        self.order = Order.objects.create(
            user=self.user,
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
            phone='9999999999',
            state='Karnataka',
            country='India',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('100.00'), quantity=2)
        self.client = Client(SERVER_NAME='localhost')

    def _cancel_url(self):
        return reverse('order:order_cancel', args=[self.order.pk])

    def test_detail_requires_login(self):
        response = self.client.get(reverse('order:order_detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_detail_only_for_owner(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse('order:order_detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_detail_renders_order_and_totals(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('order:order_detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nimbus Headphones')
        self.assertContains(response, self.order.order_number)
        self.assertContains(response, 'Download Invoice')

    def test_cancel_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(self._cancel_url())
        self.assertEqual(response.status_code, 405)

    def test_cancel_order_and_restore_stock(self):
        payment = Payment.objects.create(
            order=self.order,
            razorpay_order_id='ord_test_cancel',
            amount=Decimal('236.00'),
            status='captured',
        )
        from order.stock import commit_stock
        commit_stock(self.order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

        self.client.force_login(self.user)
        response = self.client.post(self._cancel_url(), {'reason': 'Changed my mind'})
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'refunded')

    def test_cannot_cancel_shipped_order(self):
        self.order.status = Order.Status.SHIPPED
        self.order.save()
        self.client.force_login(self.user)
        response = self.client.post(self._cancel_url())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)
        self.assertRedirects(response, reverse('order:order_detail', args=[self.order.pk]))

    def test_cancel_refunds_captured_payment(self):
        payment = Payment.objects.create(
            order=self.order,
            razorpay_order_id='ord_test_1',
            amount=Decimal('236.00'),
            status='captured',
        )
        ok, detail = cancel_order(self.order, actor=self.user, reason='test')
        self.assertTrue(ok)
        self.assertEqual(detail, 'cancelled_and_refunded')
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'refunded')

    def test_invoice_pdf_download(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('order:order_invoice', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(f'{invoice_number(self.order)}.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))


class OrderModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer2', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Speaker',
            slug='speaker',
            price=Decimal('200.00'),
        )
        self.order = Order.objects.create(
            user=self.user,
            first_name='Ada',
            last_name='Lovelace',
            email='ada@example.com',
            address='5 Analytical Way',
            postal_code='560001',
            city='Bangalore',
            phone='9999999999',
            state='Karnataka',
            country='India',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price=Decimal('200.00'), quantity=1)

    def test_cancelable_only_before_shipping(self):
        self.assertTrue(self.order.cancelable)
        self.order.status = Order.Status.PROCESSING
        self.assertTrue(self.order.cancelable)
        self.order.status = Order.Status.SHIPPED
        self.assertFalse(self.order.cancelable)
        self.order.status = Order.Status.DELIVERED
        self.assertFalse(self.order.cancelable)
        self.order.status = Order.Status.CANCELLED
        self.assertFalse(self.order.cancelable)

    def test_tax_calculation(self):
        self.order.shipping_cost = Decimal('50.00')
        self.order.discount = Decimal('30.00')
        self.order.tax_rate = Decimal('0.18')
        self.assertEqual(self.order.get_subtotal(), Decimal('200.00'))
        self.assertEqual(self.order.get_taxable_amount(), Decimal('250.00'))
        self.assertEqual(self.order.get_tax_amount(), Decimal('45.00'))
        self.assertEqual(self.order.get_total_cost(), Decimal('265.00'))

    def test_invoice_totals(self):
        self.order.shipping_cost = Decimal('50.00')
        totals = invoice_totals(self.order)
        self.assertEqual(totals['subtotal'], Decimal('200.00'))
        self.assertEqual(totals['shipping'], Decimal('50.00'))
        self.assertEqual(totals['taxable'], Decimal('250.00'))
        self.assertEqual(totals['tax'], Decimal('45.00'))
        self.assertEqual(totals['total'], Decimal('295.00'))

    def test_invoice_number_format(self):
        self.assertEqual(invoice_number(self.order), f'INV-{self.order.order_number}')

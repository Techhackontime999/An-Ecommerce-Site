from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import SellerProfile
from logistics.models import Shipment
from order.models import Order, OrderItem, Refund
from shop.models import Category, Product

from .models import SellerLedgerEntry, SellerPayout
from .services import (
    available_balance,
    create_payout,
    fail_payout,
    mark_payout_paid,
    reconcile_seller_earnings,
)


class UpdateOrderStatusTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username='buyer', password='pass1234')
        self.seller_user = User.objects.create_user(username='seller', password='pass1234')
        self.profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Seed Store',
            bank_account='00012345',
            phone='9999999999',
            address='1 Market St',
            is_verified=True,
        )
        category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=category, seller=self.profile, name='Pod', slug='pod',
            price='50.00', stock=5,
        )
        self.order = Order.objects.create(
            user=self.buyer, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
        )
        OrderItem.objects.create(order=self.order, product=self.product, price='50.00', quantity=1)
        self.client.force_login(self.seller_user)
        self.url = reverse('seller:update_order_status', args=[self.order.id])

    def test_get_request_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_other_seller_cannot_confirm_order(self):
        other = get_user_model().objects.create_user(username='other', password='pass1234')
        SellerProfile.objects.create(
            user=other, shop_name='Other Shop', bank_account='99999999',
            phone='8888888888', address='2 Other St', is_verified=True,
        )
        self.client.force_login(other)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    @mock.patch('logistics.services.fulfillment.FulfillmentService.create_shipments_for_order', autospec=True)
    def test_confirm_unpaid_order_never_marks_paid_or_fulfils(self, create_shipments):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        create_shipments.assert_not_called()
        self.assertFalse(Shipment.objects.exists())

    @mock.patch('logistics.services.fulfillment.FulfillmentService.create_shipments_for_order', autospec=True)
    def test_confirm_paid_order_starts_fulfilment_and_keeps_paid(self, create_shipments):
        self.order.paid = True
        self.order.save(update_fields=['paid', 'updated'])
        create_shipments.return_value = ['shipment-1']
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        create_shipments.assert_called_once()


class SellerEarningsBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.seller_user = User.objects.create_user(username='earnseller', password='pass1234')
        self.profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Earn Store',
            bank_account='00012345',
            phone='9999999999',
            address='1 Market St',
            is_verified=True,
        )
        self.buyer = User.objects.create_user(username='earnbuyer', password='pass1234')
        category = Category.objects.create(name='Audio', slug='audio-earn')
        self.product = Product.objects.create(
            category=category, seller=self.profile, name='Pod Pro', slug='pod-pro',
            price='200.00', stock=5,
        )
        self.order = Order.objects.create(
            user=self.buyer, first_name='Ada', last_name='Lovelace', email='ada@example.com',
            address='5 Analytical Way', postal_code='560001', city='Bangalore',
            paid=True, status=Order.Status.DELIVERED,
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, price='200.00', quantity=1,
        )


class SellerPayoutServiceTests(SellerEarningsBase):
    def test_reconcile_creates_sale_entry_with_commission(self):
        result = reconcile_seller_earnings()
        self.assertEqual(result['sale'], 1)
        entry = SellerLedgerEntry.objects.get(seller=self.profile, entry_type='sale')
        self.assertEqual(entry.gross_amount, 200)
        self.assertEqual(entry.commission_rate, Decimal('0.1000'))
        self.assertEqual(entry.commission_amount, 20)
        self.assertEqual(entry.net_amount, 180)
        self.assertEqual(entry.status, SellerLedgerEntry.Status.AVAILABLE)

    def test_reconcile_is_idempotent(self):
        reconcile_seller_earnings()
        reconcile_seller_earnings()
        self.assertEqual(SellerLedgerEntry.objects.filter(entry_type='sale').count(), 1)

    def test_reconcile_skips_undelivered_orders(self):
        self.order.status = Order.Status.PROCESSING
        self.order.save(update_fields=['status'])
        reconcile_seller_earnings()
        self.assertEqual(SellerLedgerEntry.objects.count(), 0)

    def test_reconcile_skips_unpaid_orders(self):
        self.order.paid = False
        self.order.save(update_fields=['paid'])
        reconcile_seller_earnings()
        self.assertEqual(SellerLedgerEntry.objects.count(), 0)

    def test_per_seller_commission_override(self):
        self.profile.commission_rate = 0.05
        self.profile.save(update_fields=['commission_rate'])
        reconcile_seller_earnings()
        entry = SellerLedgerEntry.objects.get(entry_type='sale')
        self.assertEqual(entry.commission_amount, 10)
        self.assertEqual(entry.net_amount, 190)

    def test_refund_claws_back_earnings(self):
        reconcile_seller_earnings()
        Refund.objects.create(order=self.order, amount='200.00', status=Refund.Status.COMPLETED)
        reconcile_seller_earnings()
        refund = SellerLedgerEntry.objects.get(seller=self.profile, entry_type='refund')
        self.assertEqual(refund.net_amount, -180)
        self.assertEqual(available_balance(self.profile), 0)

    def test_available_balance_and_create_payout(self):
        reconcile_seller_earnings()
        self.assertEqual(available_balance(self.profile), 180)
        payout, error = create_payout(self.profile, actor=self.seller_user)
        self.assertIsNone(error)
        self.assertEqual(payout.amount, 180)
        self.assertEqual(payout.status, SellerPayout.Status.PROCESSING)
        self.assertEqual(
            SellerLedgerEntry.objects.filter(status=SellerLedgerEntry.Status.PAYOUT_PENDING).count(),
            1,
        )
        self.assertEqual(available_balance(self.profile), 0)

    def test_create_payout_respects_minimum(self):
        self.item.price = '50.00'
        self.item.save(update_fields=['price'])
        reconcile_seller_earnings()
        payout, error = create_payout(self.profile, actor=self.seller_user)
        self.assertIsNone(payout)
        self.assertIn('minimum', error.lower())

    def test_mark_paid_and_fail_flow(self):
        reconcile_seller_earnings()
        payout, _ = create_payout(self.profile, actor=self.seller_user)
        mark_payout_paid(payout, actor=self.seller_user, reference='UTR123')
        payout.refresh_from_db()
        self.assertEqual(payout.status, SellerPayout.Status.PAID)
        self.assertEqual(payout.reference, 'UTR123')
        self.assertEqual(
            SellerLedgerEntry.objects.filter(status=SellerLedgerEntry.Status.PAID).count(), 1,
        )

    def test_fail_payout_releases_funds(self):
        reconcile_seller_earnings()
        payout, _ = create_payout(self.profile, actor=self.seller_user)
        fail_payout(payout, actor=self.seller_user, note='bank rejected')
        payout.refresh_from_db()
        self.assertEqual(payout.status, SellerPayout.Status.FAILED)
        self.assertEqual(available_balance(self.profile), 180)


class SellerPayoutViewTests(SellerEarningsBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.seller_user)

    def test_payouts_page_renders(self):
        reconcile_seller_earnings()
        response = self.client.get(reverse('seller:payouts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '180.00')
        self.assertContains(response, 'Earnings & Payouts')

    def test_request_payout_creates_payout(self):
        reconcile_seller_earnings()
        response = self.client.post(reverse('seller:request_payout'))
        self.assertRedirects(response, reverse('seller:payouts'))
        self.assertTrue(SellerPayout.objects.filter(seller=self.profile).exists())

    def test_unverified_seller_cannot_request_payout(self):
        self.profile.is_verified = False
        self.profile.save(update_fields=['is_verified'])
        response = self.client.get(reverse('seller:payouts'))
        self.assertContains(response, 'not approved')

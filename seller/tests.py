from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import SellerProfile
from logistics.models import Shipment
from order.models import Order, OrderItem
from shop.models import Category, Product


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

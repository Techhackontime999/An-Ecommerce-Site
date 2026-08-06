"""Shared fixtures for LMS tests."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import SellerProfile
from order.models import Order, OrderItem
from shop.models import Category, Product

from logistics.models import (
    CourierCompany,
    CourierService,
    PincodeServiceability,
    Warehouse,
)


class LogisticsTestCase(TestCase):
    """Creates the minimal fixture graph every LMS test needs:
    user → seller → product, an order + order item, a warehouse, two couriers
    (mock + mockexpress) with serviceability for one pincode.
    """

    PINCODE = '824208'

    def setUp(self):
        self.user = User.objects.create_user(
            username='customer', password='test12345', email='customer@example.com'
        )
        self.seller_user = User.objects.create_user(
            username='seller', password='test12345'
        )
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Test Seller',
            bank_account='1234567890',
            phone='9876543210',
            address='1 Test Street, Delhi',
        )
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            category=self.category,
            name='Test Product',
            slug='test-product',
            price=Decimal('999.00'),
            seller=self.seller,
        )

        self.order = Order.objects.create(
            user=self.user,
            first_name='Asha',
            last_name='Kumar',
            email=self.user.email,
            address='22 Gandhi Nagar',
            postal_code=self.PINCODE,
            city='Hazaribag',
            paid=True,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            price=self.product.price,
            quantity=1,
        )

        self.warehouse = Warehouse.objects.create(
            owner_type='seller',
            seller=self.seller,
            name='Test Warehouse',
            code='TST-01',
            address_line1='5 Fulfilment Road',
            city='New Delhi',
            state='Delhi',
            pincode='110001',
            contact_name='Warehouse Ops',
            contact_phone='9812345678',
        )

        self.mock = CourierCompany.objects.create(
            name='Mock Courier',
            code='mock',
            base_charge=Decimal('40.00'),
            per_kg_charge=Decimal('15.00'),
            cod_charge_percent=Decimal('2.00'),
            supports_cod=True,
        )
        self.mex = CourierCompany.objects.create(
            name='Mock Express',
            code='mockexpress',
            base_charge=Decimal('50.00'),
            per_kg_charge=Decimal('10.00'),
            cod_charge_percent=Decimal('1.00'),
            supports_cod=True,
        )
        for courier in (self.mock, self.mex):
            PincodeServiceability.objects.create(
                courier=courier,
                pincode=self.PINCODE,
                zone='urban',
                is_cod_available=True,
                estimated_delivery_days=4,
            )

    def make_cod_order(self, amount=Decimal('5000.00')):
        """A COD order (order.paid=False) so COD surcharges are exercised."""
        order = Order.objects.create(
            user=self.user,
            first_name='Ravi',
            last_name='Sharma',
            email=self.user.email,
            address='7 Market Road',
            postal_code=self.PINCODE,
            city='Hazaribag',
            paid=False,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=amount,
            quantity=1,
        )
        return order

    def mock_shipment(self):
        """A shipment row with a courier + tracking number, ready for labels,
        webhooks or tracking views (no full pipeline needed)."""
        from logistics.models import Shipment
        return Shipment.objects.create(
            order=self.order,
            seller=self.seller,
            warehouse=self.warehouse,
            courier=self.mock,
            tracking_number='MOCK123456789',
            payment_mode='prepaid',
            length_cm='20',
            width_cm='15',
            height_cm='10',
            weight_g='500',
            source_pincode=self.warehouse.pincode,
            destination_pincode=self.PINCODE,
        )

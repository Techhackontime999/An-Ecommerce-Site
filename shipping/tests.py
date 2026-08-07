from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from .models import ShippingAddress, ShippingMethod, Shipment
from .views import address_list, address_create, shipping_select, order_tracking
from order.models import Order, OrderItem
from shop.models import Product, Category


class ShippingURLTests(TestCase):
    def test_address_list_url_resolves(self):
        url = reverse('shipping:address_list')
        self.assertEqual(resolve(url).func, address_list)

    def test_address_create_url_resolves(self):
        url = reverse('shipping:address_create')
        self.assertEqual(resolve(url).func, address_create)

    def test_shipping_select_url_resolves(self):
        url = reverse('shipping:shipping_select', args=[1])
        self.assertEqual(resolve(url).func, shipping_select)

    def test_order_tracking_url_resolves(self):
        url = reverse('shipping:order_tracking', args=[1])
        self.assertEqual(resolve(url).func, order_tracking)


class ShippingMethodModelTests(TestCase):
    def test_create_shipping_method(self):
        method = ShippingMethod.objects.create(
            name='Test Shipping',
            price=10.00,
            estimated_delivery_days='3-5 days',
        )
        self.assertEqual(str(method), 'Test Shipping - \u20b910.00')
        self.assertTrue(method.is_active)

    def test_active_methods_ordering(self):
        ShippingMethod.objects.create(name='Cheap', price=5, estimated_delivery_days='5-7 days')
        ShippingMethod.objects.create(name='Expensive', price=20, estimated_delivery_days='1-2 days')
        methods = ShippingMethod.objects.filter(is_active=True)
        self.assertEqual(methods[0].name, 'Cheap')
        self.assertEqual(methods[1].name, 'Expensive')


class ShippingAddressModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_create_address(self):
        address = ShippingAddress.objects.create(
            user=self.user,
            full_name='Test User',
            address_line1='123 Test St',
            city='Test City',
            state='Test State',
            postal_code='123456',
            phone='1234567890',
        )
        self.assertEqual(str(address), 'Test User - 123 Test St, Test City')

    def test_default_address_ordering(self):
        ShippingAddress.objects.create(user=self.user, full_name='Addr1', address_line1='1 St', city='C', state='S', postal_code='1', phone='1', is_default=False)
        ShippingAddress.objects.create(user=self.user, full_name='Addr2', address_line1='2 St', city='C', state='S', postal_code='2', phone='2', is_default=True)
        addresses = ShippingAddress.objects.filter(user=self.user)
        self.assertEqual(addresses[0].full_name, 'Addr2')


class OrderAddressSelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')
        cat = Category.objects.create(name='Test Cat', slug='test-cat')
        self.product = Product.objects.create(
            name='Test Product', slug='test-product',
            category=cat, price=100,
            description='Test', available=True
        )
        self.order = Order.objects.create(
            user=self.user,
            first_name='John', last_name='Doe',
            email='john@example.com',
            address='123 Order St', postal_code='12345', city='OrderCity'
        )
        self.method = ShippingMethod.objects.create(
            name='Standard', price=10, estimated_delivery_days='3-5 days'
        )

    def test_shipping_select_uses_order_address(self):
        response = self.client.post(reverse('shipping:shipping_select', args=[self.order.id]), {
            'shipping_method': self.method.id,
            'shipping_address': 'order_address',
        })
        self.assertRedirects(response, reverse('payments:checkout', args=[self.order.id]), fetch_redirect_response=False)
        self.order.refresh_from_db()
        self.assertEqual(self.order.shipping_cost, 10)
        self.assertEqual(self.order.shipping_method_name, 'Standard')
        self.assertFalse(Shipment.objects.filter(order=self.order).exists())

    def test_address_create_rejects_external_next(self):
        response = self.client.post(reverse('shipping:address_create'), {
            'full_name': 'John Doe',
            'address_line1': '123 Order St',
            'city': 'OrderCity',
            'state': 'KA',
            'postal_code': '12345',
            'country': 'India',
            'phone': '9999999999',
            'next': 'https://evil.com/phish',
        })
        self.assertRedirects(response, reverse('shipping:address_list'), fetch_redirect_response=False)
        self.assertNotIn('evil.com', response.url)

    def test_address_create_allows_same_host_next(self):
        response = self.client.post(reverse('shipping:address_create'), {
            'full_name': 'John Doe',
            'address_line1': '123 Order St',
            'city': 'OrderCity',
            'state': 'KA',
            'postal_code': '12345',
            'country': 'India',
            'phone': '9999999999',
            'next': '/accounts/profile/',
        })
        self.assertEqual(response.url, '/accounts/profile/')

    def test_order_tracking_view_loads(self):
        ShippingAddress.objects.create(
            user=self.user, full_name='John Doe',
            address_line1='123 Order St', city='OrderCity',
            postal_code='12345', state='', phone=''
        )
        Shipment.objects.create(
            order=self.order,
            shipping_method=self.method,
            status='shipped', tracking_number='TRACK123'
        )
        response = self.client.get(reverse('shipping:order_tracking', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TRACK123')
        self.assertContains(response, 'Shipped')

    def test_order_tracking_no_shipment(self):
        response = self.client.get(reverse('shipping:order_tracking', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No shipment information yet')


class OrderMyOrdersTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

    def test_my_orders_page(self):
        response = self.client.get(reverse('order:my_orders'))
        self.assertEqual(response.status_code, 200)

    def test_my_orders_shows_orders(self):
        cat = Category.objects.create(name='Test Cat', slug='test-cat')
        product = Product.objects.create(
            name='Test Product', slug='test-product',
            category=cat, price=100,
            description='Test', available=True
        )
        order = Order.objects.create(
            user=self.user, first_name='A', last_name='B',
            email='a@b.com', address='Addr', postal_code='1', city='C'
        )
        response = self.client.get(reverse('order:my_orders'))
        self.assertContains(response, f'#{order.id}')

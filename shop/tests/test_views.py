from django.test import TestCase, Client
from django.urls import reverse
from shop.models import Category, Product

class TestViews(TestCase):

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name='fastfood', slug='fastfood1',)
        self.product = Product.objects.create(category=self.category, id=20, name='testproduct', slug='testproduct',
        description='my test product', image='static/core/img/logo.png', price=30)

    def test_product_list_view(self):
        response = self.client.get(reverse('shop:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/product/list.html')

    def test_product_list_by_category_view(self):
        response = self.client.get(reverse('shop:product_list_by_category', kwargs={"category_slug": "fastfood1"}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/product/list.html')

    def test_product_detail_view(self):
        response = self.client.get(reverse('shop:product_detail', kwargs={'id': 20, 'slug': 'testproduct'}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/product/detail.html')
        self.assertContains(response, 'rel="canonical"')

    def test_category_list_has_canonical(self):
        response = self.client.get(reverse('shop:product_list_by_category', kwargs={"category_slug": "fastfood1"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="canonical"')

    def test_product_detail_view_error(self):
        response = self.client.get(reverse('shop:product_detail', kwargs={'id': 21, 'slug': 'nottestproduct'}))
        self.assertEqual(response.status_code, 404)

    def test_sitemap_includes_products_and_categories(self):
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/shop/20/testproduct/')
        self.assertContains(response, '/shop/fastfood1/')

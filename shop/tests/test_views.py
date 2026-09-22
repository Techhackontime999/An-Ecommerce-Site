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

    def test_search_suggestions_returns_products_and_categories(self):
        response = self.client.get(reverse('shop:search_suggestions'), {'q': 'testprod'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['query'], 'testprod')
        self.assertTrue(any(p['name'] == 'testproduct' for p in data['products']))
        product = next(p for p in data['products'] if p['name'] == 'testproduct')
        self.assertIn('/shop/20/testproduct/', product['url'])
        self.assertIn('price', product)

        response = self.client.get(reverse('shop:search_suggestions'), {'q': 'fastfood'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(c['name'] == 'fastfood' for c in data['categories']))

    def test_search_suggestions_empty_query_returns_empty(self):
        response = self.client.get(reverse('shop:search_suggestions'), {'q': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['products'], [])
        self.assertEqual(data['categories'], [])

    def test_search_suggestions_empty_results(self):
        response = self.client.get(reverse('shop:search_suggestions'), {'q': 'zzzzznope'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['products'], [])

    def test_search_suggestions_caps_limit(self):
        response = self.client.get(reverse('shop:search_suggestions'), {'q': 'test', 'limit': '999'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data['products']), 10)

    def test_search_suggest_api_endpoint_returns_json(self):
        response = self.client.get('/api/search/suggest/', {'q': 'testprod'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].startswith('application/json'), True)
        data = response.json()
        self.assertEqual(data['query'], 'testprod')
        self.assertTrue(any(p['name'] == 'testproduct' for p in data['products']))
        self.assertIn('image', data['products'][0])
        self.assertIn('price', data['products'][0])

    def test_navbar_includes_autocomplete_markup(self):
        response = self.client.get(reverse('shop:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-search-autocomplete')
        self.assertContains(response, 'data-search-suggest-url')
        self.assertContains(response, '/api/search/suggest/')

    def test_home_renders_scroll_hero(self):
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-hero-video')
        self.assertContains(response, 'hero-video-suggestions')

    def test_home_renders_scroll_video_hero_when_configured(self):
        from platform_studio.models import SiteSetting
        from platform_studio.utils import invalidate
        for key, value in (('hero_video_light', '/media/hero/light.mp4'),
                           ('hero_video_dark', '/media/hero/dark.mp4')):
            SiteSetting.objects.update_or_create(
                key=key,
                defaults={'label': key, 'value': value, 'group': 'homepage'},
            )
        invalidate()
        try:
            response = self.client.get(reverse('shop:home'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'hero-video-aq--video')
            self.assertContains(response, 'data-hero-video-element')
            self.assertContains(response, '/media/hero/light.mp4')
            self.assertNotContains(response, 'hero-video-aq-stage')
        finally:
            SiteSetting.objects.filter(key__in=('hero_video_light', 'hero_video_dark')).delete()
            invalidate()

    def test_home_renders_default_video_hero_when_settings_empty(self):
        from platform_studio.models import SiteSetting
        from platform_studio.utils import invalidate
        SiteSetting.objects.update_or_create(
            key='hero_video_light',
            defaults={'label': 'hero_video_light', 'value': '', 'group': 'homepage'},
        )
        SiteSetting.objects.update_or_create(
            key='hero_video_dark',
            defaults={'label': 'hero_video_dark', 'value': '', 'group': 'homepage'},
        )
        invalidate()
        try:
            response = self.client.get(reverse('shop:home'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'hero-video-aq--video')
            self.assertContains(response, 'data-hero-video-element')
            self.assertContains(response, 'data-light="/static/hero/light_hero.mp4"')
            self.assertContains(response, 'data-dark="/static/hero/dark_hero.mp4"')
        finally:
            SiteSetting.objects.filter(key__in=('hero_video_light', 'hero_video_dark')).delete()
            invalidate()

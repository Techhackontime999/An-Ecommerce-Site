from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from accounts.models import SellerProfile
from shop.models import Category, Product, ProductVariant


class VariantUIVerification(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username='uiprover', password='x')
        self.profile = SellerProfile.objects.create(
            user=self.user,
            shop_name='UI Probe Shop',
            gst_number='GST9',
            bank_account='9',
            phone='12345',
            address='x',
            is_verified=True,
        )
        self.category = Category.objects.create(name='uicat', slug='uicat')
        self.product = Product.objects.create(
            category=self.category, name='UI Probe', slug='ui-probe',
            price=100, seller=self.profile, available=True,
            description='Main product description',
        )
        self.def_variant = ProductVariant.objects.create(
            product=self.product, name='Default', stock=4,
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.product, name='type-02', stock=3, price=120,
            description='<p>Extra notes for this option.</p>',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_edit_page_default_variant_hides_optional_fields(self):
        r = self.client.get(f'/seller/product/edit/{self.product.id}/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8', errors='replace')
        self.assertNotIn('id_variants-0-price', html)
        self.assertNotIn('id_variants-0-description', html)
        self.assertNotIn('id_variants-0-image', html)
        self.assertNotIn('id_variants-0-gallery_images', html)
        self.assertIn('id_variants-1-price', html)
        self.assertIn('id_variants-1-description', html)
        self.assertIn('id_variants-1-gallery_images', html)
        self.assertIn('sl-variant-note', html)
        self.assertIn('reuses the product', html)

    def test_add_page_first_row_is_default(self):
        r = self.client.get('/seller/product/add/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8', errors='replace')
        self.assertNotIn('id_variants-0-price', html)
        self.assertNotIn('id_variants-0-description', html)
        self.assertIn('id_variants-__prefix__-price', html)
        self.assertIn('id_variants-__prefix__-description', html)

    def test_detail_page_exposes_variant_descriptions(self):
        r = self.client.get(self.product.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8', errors='replace')
        self.assertIn('pdp-variant-descriptions', html)
        self.assertIn('Extra notes for this option', html)
        self.assertIn('pdp-variant-note', html)

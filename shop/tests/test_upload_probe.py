import re
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import SellerProfile
from shop.models import Category, Product, ProductVariant


class GalleryUploadProbe(TestCase):
    def setUp(self):
        U = get_user_model()
        self.user = U.objects.create_user(username='uploader', password='x')
        self.profile = SellerProfile.objects.create(
            user=self.user,
            shop_name='Uploader Shop',
            gst_number='GST123',
            bank_account='123',
            phone='12345',
            address='x',
            is_verified=True,
        )
        self.category = Category.objects.create(name='probe', slug='probe')
        self.product = Product.objects.create(
            category=self.category, name='Probe', slug='probe', price=50, seller=self.profile,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product, name='Default', stock=5,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _edit_page_data(self):
        r = self.client.get(f'/seller/product/edit/{self.product.id}/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8', errors='replace')
        data = {}
        for mm in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
            name, tag = mm.group(1), mm.group(0)
            typ = re.search(r'type="([^"]*)"', tag)
            typ = typ.group(1) if typ else 'text'
            if typ in ('submit', 'button') or name.startswith('csrf'):
                continue
            if 'gallery_images' in name:
                continue
            if typ == 'checkbox':
                if 'checked' in tag and 'DELETE' not in name:
                    data[name] = 'on'
                continue
            val = re.search(r'value="([^"]*)"', tag)
            data[name] = val.group(1) if val else ''
        for mm in re.finditer(r'<select[^>]*name="([^"]+)"', html):
            seg = html[mm.start():mm.start() + 1500]
            opt = re.search(r'<option value="([^"]*)"\s*selected', seg)
            if opt:
                data[mm.group(1)] = opt.group(1)
        for mm in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
            data[mm.group(1)] = mm.group(2)
        return data

    def test_multiple_gallery_upload(self):
        data = self._edit_page_data()
        data['gallery_images'] = [
            SimpleUploadedFile('a1.png', b'\x89PNG\r\n\x1a\n' + b'a' * 100, content_type='image/png'),
            SimpleUploadedFile('a2.png', b'\x89PNG\r\n\x1a\n' + b'b' * 100, content_type='image/png'),
            SimpleUploadedFile('a3.png', b'\x89PNG\r\n\x1a\n' + b'c' * 100, content_type='image/png'),
        ]
        r = self.client.post(f'/seller/product/edit/{self.product.id}/', data)
        self.assertEqual(r.status_code, 302, r.content[:500])
        self.assertEqual(Product.objects.get(id=self.product.id).images.count(), 3)

    def test_variant_gallery_upload(self):
        data = self._edit_page_data()
        data['variants-0-gallery_images'] = [
            SimpleUploadedFile('v1.png', b'\x89PNG\r\n\x1a\n' + b'v' * 100, content_type='image/png'),
        ]
        r = self.client.post(f'/seller/product/edit/{self.product.id}/', data)
        self.assertEqual(r.status_code, 302, r.content[:500])
        self.assertEqual(self.variant.images.count(), 1)

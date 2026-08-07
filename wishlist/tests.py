from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Category, Product

from .models import WishlistItem


class WishlistTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='wisher', password='pass1234')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.product = Product.objects.create(
            category=self.category,
            name='Nimbus Headphones',
            slug='nimbus-headphones',
            price=Decimal('49.99'),
        )
        self.client = Client(SERVER_NAME='localhost')

    def test_detail_requires_login(self):
        response = self.client.get(reverse('wishlist:wishlist_detail'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_toggle_adds_and_removes(self):
        self.client.force_login(self.user)
        url = reverse('wishlist:toggle', args=[self.product.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse('wishlist:wishlist_detail'))
        self.assertTrue(WishlistItem.objects.filter(user=self.user, product=self.product).exists())
        response = self.client.post(url)
        self.assertFalse(WishlistItem.objects.filter(user=self.user, product=self.product).exists())

    def test_duplicate_not_created(self):
        self.client.force_login(self.user)
        url = reverse('wishlist:toggle', args=[self.product.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 0)

    def test_list_shows_items(self):
        WishlistItem.objects.create(user=self.user, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(reverse('wishlist:wishlist_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nimbus Headphones')

    def test_remove(self):
        WishlistItem.objects.create(user=self.user, product=self.product)
        self.client.force_login(self.user)
        response = self.client.post(reverse('wishlist:remove', args=[self.product.pk]))
        self.assertRedirects(response, reverse('wishlist:wishlist_detail'))
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 0)

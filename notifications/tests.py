from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import SellerProfile

from .models import Notification, NotificationPreference
from .services import get_user_role, notify, notify_role


class NotificationBaseTestCase(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username='cust', password='pass1234')
        self.seller_user = User.objects.create_user(username='shop', password='pass1234')
        SellerProfile.objects.create(
            user=self.seller_user,
            shop_name='Test Shop',
            bank_account='12345',
            phone='9999999999',
            address='1 Test St',
        )
        self.admin = User.objects.create_superuser(username='boss', password='pass1234')


class RoleDetectionTests(NotificationBaseTestCase):
    def test_customer_role(self):
        self.assertEqual(get_user_role(self.customer), Notification.Role.CUSTOMER)

    def test_seller_role(self):
        self.assertEqual(get_user_role(self.seller_user), Notification.Role.SELLER)

    def test_admin_role(self):
        self.assertEqual(get_user_role(self.admin), Notification.Role.ADMIN)


class NotifyTests(NotificationBaseTestCase):
    def test_notify_creates_for_recipient(self):
        item = notify(self.customer, Notification.Category.ORDER, 'Order placed', 'Your order is in.')
        self.assertIsNotNone(item)
        self.assertEqual(item.recipient, self.customer)
        self.assertEqual(item.role, Notification.Role.CUSTOMER)
        self.assertFalse(item.is_read)

    def test_notify_respects_disabled_preference(self):
        prefs = NotificationPreference.objects.create(user=self.customer)
        prefs.order_enabled = False
        prefs.save()
        item = notify(self.customer, Notification.Category.ORDER, 'Order placed', 'Hi')
        self.assertIsNone(item)

    def test_notify_still_delivers_other_categories(self):
        NotificationPreference.objects.create(user=self.customer, order_enabled=False)
        item = notify(self.customer, Notification.Category.PAYMENT, 'Paid', 'Thanks')
        self.assertIsNotNone(item)

    def test_notify_none_recipient(self):
        self.assertIsNone(notify(None, Notification.Category.SYSTEM, 'Hi'))


class NotifyRoleTests(NotificationBaseTestCase):
    def test_broadcast_to_sellers_only(self):
        created = notify_role(
            Notification.Role.SELLER,
            Notification.Category.ORDER,
            'New order for your shop',
        )
        recipients = {n.recipient for n in created}
        self.assertIn(self.seller_user, recipients)
        self.assertNotIn(self.customer, recipients)
        self.assertNotIn(self.admin, recipients)

    def test_broadcast_to_customers_only(self):
        created = notify_role(
            Notification.Role.CUSTOMER,
            Notification.Category.PROMO,
            'Big sale',
        )
        recipients = {n.recipient for n in created}
        self.assertIn(self.customer, recipients)
        self.assertNotIn(self.seller_user, recipients)
        self.assertNotIn(self.admin, recipients)

    def test_broadcast_to_admin_only(self):
        created = notify_role(
            Notification.Role.ADMIN,
            Notification.Category.SYSTEM,
            'Maintenance window',
        )
        recipients = {n.recipient for n in created}
        self.assertIn(self.admin, recipients)
        self.assertNotIn(self.customer, recipients)


class NotificationViewTests(NotificationBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username='cust', password='pass1234')
        self.item = notify(self.customer, Notification.Category.ORDER, 'Order placed', 'Hi')
        self.item2 = notify(self.customer, Notification.Category.PAYMENT, 'Payment done', 'Thanks')

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_only_own(self):
        other = User.objects.create_user(username='x', password='pass1234')
        notify(other, Notification.Category.SYSTEM, 'Secret', 'S')
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Order placed')
        self.assertNotContains(response, 'Secret')
        self.assertEqual(len(response.context['notifications']), 2)

    def test_mark_read(self):
        url = reverse('notifications:mark_read', args=[self.item.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Notification.objects.get(pk=self.item.pk).is_read)
        self.assertEqual(response.json()['unread'], 1)

    def test_mark_all_read(self):
        response = self.client.post(reverse('notifications:mark_all_read'))
        self.assertEqual(response.json()['unread'], 0)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)

    def test_delete_notification(self):
        url = reverse('notifications:delete', args=[self.item.pk])
        self.client.post(url)
        self.assertFalse(Notification.objects.filter(pk=self.item.pk).exists())

    def test_cannot_modify_others_notifications(self):
        self.client.login(username='shop', password='pass1234')
        url = reverse('notifications:mark_read', args=[self.item.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Notification.objects.get(pk=self.item.pk).is_read)

    def test_filter_by_category(self):
        response = self.client.get(reverse('notifications:list') + '?category=payment')
        self.assertEqual(len(response.context['notifications']), 1)
        self.assertEqual(response.context['notifications'][0].category, 'payment')

    def test_settings_updates_preferences(self):
        url = reverse('notifications:settings')
        response = self.client.post(url, {
            'order_enabled': 'off',
            'payment_enabled': 'on',
            'shipping_enabled': 'on',
            'deal_enabled': 'on',
            'review_enabled': 'on',
            'account_enabled': 'on',
            'system_enabled': 'on',
            'promo_enabled': 'on',
            'email_enabled': 'on',
        })
        self.assertRedirects(response, url)
        prefs = NotificationPreference.objects.get(user=self.customer)
        self.assertFalse(prefs.order_enabled)
        self.assertTrue(prefs.payment_enabled)
        self.assertTrue(prefs.email_enabled)

    def test_disabled_category_blocks_new_notifications(self):
        prefs = NotificationPreference.objects.create(user=self.customer)
        prefs.order_enabled = False
        prefs.save()
        self.assertIsNone(notify(self.customer, Notification.Category.ORDER, 'Blocked', 'B'))

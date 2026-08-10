from django.core import mail
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from .models import Subscriber
from . import views


class NewsletterDoubleOptInTests(TestCase):
    def setUp(self):
        self.email = 'buyer@example.com'

    def _subscribe(self, email=None):
        return self.client.post(reverse('newsletter:subscribe'), {'email': email or self.email})

    def test_subscribe_does_not_activate_until_confirmed(self):
        response = self._subscribe()
        self.assertEqual(response.status_code, 302)
        sub = Subscriber.objects.get(email=self.email)
        self.assertFalse(sub.is_active)
        self.assertFalse(sub.is_confirmed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('confirm', mail.outbox[0].subject.lower())

    def test_confirm_activates_and_sends_welcome(self):
        self._subscribe()
        token = views._confirm_token(self.email)
        response = self.client.get(reverse('newsletter:confirm', args=[token]))
        self.assertEqual(response.status_code, 200)
        sub = Subscriber.objects.get(email=self.email)
        self.assertTrue(sub.is_active)
        self.assertTrue(sub.is_confirmed)
        self.assertIsNotNone(sub.confirmed_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('welcome', mail.outbox[1].subject.lower())

    def test_confirm_requires_valid_token(self):
        response = self.client.get(reverse('newsletter:confirm', args=['bad-token']))
        self.assertEqual(response.status_code, 400)

    def test_confirm_link_is_idempotent(self):
        self._subscribe()
        token = views._confirm_token(self.email)
        self.client.get(reverse('newsletter:confirm', args=[token]))
        self.client.get(reverse('newsletter:confirm', args=[token]))
        sub = Subscriber.objects.get(email=self.email)
        self.assertTrue(sub.is_active)
        self.assertTrue(sub.is_confirmed)
        self.assertEqual(len(mail.outbox), 2)

    def test_resubscribe_confirmed_subscriber_stays_active(self):
        self._subscribe()
        token = views._confirm_token(self.email)
        self.client.get(reverse('newsletter:confirm', args=[token]))
        mail.outbox.clear()
        self._subscribe()
        sub = Subscriber.objects.get(email=self.email)
        self.assertTrue(sub.is_active)
        self.assertTrue(sub.is_confirmed)
        self.assertEqual(len(mail.outbox), 0)

    def test_unsubscribe_deactivates(self):
        self._subscribe()
        token = views._confirm_token(self.email)
        self.client.get(reverse('newsletter:confirm', args=[token]))
        unsub_token = views._unsubscribe_token(self.email)
        response = self.client.get(reverse('newsletter:unsubscribe', args=[unsub_token]))
        self.assertEqual(response.status_code, 200)
        sub = Subscriber.objects.get(email=self.email)
        self.assertFalse(sub.is_active)

    def test_invalid_email_rejected(self):
        response = self._subscribe(email='not-an-email')
        self.assertEqual(Subscriber.objects.count(), 0)
        self.assertEqual(response.status_code, 302)

    def test_repeat_unconfirmed_subscribe_resends_confirmation(self):
        self._subscribe()
        mail.outbox.clear()
        self._subscribe()
        sub = Subscriber.objects.get(email=self.email)
        self.assertFalse(sub.is_active)
        self.assertFalse(sub.is_confirmed)
        self.assertEqual(len(mail.outbox), 1)

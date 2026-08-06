"""Tests for the public tracking + courier webhook views."""

import hashlib
import hmac
import json

from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from logistics.models import WebhookEvent

from .base import LogisticsTestCase


class TrackingViewTests(LogisticsTestCase):

    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_lookup_by_tracking_number(self):
        shipment = self.mock_shipment()
        url = reverse('logistics:tracking_lookup')
        resp = self.client.get(url, {'q': shipment.tracking_number})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, shipment.shipment_number)

    def test_lookup_unknown_returns_error(self):
        resp = self.client.get(reverse('logistics:tracking_lookup'), {'q': 'NOPE123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No shipment found')

    def test_tracking_detail_page(self):
        shipment = self.mock_shipment()
        url = reverse('logistics:tracking_detail', args=[shipment.shipment_number])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, shipment.get_status_display())


class WebhookViewTests(LogisticsTestCase):

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.shipment = self.mock_shipment()
        self.secret = 'test-secret'
        self.settings_override = self.settings(
            LOGISTICS_WEBHOOK_SECRETS={'mock': self.secret, 'mockexpress': self.secret}
        )
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        super().tearDown()

    def _post(self, payload, signature=''):
        kwargs = {'content_type': 'application/json'}
        if signature:
            kwargs['HTTP_X_LMS_SIGNATURE'] = f'sha256={signature}'
        return self.client.post(
            reverse('logistics:webhook', args=['mock']),
            data=json.dumps(payload),
            **kwargs,
        )

    def _sign(self, body):
        return hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()

    def test_rejects_bad_signature(self):
        resp = self._post({'event_type': 'status'}, signature='deadbeef')
        self.assertEqual(resp.status_code, 401)

    def test_accepts_valid_signature_and_applies_event(self):
        payload = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'out_for_delivery',
            'location': self.PINCODE,
            'description': 'Out for delivery',
            'timestamp': (timezone.now() + timedelta(hours=2)).isoformat(),
        }
        body = json.dumps(payload).encode()
        resp = self._post(payload, signature=self._sign(body))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['added'], 1)

        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'out_for_delivery')
        self.assertTrue(WebhookEvent.objects.filter(processed=True).exists())

    def test_unknown_shipment_returns_404(self):
        payload = {'event_type': 'status', 'tracking_number': 'UNKNOWN-1'}
        body = json.dumps(payload).encode()
        resp = self._post(payload, signature=self._sign(body))
        self.assertEqual(resp.status_code, 404)

    def test_invalid_json_returns_400(self):
        body = b'{"broken'
        kwargs = {'content_type': 'application/json'}
        kwargs['HTTP_X_LMS_SIGNATURE'] = f'sha256={self._sign(body)}'
        resp = self.client.post(reverse('logistics:webhook', args=['mock']), data=body, **kwargs)
        self.assertEqual(resp.status_code, 400)

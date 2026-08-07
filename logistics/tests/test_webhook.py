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

    def test_replay_of_same_payload_is_idempotent(self):
        payload = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'in_transit',
            'timestamp': (timezone.now() + timedelta(hours=1)).isoformat(),
        }
        body = json.dumps(payload).encode()
        first = self._post(payload, signature=self._sign(body))
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['added'], 1)
        event_count = WebhookEvent.objects.count()
        tracking_count = self.shipment.tracking_events.count()

        second = self._post(payload, signature=self._sign(body))
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()['detail'], 'duplicate')
        self.assertEqual(WebhookEvent.objects.count(), event_count)
        self.assertEqual(self.shipment.tracking_events.count(), tracking_count)

    def test_late_newer_event_cannot_regress_timeline(self):
        self.shipment.status = 'order_confirmed'
        self.shipment.save(update_fields=['status'])
        base = timezone.now()

        forward = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'out_for_delivery',
            'timestamp': (base + timedelta(hours=2)).isoformat(),
        }
        body = json.dumps(forward).encode()
        resp = self._post(forward, signature=self._sign(body))
        self.assertEqual(resp.json()['added'], 1)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'out_for_delivery')

        # A stale-but-newer-timestamp 'in_transit' must not regress status.
        stale = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'in_transit',
            'timestamp': (base + timedelta(hours=3)).isoformat(),
        }
        body = json.dumps(stale).encode()
        resp = self._post(stale, signature=self._sign(body))
        self.assertEqual(resp.json()['added'], 1)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'out_for_delivery')

    def test_terminal_status_is_sticky(self):
        base = timezone.now()
        delivered = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'delivered',
            'location': self.PINCODE,
            'description': 'Delivered',
            'timestamp': (base + timedelta(hours=2)).isoformat(),
            'pod_url': 'https://proof.example.com/pod/abc.jpg',
            'received_by': 'Asha Kumar',
        }
        body = json.dumps(delivered).encode()
        resp = self._post(delivered, signature=self._sign(body))
        self.assertEqual(resp.json()['added'], 1)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'delivered')

        # A later 'cancelled' push must not overwrite a delivered shipment.
        cancelled = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'cancelled',
            'timestamp': (base + timedelta(hours=4)).isoformat(),
        }
        body = json.dumps(cancelled).encode()
        resp = self._post(cancelled, signature=self._sign(body))
        self.assertEqual(resp.status_code, 200)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, 'delivered')

    def test_delivery_proof_and_source_recorded(self):
        payload = {
            'event_type': 'status',
            'tracking_number': self.shipment.tracking_number,
            'status': 'delivered',
            'location': self.PINCODE,
            'description': 'Package delivered',
            'timestamp': (timezone.now() + timedelta(hours=2)).isoformat(),
            'pod_url': 'https://proof.example.com/pod/abc.jpg',
            'received_by': 'Asha Kumar',
        }
        body = json.dumps(payload).encode()
        resp = self._post(payload, signature=self._sign(body))
        self.assertEqual(resp.json()['added'], 1)

        event = self.shipment.tracking_events.filter(status='delivered').first()
        self.assertEqual(event.source, 'webhook')
        self.assertEqual(event.pod_url, 'https://proof.example.com/pod/abc.jpg')
        self.assertEqual(event.received_by, 'Asha Kumar')

    def test_poll_events_tagged_as_poll(self):
        from logistics.services.fulfillment import FulfillmentService
        from logistics.constants import ShipmentStatus
        events = [{
            'courier_status': 'In Transit',
            'status': 'in_transit',
            'location': 'Hub',
            'description': 'Moving',
            'timestamp': (timezone.now() + timedelta(hours=1)).isoformat(),
        }]
        FulfillmentService.apply_events(self.shipment, events, source='poll')
        event = self.shipment.tracking_events.filter(status='in_transit').first()
        self.assertEqual(event.source, 'poll')
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, ShipmentStatus.IN_TRANSIT)

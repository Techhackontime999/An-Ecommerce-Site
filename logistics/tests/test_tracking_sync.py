from io import StringIO
from unittest import mock
from django.utils import timezone
from django.core.management import call_command

from logistics.constants import ShipmentStatus
from logistics.models import Shipment, TrackingEvent
from logistics.tests.base import LogisticsTestCase


class SyncTrackingStatusTests(LogisticsTestCase):
    def _run(self, *args):
        out = StringIO()
        call_command('sync_tracking_status', *args, stdout=out)
        return out.getvalue()

    def test_syncs_never_tracked_shipment(self):
        shipment = self.mock_shipment()
        now = timezone.now()
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=now - timezone.timedelta(hours=6),
        )
        output = self._run('--min-age-hours', '1')
        self.assertIn('1/1 shipment(s) updated', output)
        shipment.refresh_from_db()
        self.assertNotEqual(shipment.status, ShipmentStatus.ORDER_CONFIRMED)
        self.assertTrue(TrackingEvent.objects.filter(shipment=shipment).exists())
        self.assertIsNotNone(shipment.last_tracked_at)

    def test_skips_recently_tracked_shipment(self):
        shipment = self.mock_shipment()
        Shipment.objects.filter(pk=shipment.pk).update(
            last_tracked_at=timezone.now(),
        )
        output = self._run('--min-age-hours', '6')
        self.assertIn('0/0 shipment(s) updated', output)

    def test_skips_terminal_shipments(self):
        shipment = self.mock_shipment()
        Shipment.objects.filter(pk=shipment.pk).update(status=ShipmentStatus.DELIVERED)
        output = self._run('--min-age-hours', '0')
        self.assertIn('0/0 shipment(s) updated', output)
        self.assertFalse(TrackingEvent.objects.filter(shipment=shipment).exists())

    def test_limit_caps_number_of_polls(self):
        self.mock_shipment()
        self.mock_shipment(shipment_number='SSD-999999-2')
        now = timezone.now()
        Shipment.objects.all().update(created_at=now - timezone.timedelta(hours=6))
        with mock.patch('logistics.services.fulfillment.FulfillmentService.track') as track:
            track.return_value = []
            output = self._run('--min-age-hours', '0', '--limit', '1')
        self.assertIn('0/1 shipment(s) updated', output)
        self.assertEqual(track.call_count, 1)

    def test_failed_courier_call_does_not_break_command(self):
        shipment = self.mock_shipment()
        now = timezone.now()
        Shipment.objects.filter(pk=shipment.pk).update(
            created_at=now - timezone.timedelta(hours=6),
        )
        with mock.patch(
            'logistics.services.fulfillment.FulfillmentService.track'
        ) as track:
            from logistics.couriers.base import CourierAPIError
            track.side_effect = CourierAPIError('API down')
            output = self._run('--min-age-hours', '0')
        self.assertIn('0/1 shipment(s) updated', output)
        self.assertIn('1 failed', output)
        self.assertFalse(TrackingEvent.objects.filter(shipment=shipment).exists())

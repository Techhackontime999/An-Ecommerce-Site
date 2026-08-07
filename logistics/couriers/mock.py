"""A simulated courier used for development, demos and testing.

The mock courier advances a shipment through the canonical lifecycle based on
how long the shipment has existed, so you can watch tracking without any real
API credentials. It also accepts webhooks so you can exercise the full
pipeline end to end.
"""

import random
from datetime import timedelta

from django.utils import timezone

from .base import BaseCourierAdapter, CourierConfigError
from .registry import register
from .client import CourierClient


def _elapsed_minutes(shipment):
    return (timezone.now() - shipment.created_at).total_seconds() / 60.0


class MockLifecycleMixin:
    """Shared simulated tracking timeline used by both mock couriers."""

    # (max_elapsed_minutes, canonical status, description)
    STAGES = [
        (0, 'picked_up', 'Shipment picked up from seller'),
        (15, 'at_origin_hub', 'Shipment received at origin hub'),
        (45, 'in_transit', 'Shipment in transit to destination'),
        (90, 'at_destination_hub', 'Shipment reached destination hub'),
        (150, 'out_for_delivery', 'Shipment out for delivery'),
    ]

    def simulated_events(self, shipment):
        """Build a realistic event list based on the shipment's age."""
        events = [
            {
                'courier_status': 'Order Confirmed',
                'status': 'order_confirmed',
                'location': '',
                'description': 'Shipment created and handed to courier',
                'timestamp': shipment.created_at,
            }
        ]
        minutes = _elapsed_minutes(shipment)
        for max_min, status, description in self.STAGES:
            if minutes >= max_min:
                events.append({
                    'courier_status': status.replace('_', ' ').title(),
                    'status': status,
                    'location': self.hub_location(shipment, status),
                    'description': description,
                    'timestamp': shipment.created_at + timedelta(minutes=max_min),
                })
        if minutes >= (self.STAGES[-1][0] + 60):
            events.append({
                'courier_status': 'Delivered',
                'status': 'delivered',
                'location': shipment.destination_pincode,
                'description': 'Package delivered to recipient',
                'timestamp': shipment.created_at + timedelta(minutes=self.STAGES[-1][0] + 60),
            })
        return events

    def hub_location(self, shipment, status):
        if status == 'at_origin_hub':
            return shipment.source_pincode or 'Origin City'
        if status == 'at_destination_hub':
            return shipment.destination_pincode or 'Destination City'
        return ''

    def _next_awb(self, shipment, prefix):
        seed = f'{prefix}-{shipment.pk}-{shipment.created_at:%Y%m%d%H%M%S}'
        rng = random.Random(seed)
        digits = ''.join(str(rng.randint(0, 9)) for _ in range(9))
        return f'{prefix}{digits}'

    def _client(self):
        headers = {'Content-Type': 'application/json'}
        if self.courier.api_key:
            headers['Authorization'] = f'Token {self.courier.api_key}'
        return CourierClient(
            self.courier.api_base_url,
            headers=headers,
            courier_code=self.courier.code,
        )


@register
class MockCourierAdapter(MockLifecycleMixin, BaseCourierAdapter):
    code = 'mock'
    display_name = 'Mock Courier (Simulation)'
    capabilities = {
        **BaseCourierAdapter.capabilities,
        'pickup_cancellation': True,
        'reverse_pickup': True,
        'return_shipment': True,
        'cod_remittance': True,
        'manifest_generation': True,
    }

    def create_shipment(self, shipment):
        if shipment.courier is None or not shipment.courier.is_active:
            raise CourierConfigError('Mock courier is not configured or is inactive.')
        if not shipment.courier.sandbox_mode and not shipment.courier.api_base_url:
            raise CourierConfigError('Mock courier requires api_base_url when sandbox_mode is off.')

        tracking = self._next_awb(shipment, 'MOCK')
        # A simulated courier delay is long enough that tracking never
        # pre-empts the AWB assignment.
        shipment.tracking_number = tracking
        shipment.external_shipment_id = f'MOCK-EXT-{shipment.pk}'
        shipment.courier_tracking_url = ''
        return {
            'tracking_number': tracking,
            'external_shipment_id': f'MOCK-EXT-{shipment.pk}',
            'courier_tracking_url': '',
            'pickup_reference': f'MOCKPICK-{shipment.pk}',
            'estimated_delivery_date': (shipment.created_at + timedelta(days=5)).date(),
            'raw': {'simulated': True, 'courier': 'mock'},
        }

    def track(self, shipment):
        return self.simulated_events(shipment)

    def schedule_pickup(self, shipment, scheduled_at=None, slot=''):
        return {
            'reference': f'MOCKPICK-{shipment.pk}',
            'scheduled_at': scheduled_at or timezone.now() + timedelta(hours=4),
            'slot': slot or '10:00-14:00',
            'raw': {'simulated': True},
        }

    def cancel_pickup(self, pickup):
        return {'reference': pickup.reference, 'status': 'cancelled', 'raw': {'simulated': True}}

    def cancel_shipment(self, shipment):
        return {'status': 'cancelled', 'tracking_number': shipment.tracking_number}

    def reverse_pickup(self, shipment, scheduled_at=None):
        return {'reference': f'MOCKRETURN-{shipment.pk}', 'raw': {'simulated': True}}

    def handle_webhook(self, payload):
        if not isinstance(payload, dict):
            return None
        event_type = payload.get('event_type') or payload.get('event')
        if event_type not in ('status', 'tracking'):
            return None
        timestamp = payload.get('timestamp') or timezone.now().isoformat()
        return [{
            'courier_status': payload.get('courier_status', ''),
            'status': self.normalize_status(payload.get('status', '')),
            'location': payload.get('location', ''),
            'description': payload.get('description', ''),
            'timestamp': timestamp,
            'pod_url': payload.get('pod_url', ''),
            'received_by': payload.get('received_by', ''),
        }]


@register
class MockExpressCourierAdapter(MockLifecycleMixin, BaseCourierAdapter):
    """A second simulated courier — faster and cheaper — used to exercise the
    shipping engine's courier *choice* logic."""

    code = 'mockexpress'
    display_name = 'Mock Express (Simulation)'
    capabilities = {
        **BaseCourierAdapter.capabilities,
        'pickup_cancellation': True,
        'reverse_pickup': True,
        'return_shipment': True,
        'cod_remittance': True,
        'manifest_generation': True,
    }

    # Faster simulated delivery stages.
    STAGES = [
        (0, 'picked_up', 'Shipment picked up from seller'),
        (10, 'at_origin_hub', 'Shipment received at origin hub'),
        (30, 'in_transit', 'Shipment in transit to destination'),
        (60, 'at_destination_hub', 'Shipment reached destination hub'),
        (100, 'out_for_delivery', 'Shipment out for delivery'),
    ]

    def create_shipment(self, shipment):
        if shipment.courier is None or not shipment.courier.is_active:
            raise CourierConfigError('Mock Express courier is not configured or is inactive.')
        tracking = self._next_awb(shipment, 'MEX')
        shipment.tracking_number = tracking
        shipment.external_shipment_id = f'MEX-EXT-{shipment.pk}'
        return {
            'tracking_number': tracking,
            'external_shipment_id': f'MEX-EXT-{shipment.pk}',
            'courier_tracking_url': '',
            'pickup_reference': f'MEXPICK-{shipment.pk}',
            'estimated_delivery_date': (shipment.created_at + timedelta(days=2)).date(),
            'raw': {'simulated': True, 'courier': 'mockexpress'},
        }

    def track(self, shipment):
        return self.simulated_events(shipment)

    def schedule_pickup(self, shipment, scheduled_at=None, slot=''):
        return {
            'reference': f'MEXPICK-{shipment.pk}',
            'scheduled_at': scheduled_at or timezone.now() + timedelta(hours=2),
            'slot': slot or '10:00-14:00',
            'raw': {'simulated': True},
        }

    def cancel_pickup(self, pickup):
        return {'reference': pickup.reference, 'status': 'cancelled', 'raw': {'simulated': True}}

    def cancel_shipment(self, shipment):
        return {'status': 'cancelled', 'tracking_number': shipment.tracking_number}

    def reverse_pickup(self, shipment, scheduled_at=None):
        return {'reference': f'MEXRETURN-{shipment.pk}', 'raw': {'simulated': True}}

    def handle_webhook(self, payload):
        if not isinstance(payload, dict):
            return None
        if (payload.get('event_type') or payload.get('event')) not in ('status', 'tracking'):
            return None
        timestamp = payload.get('timestamp') or timezone.now().isoformat()
        return [{
            'courier_status': payload.get('courier_status', ''),
            'status': self.normalize_status(payload.get('status', '')),
            'location': payload.get('location', ''),
            'description': payload.get('description', ''),
            'timestamp': timestamp,
            'pod_url': payload.get('pod_url', ''),
            'received_by': payload.get('received_by', ''),
        }]

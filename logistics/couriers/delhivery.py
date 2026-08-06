"""Delhivery courier adapter.

Implements the publicly documented Delhivery API surface:

- Auth via ``Authorization: Token <api_key>``
- AWB generation:  ``POST {base}/api/p/edit`` (form: ``waybill=<count>``)
- Shipment creation: ``POST {base}/api/cmu/create.json``
- Tracking: ``GET {base}/api/v1/packages/json/?waybill=<awb>``
- Pickup: ``POST {base}/api/pickupexpress/``
- Cancel: ``POST {base}/api/p/edit`` (form: ``waybill=<awb>``)

Missing API credentials raise :class:`CourierConfigError` so the shipment
service can fall back to another courier instead of silently failing.
"""

import logging

from django.utils import timezone
from datetime import datetime

from .base import BaseCourierAdapter, CourierAPIError, CourierConfigError
from .registry import register
from .client import CourierClient

logger = logging.getLogger(__name__)


# Raw Delhivery status strings → canonical statuses. Delhivery statuses come
# as "status" + "status_status" fields inside each package's scans.
DELHIVERY_STATUS_MAP = {
    'UD': 'picked_up',                    # Under Delivery → picked up by hub
    'OFD': 'out_for_delivery',
    'DL': 'delivered',
    'OT': 'in_transit',
    'INT': 'in_transit',
    'RT': 'rto_initiated',
    'RTO': 'rto_initiated',
    'CAN': 'cancelled',
    'NDR': 'customer_unavailable',
    'LST': 'lost',
    'DMG': 'damaged',
    'CONFIRMED': 'order_confirmed',
}


def _parse_iso(value):
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return timezone.now()


@register
class DelhiveryAdapter(BaseCourierAdapter):
    code = 'delhivery'
    display_name = 'Delhivery'
    capabilities = {
        **BaseCourierAdapter.capabilities,
        'pickup_cancellation': True,
        'reverse_pickup': True,
        'return_shipment': True,
        'cod_remittance': True,
        'rate_api': True,
        'serviceability_api': True,
        'manifest_generation': True,
    }

    def _require_config(self):
        if not self.courier.api_base_url or not self.courier.api_key:
            raise CourierConfigError(
                f'Delhivery courier "{self.courier.code}" is missing api_base_url/api_key. '
                'Set them on the CourierCompany row (or the seed command).'
            )

    @property
    def client(self):
        self._require_config()
        return CourierClient(
            self.courier.api_base_url,
            headers={
                'Authorization': f'Token {self.courier.api_key}',
                'Content-Type': 'application/json',
            },
            courier_code=self.courier.code,
        )

    # ------------------------------------------------------------------ awb
    def generate_awbs(self, count=1):
        data = self.client.post(
            '/api/p/edit',
            data={'waybill': str(count)},
            extra_headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        # Delhivery returns {"waybills": ["...", ...]} on success.
        waybills = (data or {}).get('waybills') or []
        if not waybills:
            raise CourierAPIError('Delhivery returned no waybills', payload=data)
        return waybills

    # --------------------------------------------------------- shipments
    def create_shipment(self, shipment):
        self._require_config()
        awbs = self.generate_awbs(1)
        awb = awbs[0]

        line_items = []
        for item in shipment.items.all():
            line_items.append({
                'name': item.product_name,
                'sku': item.sku or item.product_name,
                'units': item.quantity,
                'hsn_code': item.hsn_code or '9999',
                'price': float(item.unit_price),
                'weight': max(float(item.weight_g) / 1000.0, 0.001),
                'amount': float(item.unit_price) * item.quantity,
            })

        order = shipment.order
        payload = {
            'format': 'json',
            'data_delimiter': ',',
            'data': [{
                'shipments': [{
                    'name': f'{order.first_name} {order.last_name}',
                    'add': order.address,
                    'city': order.city,
                    'state': '',
                    'country': 'India',
                    'phone': getattr(order, 'phone', ''),
                    'pin': shipment.destination_pincode,
                    'order': shipment.shipment_number,
                    'payment_mode': 'COD' if shipment.is_cod else 'Prepaid',
                    'cod_amount': float(shipment.cod_amount) if shipment.is_cod else 0,
                    'total_amount': float(shipment.declared_value),
                    'waybill': awb,
                    'pickup_location': shipment.warehouse.code if shipment.warehouse else 'default',
                    'weight': str(max(shipment.chargeable_weight_g / 1000.0, 0.001)),
                    'vol_weight': str(max(shipment.volumetric_weight_g / 1000.0, 0.001)),
                    'length': str(float(shipment.length_cm)),
                    'breadth': str(float(shipment.width_cm)),
                    'height': str(float(shipment.height_cm)),
                    'hazardous': 'yes' if shipment.is_hazardous else 'no',
                    'client': getattr(self.courier, 'extra_config', {}).get('client', ''),
                    'products': line_items or [{'name': shipment.shipment_number, 'units': 1, 'amount': float(shipment.declared_value or 1)}],
                }],
                'pickup_location': {
                    'name': shipment.warehouse.name if shipment.warehouse else 'Shop-Seed',
                    'address': shipment.warehouse.address_line1 if shipment.warehouse else '',
                    'city': shipment.warehouse.city if shipment.warehouse else '',
                    'pin': shipment.warehouse.pincode if shipment.warehouse else '',
                    'phone': shipment.warehouse.contact_phone if shipment.warehouse else '',
                },
            }],
        }

        result = self.client.post('/api/cmu/create.json', json=payload, idempotency_key=f'cmu:{shipment.shipment_number}')
        # {"packages": [{"shipment": ..., "waybill": ..., "status": ...}], "response": [...]}
        packages = (result or {}).get('packages') or []
        if packages and packages[0].get('waybill'):
            shipment.tracking_number = packages[0]['waybill']
            shipment.external_shipment_id = packages[0].get('shipment', '')
            return {
                'tracking_number': packages[0]['waybill'],
                'external_shipment_id': packages[0].get('shipment', ''),
                'courier_tracking_url': '',
                'raw': result,
            }
        raise CourierAPIError('Delhivery shipment creation failed', payload=result)

    def track(self, shipment):
        self._require_config()
        result = self.client.get('/api/v1/packages/json/', params={'waybill': shipment.tracking_number})
        events = []
        data = result or {}
        package_data = data.get('packages') or data.get('ShipmentData') or []
        for package in package_data:
            scans = package.get('scans') or []
            for scan in scans:
                raw_status = scan.get('status', '')
                canonical = self.normalize_status(raw_status)
                events.append({
                    'courier_status': raw_status,
                    'status': canonical,
                    'location': scan.get('location', '') or scan.get('scan', ''),
                    'description': scan.get('remarks', '') or scan.get('status', ''),
                    'timestamp': _parse_iso(scan.get('scan_date')),
                })
        events.sort(key=lambda e: e['timestamp'])
        return events

    def schedule_pickup(self, shipment, scheduled_at=None, slot=''):
        self._require_config()
        result = self.client.post(
            '/api/pickupexpress/',
            json={
                'pickup_time': scheduled_at.isoformat() if scheduled_at else timezone.now().isoformat(),
                'pickup_date': (scheduled_at or timezone.now()).strftime('%Y-%m-%d'),
                'pickup_location': shipment.warehouse.code if shipment.warehouse else 'default',
                'expected_package_count': shipment.items.count() or 1,
            },
        )
        return {'reference': (result or {}).get('response', '') or '', 'raw': result}

    def cancel_shipment(self, shipment):
        self._require_config()
        result = self.client.post(
            '/api/p/edit',
            data={'waybill': shipment.tracking_number},
            extra_headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        return {'status': 'cancelled', 'raw': result}

    def normalize_status(self, raw_status):
        canonical = super().normalize_status(raw_status)
        if canonical:
            return canonical
        code = (raw_status or '').strip().upper()
        return DELHIVERY_STATUS_MAP.get(code)

    def handle_webhook(self, payload):
        """Delhivery push-based tracking posts shipment scan payloads."""
        events = []
        data = payload if isinstance(payload, dict) else {}
        scans = data.get('scans') or data.get('packages') or []
        for scan in scans:
            raw_status = scan.get('status', '')
            events.append({
                'courier_status': raw_status,
                'status': self.normalize_status(raw_status),
                'location': scan.get('location', ''),
                'description': scan.get('remarks', '') or raw_status,
                'timestamp': _parse_iso(scan.get('scan_date')),
            })
        return events or None

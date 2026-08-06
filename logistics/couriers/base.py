from abc import ABC, abstractmethod


class BaseCourierAdapter(ABC):
    """Universal courier abstraction.

    Every courier integration (Delhivery, Blue Dart, FedEx, ...) implements
    this interface. The rest of the platform only ever talks to
    ``CourierCompany.adapter`` — adding a courier never touches business
    logic, only a new adapter + a CourierCompany row.

    Adapters should be *stateless*: they receive the ``CourierCompany`` row
    in ``__init__`` and read credentials from it (or from settings).
    """

    #: Registry key. Must match CourierCompany.code.
    code = 'base'
    #: Human readable name shown in admin/dashboards.
    display_name = 'Base Courier'
    #: Capabilities the adapter implements.
    capabilities = {
        'shipment_creation': True,
        'awb_generation': True,
        'shipping_label': True,
        'pickup_scheduling': True,
        'pickup_cancellation': False,
        'shipment_tracking': True,
        'status_webhooks': True,
        'delivery_confirmation': True,
        'reverse_pickup': False,
        'return_shipment': False,
        'cod_remittance': False,
        'rate_api': False,
        'serviceability_api': False,
        'manifest_generation': False,
    }

    def __init__(self, courier):
        self.courier = courier

    # ------------------------------------------------------------------ core
    @abstractmethod
    def create_shipment(self, shipment):
        """Create a shipment and return a dict::

            {
                'tracking_number': str,
                'external_shipment_id': str,
                'courier_tracking_url': str,
                'pickup_reference': str,   # optional, if pickup auto-books
                'estimated_delivery_date': 'YYYY-MM-DD' or None,
                'raw': dict,
            }

        Must raise ``CourierAPIError`` on failure so the shipment service can
        fall back to another courier.
        """

    @abstractmethod
    def track(self, shipment):
        """Return a list of events ordered oldest → newest::

            [
                {
                    'courier_status': str,
                    'status': canonical status str or None (auto-mapped),
                    'location': str,
                    'description': str,
                    'timestamp': datetime,
                },
            ]

        Implementations may fall back to their own mapping via
        ``self.normalize_status``.
        """

    # ------------------------------------------------------------ optional
    def generate_label(self, shipment):
        """Return (bytes, content_type, filename). The base implementation
        renders the generic local label via ``logistics.services.labels``."""
        from logistics.services.labels import generate_label_pdf
        data = generate_label_pdf(shipment)
        return data, 'application/pdf', f'{shipment.shipment_number}.pdf'

    def cancel_shipment(self, shipment):
        raise CourierAPIError('cancel_shipment is not supported by this courier')

    def schedule_pickup(self, shipment, scheduled_at=None, slot=''):
        """Book a pickup. Return dict with at least ``reference``."""
        raise CourierAPIError('pickup scheduling is not supported by this courier')

    def cancel_pickup(self, pickup):
        raise CourierAPIError('pickup cancellation is not supported by this courier')

    def reverse_pickup(self, shipment, scheduled_at=None):
        """Book a reverse (return) pickup."""
        raise CourierAPIError('reverse pickup is not supported by this courier')

    def manifest(self, shipment_ids):
        """Generate a courier manifest (packet list) for the given shipment ids."""
        from logistics.services.labels import generate_manifest_pdf
        data = generate_manifest_pdf(shipment_ids)
        return data, 'application/pdf', 'manifest.pdf'

    def rate(self, shipment, service=None):
        """Return a rate quote dict. When the courier exposes a rate API,
        override this; the base implementation estimates from CourierCompany
        pricing config."""
        weight = shipment.chargeable_weight_g / 1000.0
        base = float(self.courier.base_charge)
        per_kg = float(self.courier.per_kg_charge)
        cod_charge = 0.0
        if shipment.is_cod and self.courier.supports_cod:
            cod_charge = float(self.courier.cod_charge_percent) / 100.0 * float(shipment.cod_amount)
        total = base + per_kg * weight + cod_charge
        return {
            'base_charge': base,
            'cod_charge': cod_charge,
            'fuel_surcharge': 0.0,
            'total': total,
            'currency': shipment.currency,
            'eta_days': self._eta_days(shipment),
            'raw': {},
        }

    def serviceability(self, pincode):
        """Return serviceability info for a pincode or None."""
        svc = self.courier.serviceability_for(pincode)
        if svc is None:
            return None
        return {
            'pincode': svc.pincode,
            'city': svc.city,
            'state': svc.state,
            'zone': svc.zone,
            'is_cod_available': svc.is_cod_available,
            'max_cod_amount': float(svc.max_cod_amount),
            'estimated_delivery_days': svc.estimated_delivery_days,
        }

    def handle_webhook(self, payload):
        """Given a raw webhook payload from the courier, return tracking data
        in the same shape as ``track`` (list of events) or None if unhandled."""
        return None

    # ---------------------------------------------------------------- utils
    def normalize_status(self, raw_status):
        """Map a courier raw status string to a canonical status. Subclasses
        should extend the default mapping with courier-specific strings."""
        raw = (raw_status or '').strip().lower()
        # Treat underscores and spaces interchangeably so both "out for
        # delivery" and "out_for_delivery" resolve to the same canonical value.
        raw = raw.replace('_', ' ')
        mapping = {
            'order confirmed': 'order_confirmed',
            'confirmed': 'order_confirmed',
            'packed': 'packed',
            'ready for pickup': 'ready_for_pickup',
            'ready for dispatch': 'ready_for_pickup',
            'picked up': 'picked_up',
            'picked': 'picked_up',
            'in transit': 'in_transit',
            'transit': 'in_transit',
            'at origin hub': 'at_origin_hub',
            'origin hub': 'at_origin_hub',
            'at destination hub': 'at_destination_hub',
            'destination hub': 'at_destination_hub',
            'out for delivery': 'out_for_delivery',
            'out for delivery (ofd)': 'out_for_delivery',
            'ofd': 'out_for_delivery',
            'delivered': 'delivered',
            'delivery failed': 'delivery_failed',
            'customer unavailable': 'customer_unavailable',
            'attempted': 'delivery_failed',
            'rto initiated': 'rto_initiated',
            'rto': 'rto_initiated',
            'returned': 'returned',
            'cancelled': 'cancelled',
            'cancel': 'cancelled',
            'lost': 'lost',
            'damaged': 'damaged',
        }
        return mapping.get(raw)

    def _eta_days(self, shipment):
        svc = self.courier.serviceability_for(shipment.destination_pincode)
        if svc and svc.estimated_delivery_days:
            return svc.estimated_delivery_days
        if shipment.service and shipment.service.delivery_sla_days:
            return shipment.service.delivery_sla_days
        return 5

    def _pickup_address_lines(self, shipment):
        if shipment.warehouse:
            return shipment.warehouse.full_address
        if shipment.seller:
            return shipment.seller.address
        return ''

    def _delivery_address_lines(self, shipment):
        order = shipment.order
        return ', '.join(filter(None, [
            order.address,
            f'{order.city} - {order.postal_code}',
        ]))

    def __repr__(self):
        return f'<{self.__class__.__name__} code={self.code}>'


class CourierAPIError(Exception):
    """Raised when a courier API call fails. The shipment service catches this
    to retry and fall back to alternate couriers."""

    def __init__(self, message, *, status_code=None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class CourierConfigError(CourierAPIError):
    """Raised when a courier is missing required configuration (API keys)."""

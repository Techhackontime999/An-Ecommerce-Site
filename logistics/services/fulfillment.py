"""Fulfilment orchestration — the heart of the LMS.

``FulfillmentService`` coordinates every step between an order and a delivered
shipment:

1. Splitting an order into shipments (per warehouse) and snapping order lines
   into ``ShipmentItem`` rows.
2. Running the shipping engine to pick a courier, calling the adapter with
   automatic fallback to the next-best courier on failure.
3. Persisting tracking events into the unified timeline (deduplicated).
4. Scheduling/cancelling pickups.
5. Recording NDRs and driving reverse logistics (returns).

Every mutating step writes an ``AuditLog`` row. Every status change pings the
customer through the notifications app.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from logistics.constants import (
    ShipmentStatus,
    PaymentMode,
    SelectionMethod,
    PickupStatus,
    ReturnStatus,
    ReturnType,
    NdrStatus,
    InspectionDecision,
)
from logistics.models import (
    Shipment,
    ShipmentItem,
    TrackingEvent,
    PickupRequest,
    ShippingRateQuote,
    NDRRecord,
    ReturnShipment,
    AuditLog,
)
from logistics.couriers.base import CourierAPIError, CourierConfigError
from logistics.services.shipping_engine import ShippingEngine, ShippingContext, NoEligibleCourier
from logistics.services.warehouse_engine import WarehouseEngine, WarehouseContext
from logistics.services.labels import attach_label
from logistics.services.notifications import notify_shipment_update, notify_seller

logger = logging.getLogger(__name__)


class FulfillmentError(Exception):
    pass


class ShipmentCreationError(FulfillmentError):
    pass


def _default_item_weight_g():
    return int(getattr(settings, 'LOGISTICS_DEFAULT_ITEM_WEIGHT_G', '500'))


def _item_weight(order_item):
    product = getattr(order_item, 'product', None)
    weight = getattr(product, 'weight_g', None) if product else None
    if weight is None:
        return Decimal(str(_default_item_weight_g()))
    return Decimal(str(weight))


def _payment_mode_for(order):
    """Prepaid when the order is paid; otherwise COD (best effort)."""
    return PaymentMode.PREPAID if order.paid else PaymentMode.COD


def _all_items_delivered(order):
    shipments = order.logistics_shipments.all()
    return bool(shipments) and all(s.status == ShipmentStatus.DELIVERED for s in shipments)


def _any_shipment_active(order):
    return order.logistics_shipments.filter(
        status__in=ShipmentStatus.TIMELINE,
    ).exists()


class FulfillmentService:

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _inventory_fn(warehouse):
        """Default inventory predicate — a warehouse can fulfil anything.

        Swap this out for a real inventory lookup (WMS) when integrated.
        """
        return True

    # -------------------------------------------- order → shipments creation
    @classmethod
    def create_shipments_for_order(cls, order, *, actor=None):
        """Create a shipment (or several, when lines map to multiple
        warehouses) for a fresh order. Runs the whole fulfilment pipeline for
        each shipment."""
        grouped = cls.group_order_items(order)
        created = []
        for warehouse, items in grouped:
            shipment = cls.build_shipment(order, warehouse, items, actor=actor)
            try:
                cls.create_shipment(shipment, actor=actor)
                created.append(shipment)
            except FulfillmentError as exc:
                shipment.error_message = str(exc)
                shipment.save(update_fields=['error_message', 'updated_at'])
                logger.error('Fulfilment failed for %s: %s', shipment.shipment_number, exc)
        return created

    @staticmethod
    def group_order_items(order):
        """Group order lines into (warehouse, [OrderItem, ...]) tuples.

        Without a connected inventory system every line is assigned to the
        single best warehouse via the warehouse engine. With an inventory
        service, replace this to group by each line's owning warehouse.
        """
        items = list(order.items.all())
        if not items:
            return []
        order_item = items[0]
        destination = order.postal_code or ''
        ctx = WarehouseContext(
            destination_pincode=destination,
            inventory_fn=lambda w: True,
            declared_value=Decimal(str(order_item.price or 0)) * order_item.quantity,
        )
        best = WarehouseEngine.select_warehouse(ctx)
        return [(best.warehouse, items)]

    @classmethod
    def build_shipment(cls, order, warehouse, items, *, actor=None):
        """Create the Shipment + ShipmentItem rows for one warehouse split."""
        total_weight = sum(
            (Decimal(str(item.quantity)) * _item_weight(item)) for item in items
        )
        declared_value = sum(
            Decimal(str(item.price)) * item.quantity for item in items
        )
        cod_amount = declared_value if not order.paid else Decimal('0')

        shipment = Shipment(
            order=order,
            seller=getattr(warehouse, 'seller', None),
            warehouse=warehouse,
            payment_mode=_payment_mode_for(order),
            cod_amount=cod_amount,
            declared_value=declared_value,
            destination_pincode=order.postal_code or '',
            source_pincode=warehouse.pincode if warehouse else '',
            weight_g=total_weight,
            currency=getattr(settings, 'LOGISTICS_DEFAULT_CURRENCY', 'INR'),
        )
        # Default dimensions until packing data arrives.
        shipment.length_cm = Decimal('20')
        shipment.width_cm = Decimal('15')
        shipment.height_cm = Decimal('10')
        shipment.save()

        for item in items:
            ShipmentItem.objects.create(
                shipment=shipment,
                order_item=item,
                product=item.product,
                product_name=item.product.name if item.product else f'Item #{item.pk}',
                sku=getattr(item.variant, 'sku', '') if item.variant else '',
                hsn_code='',
                quantity=item.quantity,
                weight_g=_item_weight(item),
                unit_price=item.price,
            )

        AuditLog.log(AuditLog.ACTION_CREATE, 'shipment', shipment.shipment_number,
                     {'warehouse': warehouse.code if warehouse else None, 'items': len(items)}, actor)
        return shipment

    # ------------------------------------------------------- courier creation
    @classmethod
    def create_shipment(cls, shipment, *, force_courier=None, actor=None):
        """Create the shipment at the courier.

        - Builds a shipping context from the shipment snapshot.
        - If ``force_courier`` is given, tries it first.
        - Otherwise the shipping engine ranks couriers and we try each in turn
          (capped by ``LOGISTICS_SHIPMENT_FALLBACK_ATTEMPTS``).
        - On success: persists AWB data, attaches the PDF label, auto-schedules
          a pickup (when enabled) and pulls the first tracking events.
        """
        if shipment.courier_id and shipment.tracking_number:
            # Already created — idempotent return.
            return shipment

        context = cls._context_for(shipment, force_courier)

        attempts = getattr(settings, 'LOGISTICS_SHIPMENT_FALLBACK_ATTEMPTS', 3)
        if force_courier and not shipment.courier_id:
            shipment.courier = force_courier

        if shipment.courier_id:
            ordered_couriers = [shipment.courier]
            decision = {'method': SelectionMethod.MANUAL, 'reasons': ['Courier fixed by caller.']}
        else:
            try:
                ordered_couriers, decision = cls._ranked_couriers(context)
            except NoEligibleCourier:
                cls._ensure_serviceability(shipment)
                ordered_couriers, decision = cls._ranked_couriers(context)
            if not ordered_couriers:
                raise NoEligibleCourier(
                    f'No courier can serve pincode {shipment.destination_pincode}.'
                )

        last_error = ''
        for index, courier in enumerate(ordered_couriers[:attempts]):
            shipment.courier = courier
            shipment.service = None
            try:
                cls._ship_with(shipment, context, decision)
                return shipment
            except (CourierAPIError, CourierConfigError, NoEligibleCourier) as exc:
                last_error = str(exc)
                logger.warning(
                    'Courier %s failed for %s: %s — trying next.', courier.code,
                    shipment.shipment_number, exc,
                )
                shipment.error_message = last_error
                shipment.retry_count += 1
                shipment.save(update_fields=['error_message', 'retry_count', 'updated_at'])
                AuditLog.log(AuditLog.ACTION_ERROR, 'shipment', shipment.shipment_number,
                             {'courier': courier.code, 'error': last_error}, actor)

        raise ShipmentCreationError(
            f'All couriers failed for {shipment.shipment_number}: {last_error}'
        )

    @staticmethod
    def _ensure_serviceability(shipment):
        """Auto-create PincodeServiceability rows for the simulated couriers so
        the pipeline works out of the box for any destination pincode.

        Real couriers (e.g. delhivery) must be enabled deliberately with a
        seeded pincode table; mock couriers are safe to auto-enable because
        they never perform a real shipment."""
        from logistics.models import CourierCompany, PincodeServiceability

        pincode = (shipment.destination_pincode or '').strip()
        if not pincode or not pincode.isdigit():
            return
        for courier in CourierCompany.objects.filter(
            is_active=True, code__in=('mock', 'mockexpress'),
        ):
            PincodeServiceability.objects.get_or_create(
                courier=courier,
                pincode=pincode,
                defaults={
                    'is_active': True,
                    'is_cod_available': True,
                    'estimated_delivery_days': 5,
                },
            )

    @classmethod
    def _ranked_couriers(cls, context):
        """Return (list of CourierCompany ordered best→worst, decision dict)."""
        from logistics.models import CourierCompany

        best, decision = ShippingEngine.select_courier(context)
        ranking = decision.get('ranking') or []
        order = [best.courier]
        seen = {best.courier.pk}
        for row in ranking:
            if row.get('courier') and row['courier'] not in seen:
                courier = CourierCompany.objects.filter(code=row['courier']).first()
                if courier and courier.pk not in seen:
                    order.append(courier)
                    seen.add(courier.pk)
        # Any remaining eligible couriers (fallback safety net).
        for candidate, _svc in ShippingEngine.eligible_couriers(context):
            if candidate.courier.pk not in seen:
                order.append(candidate.courier)
                seen.add(candidate.courier.pk)
        return order, decision

    @classmethod
    def _context_for(cls, shipment, force_courier=None):
        category_id = None
        item = shipment.items.first()
        if item and item.product and item.product.category_id:
            category_id = item.product.category_id
        return ShippingContext(
            destination_pincode=shipment.destination_pincode,
            weight_g=shipment.chargeable_weight_g if shipment.pk else shipment.weight_g,
            payment_mode=shipment.payment_mode,
            cod_amount=shipment.cod_amount,
            declared_value=shipment.declared_value,
            is_hazardous=shipment.is_hazardous,
            delivery_speed=shipment.delivery_speed,
            category_id=category_id,
            source_pincode=shipment.source_pincode,
            force_courier_id=force_courier.pk if force_courier else None,
        )

    @classmethod
    def _ship_with(cls, shipment, context, decision):
        """Persist the courier decision, call the adapter and wire up the
        resulting shipment."""
        adapter = shipment.courier.adapter
        result = adapter.create_shipment(shipment)

        shipment.tracking_number = result.get('tracking_number', shipment.tracking_number)
        shipment.external_shipment_id = result.get('external_shipment_id', '')
        shipment.courier_tracking_url = result.get('courier_tracking_url', '')
        shipment.selected_by = decision.get('method', SelectionMethod.DEFAULT)
        shipment.selection_reason = ' | '.join(decision.get('reasons', []))
        shipment.error_message = ''

        # ETA
        eta_days = result.get('estimated_delivery_date')
        if eta_days:
            try:
                if not isinstance(eta_days, date):
                    from datetime import datetime
                    eta_days = datetime.strptime(str(eta_days)[:10], '%Y-%m-%d').date()
                shipment.estimated_delivery_date = eta_days
            except (ValueError, TypeError):
                shipment.estimated_delivery_date = timezone.localdate() + timedelta(days=5)
        else:
            shipment.estimated_delivery_date = (
                timezone.localdate()
                + timedelta(days=int(getattr(context, 'eta_days', 5) or 5))
            )

        # Quote snapshot
        if result.get('raw') or shipment.courier:
            try:
                quote = adapter.rate(shipment)
                ShippingRateQuote.objects.create(
                    courier=shipment.courier,
                    service=shipment.service,
                    shipment=shipment,
                    base_charge=Decimal(str(quote.get('base_charge', 0))),
                    cod_charge=Decimal(str(quote.get('cod_charge', 0))),
                    fuel_surcharge=Decimal(str(quote.get('fuel_surcharge', 0))),
                    total=Decimal(str(quote.get('total', 0))),
                    currency=quote.get('currency', shipment.currency),
                    eta_days=quote.get('eta_days', 5),
                    raw=quote.get('raw'),
                )
                shipment.courier_charge = Decimal(str(quote.get('total', 0)))
            except Exception as exc:  # quote failure must not break creation
                logger.debug('Rate quote failed for %s: %s', shipment.shipment_number, exc)

        shipment.save()

        # Sync the actual courier charge back onto the order record so the
        # storefront totals reflect what the shipping engine quoted.
        cls._sync_shipping_cost(shipment)

        # Label + initial event + tracking pull.
        cls.set_status(
            shipment, ShipmentStatus.ORDER_CONFIRMED,
            description=f'Shipment created via {shipment.courier.name}',
            location=shipment.source_pincode,
        )
        try:
            attach_label(shipment)
        except Exception as exc:  # pragma: no cover - label failure is non-fatal
            logger.warning('Label attach failed for %s: %s', shipment.shipment_number, exc)

        cls.track(shipment)

        if getattr(settings, 'LOGISTICS_PICKUP_AUTOSCHEDULE', True):
            try:
                cls.schedule_pickup(shipment)
            except Exception as exc:
                logger.warning('Auto pickup failed for %s: %s', shipment.shipment_number, exc)

        AuditLog.log(AuditLog.ACTION_CREATE, 'shipment', shipment.shipment_number,
                     {'courier': shipment.courier.code, 'awb': shipment.tracking_number})
        return shipment

    # ------------------------------------------------------------- tracking
    @classmethod
    def track(cls, shipment, *, persist=True):
        """Pull the latest tracking from the courier and apply it."""
        if not shipment.courier or not shipment.tracking_number:
            return []
        try:
            events = shipment.courier.adapter.track(shipment)
        except (CourierAPIError, CourierConfigError) as exc:
            logger.warning('Tracking pull failed for %s: %s', shipment.shipment_number, exc)
            return []
        if persist:
            cls.apply_events(shipment, events)
        return events

    @classmethod
    def apply_events(cls, shipment, events, *, source='poll'):
        """Store events into the unified timeline (deduplicated) and advance
        the shipment's canonical status.

        ``source`` records where each event came from (webhook push vs. poll).
        Delivery-proof fields (POD URL / recipient name) are captured from the
        event dict when the courier provides them.
        """
        if not events:
            return 0
        known = set(
            TrackingEvent.objects.filter(shipment=shipment)
            .values_list('courier_status', 'status', 'timestamp')
        )
        added = 0
        for event in events:
            timestamp = cls._parse_timestamp(event.get('timestamp'))
            if timestamp is None:
                continue
            status = event.get('status')
            if status not in dict(ShipmentStatus.CHOICES):
                status = ShipmentStatus.ORDER_CONFIRMED
            key = (event.get('courier_status', ''), status, timestamp)
            if key in known:
                continue
            pod_url = ''
            received_by = ''
            if status == ShipmentStatus.DELIVERED:
                pod_url = event.get('pod_url') or event.get('proof_url') or event.get('image_url') or ''
                received_by = (
                    event.get('received_by') or event.get('recipient_name')
                    or event.get('signed_by') or event.get('receiver_name') or ''
                )
            TrackingEvent.objects.create(
                shipment=shipment,
                courier_status=event.get('courier_status', ''),
                status=status,
                location=event.get('location', ''),
                description=event.get('description', ''),
                timestamp=timestamp,
                source=source,
                pod_url=pod_url,
                received_by=received_by,
                raw_payload=event.get('raw') or None,
            )
            known.add(key)
            added += 1

        if added:
            cls._advance_from_events(shipment)
            shipment.last_tracked_at = timezone.now()
            shipment.save(update_fields=['last_tracked_at', 'updated_at'])
        return added

    @classmethod
    def _parse_timestamp(cls, value):
        """Coerce a courier timestamp (datetime, ISO string, epoch) to an
        aware datetime. Returns None when unparseable."""
        if value is None:
            return None
        if isinstance(value, datetime):
            if timezone.is_naive(value):
                return timezone.make_aware(value)
            return value
        if isinstance(value, (int, float)):
            return timezone.datetime.fromtimestamp(value, tz=timezone.utc)
        parsed = parse_datetime(str(value))
        if parsed is None:
            parsed = parse_date(str(value))
            if parsed is not None:
                return timezone.make_aware(
                    timezone.datetime(parsed.year, parsed.month, parsed.day)
                )
            return None
        return parsed

    @classmethod
    def _advance_from_events(cls, shipment):
        latest = shipment.tracking_events.order_by('-timestamp', '-id').first()
        if latest is None:
            return
        cls.set_status(
            shipment, latest.status, notify=False,
            source=latest.source, pod_url=latest.pod_url, received_by=latest.received_by,
        )

    # ------------------------------------------------------------ transitions
    @staticmethod
    def _transition_allowed(current, new):
        """Monotonicity guard for the canonical shipment status.

        - A terminal status (delivered / returned / cancelled / lost / damaged)
          is sticky and can never be overwritten by a late event.
        - Timeline statuses may only move forward (no out_for_delivery → in
          transit regressions), even if a *newer* event arrives out of order.
        - Exception statuses (delivery_failed, rto_initiated, ...) sit outside
          the timeline, so re-attempts back into the timeline always pass.
        """
        if current == new:
            return True
        if ShipmentStatus.is_terminal(current):
            return False
        current_idx = ShipmentStatus.timeline_index(current)
        new_idx = ShipmentStatus.timeline_index(new)
        if current_idx >= 0 and new_idx >= 0 and new_idx < current_idx:
            return False
        return True

    @classmethod
    def set_status(cls, shipment, status, *, description='', location='',
                   timestamp=None, actor=None, notify=True, raw_payload=None,
                   source='system', pod_url='', received_by=''):
        """Advance a shipment to a canonical status, write the event, keep
        timestamps consistent and sync the order + notifications."""
        if status == shipment.status and shipment.tracking_events.filter(status=status).exists():
            return shipment
        if not cls._transition_allowed(shipment.status, status):
            logger.warning(
                'Refusing shipment %s status %s → %s (monotonicity guard).',
                shipment.shipment_number, shipment.status, status,
            )
            return shipment

        old = shipment.status
        now = timestamp or timezone.now()

        # Clear is_current on previous events.
        shipment.tracking_events.filter(is_current=True).update(is_current=False)

        TrackingEvent.objects.create(
            shipment=shipment,
            status=status,
            location=location or '',
            description=description,
            timestamp=now,
            source=source,
            pod_url=pod_url,
            received_by=received_by,
            is_current=True,
            raw_payload=raw_payload,
        )

        shipment.status = status
        if status == ShipmentStatus.PICKED_UP and not shipment.picked_up_at:
            shipment.picked_up_at = now
        if status == ShipmentStatus.DELIVERED and not shipment.delivered_at:
            shipment.delivered_at = now
        if status == ShipmentStatus.READY_FOR_PICKUP and shipment.pickup_requests.exists():
            shipment.pickup_requests.filter(status=PickupStatus.REQUESTED).update(status=PickupStatus.SCHEDULED)

        shipment.save(update_fields=['status', 'picked_up_at', 'delivered_at', 'updated_at'])

        AuditLog.log(AuditLog.ACTION_STATUS, 'shipment', shipment.shipment_number,
                     {'from': old, 'to': status, 'description': description}, actor)

        if notify:
            notify_shipment_update(shipment, description)

        cls._sync_order(shipment)
        return shipment

    @classmethod
    def _sync_shipping_cost(cls, shipment):
        """Copy the charged courier cost to the order's shipping_cost field."""
        order = shipment.order
        if order is None or not shipment.courier_charge:
            return
        order.shipping_cost = Decimal(str(shipment.courier_charge))
        order.shipping_method_name = shipment.courier.name
        if shipment.service:
            order.shipping_method_name += f' · {shipment.service.name}'
        order.save(update_fields=['shipping_cost', 'shipping_method_name', 'updated'])

    @classmethod
    def _sync_order(cls, shipment):
        """Mirror a shipment milestone onto the order via the validated state
        machine. Illegal transitions (e.g. a late delivery webhook on a
        cancelled order) are rejected and logged instead of resurrecting the
        order."""
        from order.state import set_order_status
        order = shipment.order
        if order is None:
            return
        target = None
        if shipment.status == ShipmentStatus.PICKED_UP and order.status == order.Status.PROCESSING:
            target = order.Status.SHIPPED
        elif shipment.status == ShipmentStatus.DELIVERED:
            if _all_items_delivered(order):
                target = order.Status.DELIVERED
        elif shipment.status == ShipmentStatus.CANCELLED:
            target = order.Status.CANCELLED
        if target is not None:
            ok, _reason = set_order_status(
                order, target, actor=None,
                note=f'Shipment {shipment.shipment_number} → {shipment.status}',
            )
            if not ok:
                logger.warning(
                    'Order %s sync skipped: %s', order.id, _reason,
                )
        cls._sync_legacy_shipment(shipment)

    @classmethod
    def _sync_legacy_shipment(cls, shipment):
        """Mirror the LMS status onto the legacy shipping.Shipment (if one
        exists for historical orders) so the older tracking UI and admin
        dashboard stay consistent."""
        order = shipment.order
        if order is None:
            return
        legacy = getattr(order, 'shipment', None)
        if legacy is None:
            return
        mapping = {
            ShipmentStatus.ORDER_CONFIRMED: 'pending',
            ShipmentStatus.PACKED: 'pending',
            ShipmentStatus.READY_FOR_PICKUP: 'pending',
            ShipmentStatus.PICKED_UP: 'shipped',
            ShipmentStatus.AT_ORIGIN_HUB: 'in_transit',
            ShipmentStatus.IN_TRANSIT: 'in_transit',
            ShipmentStatus.AT_DESTINATION_HUB: 'in_transit',
            ShipmentStatus.OUT_FOR_DELIVERY: 'in_transit',
            ShipmentStatus.DELIVERED: 'delivered',
            ShipmentStatus.DELIVERY_FAILED: 'failed',
            ShipmentStatus.CUSTOMER_UNAVAILABLE: 'failed',
            ShipmentStatus.CANCELLED: 'failed',
            ShipmentStatus.RETURNED: 'failed',
            ShipmentStatus.RTO_INITIATED: 'failed',
            ShipmentStatus.LOST: 'failed',
            ShipmentStatus.DAMAGED: 'failed',
        }
        fields = []
        legacy_status = mapping.get(shipment.status)
        if legacy_status and legacy.status != legacy_status:
            legacy.status = legacy_status
            fields.append('status')
        if shipment.tracking_number and legacy.tracking_number != shipment.tracking_number:
            legacy.tracking_number = shipment.tracking_number
            fields.append('tracking_number')
        if fields:
            legacy.save(update_fields=fields + ['updated_at'])

    # --------------------------------------------------------------- pickups
    @classmethod
    def schedule_pickup(cls, shipment, *, scheduled_at=None, slot='', actor=None):
        """Create a PickupRequest and book it with the courier."""
        if shipment.pickup_requests.filter(status__in=(
            PickupStatus.REQUESTED, PickupStatus.SCHEDULED, PickupStatus.CONFIRMED,
        )).exists():
            return shipment.pickup_requests.filter(status__in=(
                PickupStatus.REQUESTED, PickupStatus.SCHEDULED, PickupStatus.CONFIRMED,
            )).first()

        pickup = PickupRequest.objects.create(
            shipment=shipment,
            courier=shipment.courier,
            scheduled_at=scheduled_at,
            slot=slot,
        )
        if not shipment.courier:
            return pickup

        try:
            result = shipment.courier.adapter.schedule_pickup(shipment, scheduled_at, slot)
            pickup.reference = result.get('reference', pickup.reference)
            pickup.scheduled_at = result.get('scheduled_at') or pickup.scheduled_at
            pickup.slot = result.get('slot') or slot
            pickup.status = PickupStatus.CONFIRMED
            pickup.save()
            cls.set_status(shipment, ShipmentStatus.READY_FOR_PICKUP,
                           description=f'Pickup booked with {shipment.courier.name}')
        except (CourierAPIError, CourierConfigError) as exc:
            pickup.status = PickupStatus.FAILED
            pickup.error_message = str(exc)
            pickup.save()
            cls.set_status(shipment, ShipmentStatus.READY_FOR_PICKUP,
                           description='Pickup booked (manual confirmation pending)')
            logger.warning('Pickup booking failed for %s: %s', shipment.shipment_number, exc)

        AuditLog.log(AuditLog.ACTION_PICKUP, 'pickup', pickup.pk,
                     {'status': pickup.status, 'reference': pickup.reference}, actor)
        return pickup

    @classmethod
    def cancel_pickup(cls, pickup, *, actor=None):
        if pickup.courier:
            try:
                pickup.courier.adapter.cancel_pickup(pickup)
            except (CourierAPIError, CourierConfigError) as exc:
                pickup.error_message = str(exc)
        pickup.status = PickupStatus.CANCELLED
        pickup.save()
        AuditLog.log(AuditLog.ACTION_PICKUP, 'pickup', pickup.pk,
                     {'status': 'cancelled'}, actor)
        return pickup

    @classmethod
    def mark_picked_up(cls, shipment, *, actor=None):
        cls.set_status(shipment, ShipmentStatus.PICKED_UP,
                       description='Package picked up by courier', actor=actor)
        cls.track(shipment)
        return shipment

    # ------------------------------------------------------------ exceptions
    @classmethod
    def cancel_shipment(cls, shipment, *, reason='', actor=None):
        """Cancel a shipment at the courier (if already created) and set the
        canonical status. Called from the cancellation flow at any stage."""
        if shipment.is_terminal:
            return shipment
        if shipment.courier and shipment.tracking_number:
            try:
                shipment.courier.adapter.cancel_shipment(shipment)
            except (CourierAPIError, CourierConfigError) as exc:
                logger.warning('Courier cancel failed for %s: %s', shipment.shipment_number, exc)
        cls.set_status(shipment, ShipmentStatus.CANCELLED,
                       description=reason or 'Shipment cancelled', actor=actor)
        return shipment

    @classmethod
    def record_ndr(cls, shipment, *, reason, remarks='', actor=None):
        """Record a Non-Delivery Report for a failed delivery."""
        cls.set_status(shipment, ShipmentStatus.DELIVERY_FAILED,
                       description=f'NDR: {remarks or reason}', actor=actor)
        record = NDRRecord.objects.create(
            shipment=shipment,
            reason=reason,
            courier_remarks=remarks,
        )
        AuditLog.log(AuditLog.ACTION_MANUAL, 'ndr', record.pk,
                     {'reason': reason, 'remarks': remarks}, actor)
        return record

    # -------------------------------------------------------- reverse logistics
    @classmethod
    def create_return(cls, original_shipment, *, return_type=ReturnType.REFUND,
                      reason='', notes='', return_request=None, actor=None):
        """Create a reverse shipment for a customer return."""
        ret = ReturnShipment.objects.create(
            original_shipment=original_shipment,
            order=original_shipment.order,
            return_request=return_request,
            return_type=return_type,
            reason=reason,
            customer_notes=notes,
            courier=original_shipment.courier,
            pickup_address=original_shipment.order.address,
        )
        AuditLog.log(AuditLog.ACTION_CREATE, 'return', ret.return_number,
                     {'return_type': return_type, 'reason': reason}, actor)
        return ret

    @classmethod
    def approve_return(cls, return_shipment, *, actor=None, reschedule=True):
        return_shipment.status = ReturnStatus.APPROVED
        return_shipment.save(update_fields=['status', 'updated_at'])
        AuditLog.log(AuditLog.ACTION_MANUAL, 'return', return_shipment.return_number,
                     {'status': ReturnStatus.APPROVED}, actor)
        if reschedule:
            cls.schedule_return_pickup(return_shipment)
        return return_shipment

    @classmethod
    def schedule_return_pickup(cls, return_shipment, *, scheduled_at=None, slot='', actor=None):
        return_shipment.status = ReturnStatus.PICKUP_SCHEDULED
        return_shipment.pickup_scheduled_at = scheduled_at or (timezone.now() + timedelta(days=1))
        return_shipment.save(update_fields=['status', 'pickup_scheduled_at', 'updated_at'])

        if return_shipment.courier and return_shipment.original_shipment:
            try:
                result = return_shipment.courier.adapter.reverse_pickup(
                    return_shipment.original_shipment, scheduled_at,
                )
                return_shipment.pickup_reference = result.get('reference', '')
                return_shipment.tracking_number = result.get('tracking_number', '')
                return_shipment.save(update_fields=['pickup_reference', 'tracking_number', 'updated_at'])
            except (CourierAPIError, CourierConfigError) as exc:
                return_shipment.error_message = str(exc)
                return_shipment.save(update_fields=['error_message', 'updated_at'])
                logger.warning('Reverse pickup failed for %s: %s', return_shipment.return_number, exc)

        AuditLog.log(AuditLog.ACTION_PICKUP, 'return', return_shipment.return_number,
                     {'status': ReturnStatus.PICKUP_SCHEDULED}, actor)
        return return_shipment

    @classmethod
    def mark_return_picked_up(cls, return_shipment, *, actor=None):
        return_shipment.status = ReturnStatus.PICKED_UP
        return_shipment.save(update_fields=['status', 'updated_at'])
        AuditLog.log(AuditLog.ACTION_STATUS, 'return', return_shipment.return_number,
                     {'to': ReturnStatus.PICKED_UP}, actor)
        return return_shipment

    @classmethod
    def inspect_return(cls, return_shipment, *, decision, notes='', actor=None):
        """Record the outcome of warehouse inspection."""
        valid = dict(InspectionDecision.CHOICES)
        if decision not in valid:
            raise FulfillmentError(f'Unknown inspection decision: {decision}')
        return_shipment.inspection_decision = decision
        return_shipment.inspection_notes = notes
        return_shipment.inspected_by = actor
        return_shipment.inspected_at = timezone.now()
        if decision == InspectionDecision.OK:
            return_shipment.status = ReturnStatus.INSPECTING
        else:
            return_shipment.status = ReturnStatus.DAMAGED if decision == InspectionDecision.DAMAGED else ReturnStatus.INSPECTING
        return_shipment.save()
        AuditLog.log(AuditLog.ACTION_MANUAL, 'return', return_shipment.return_number,
                     {'decision': decision, 'notes': notes}, actor)
        return return_shipment

    @classmethod
    def restock_return(cls, return_shipment, *, warehouse=None, actor=None):
        """Restock the returned items into a warehouse."""
        if return_shipment.inspection_decision not in (InspectionDecision.OK, ''):
            raise FulfillmentError('Only "good" returns can be restocked.')
        return_shipment.restock_warehouse = warehouse or return_shipment.original_shipment.warehouse
        return_shipment.status = ReturnStatus.RESTOCKED
        return_shipment.restocked_at = timezone.now()
        return_shipment.save()
        AuditLog.log(AuditLog.ACTION_MANUAL, 'return', return_shipment.return_number,
                     {'status': ReturnStatus.RESTOCKED}, actor)
        return return_shipment

    @classmethod
    def complete_return_refund(cls, return_shipment, *, amount, actor=None):
        """Mark a refund as issued for a return."""
        return_shipment.refund_amount = Decimal(str(amount))
        return_shipment.refunded_at = timezone.now()
        return_shipment.status = ReturnStatus.REFUNDED
        return_shipment.save()
        AuditLog.log(AuditLog.ACTION_MANUAL, 'return', return_shipment.return_number,
                     {'amount': str(amount)}, actor)
        return return_shipment

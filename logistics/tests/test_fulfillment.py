"""Tests for the fulfilment pipeline (shipment creation, tracking, NDR, returns)."""

from decimal import Decimal

from django.utils import timezone
from datetime import timedelta

from logistics.constants import (
    ShipmentStatus,
    NdrStatus,
    ReturnStatus,
    PickupStatus,
)
from logistics.models import (
    NDRRecord,
    PickupRequest,
    ReturnShipment,
    Shipment,
    ShipmentItem,
    TrackingEvent,
)
from logistics.services.fulfillment import FulfillmentService, ShipmentCreationError

from .base import LogisticsTestCase


class ShipmentCreationTests(LogisticsTestCase):

    def test_creates_shipment_with_courier_and_items(self):
        shipments = FulfillmentService.create_shipments_for_order(self.order)
        self.assertEqual(len(shipments), 1)
        shipment = shipments[0]
        self.assertIn(shipment.courier.code, {'mock', 'mockexpress'})
        self.assertTrue(shipment.tracking_number.startswith(('MOCK', 'MEX')))
        self.assertEqual(shipment.items.count(), 1)
        self.assertEqual(
            shipment.items.first().product_name, 'Test Product'
        )
        self.assertEqual(shipment.selected_by, 'engine')

    def test_shipment_populates_route_and_charges(self):
        shipment = FulfillmentService.create_shipments_for_order(self.order)[0]
        self.assertEqual(shipment.destination_pincode, self.PINCODE)
        self.assertEqual(shipment.warehouse_id, self.warehouse.pk)
        self.assertGreater(shipment.courier_charge, 0)
        self.assertIsNotNone(shipment.estimated_delivery_date)
        self.assertEqual(shipment.payment_mode, 'prepaid')  # order is paid

    def test_cod_shipment_is_cod(self):
        order = self.make_cod_order(Decimal('2000.00'))
        shipment = FulfillmentService.create_shipments_for_order(order)[0]
        self.assertTrue(shipment.is_cod)
        self.assertEqual(shipment.cod_amount, Decimal('2000.00'))

    def test_status_flow_and_tracking_events(self):
        shipment = FulfillmentService.create_shipments_for_order(self.order)[0]
        FulfillmentService.schedule_pickup(shipment)
        self.assertTrue(shipment.tracking_events.exists())
        self.assertIn(
            shipment.status,
            ShipmentStatus.TIMELINE,
        )


class TrackingTests(LogisticsTestCase):

    def test_track_applies_events_and_advances_status(self):
        shipment = self.mock_shipment()
        before = shipment.tracking_events.count()
        FulfillmentService.track(shipment)
        shipment.refresh_from_db()
        self.assertGreater(shipment.tracking_events.count(), before)

    def test_apply_events_is_idempotent(self):
        shipment = self.mock_shipment()
        events = shipment.courier.adapter.track(shipment)
        first = FulfillmentService.apply_events(shipment, events)
        second = FulfillmentService.apply_events(shipment, events)
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)

    def test_webhook_style_events_advance_status(self):
        shipment = FulfillmentService.create_shipments_for_order(self.order)[0]
        events = [{
            'courier_status': 'OFD',
            'status': 'out_for_delivery',
            'location': self.PINCODE,
            'description': 'Out for delivery',
            'timestamp': timezone.now() + timedelta(hours=2),
        }]
        FulfillmentService.apply_events(shipment, events)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.OUT_FOR_DELIVERY)


class NdrAndReturnTests(LogisticsTestCase):

    def setUp(self):
        super().setUp()
        self.shipment = FulfillmentService.create_shipments_for_order(self.order)[0]

    def test_record_ndr_creates_open_record(self):
        ndr = FulfillmentService.record_ndr(
            self.shipment, reason='customer_unreachable', remarks='2 attempts'
        )
        self.assertEqual(ndr.status, NdrStatus.OPEN)
        self.assertTrue(self.shipment.ndr_records.filter(pk=ndr.pk).exists())

    def test_return_full_cycle(self):
        ndr_reason = 'wrong_item'
        ret = FulfillmentService.create_return(
            self.shipment, reason=ndr_reason, notes='Size mismatch'
        )
        self.assertEqual(ret.status, ReturnStatus.REQUESTED)

        FulfillmentService.approve_return(ret, reschedule=False)
        self.assertEqual(ret.status, ReturnStatus.APPROVED)

        FulfillmentService.schedule_return_pickup(ret)
        self.assertEqual(ret.status, ReturnStatus.PICKUP_SCHEDULED)
        self.assertTrue(ret.pickup_reference)

        FulfillmentService.mark_return_picked_up(ret)
        self.assertEqual(ret.status, ReturnStatus.PICKED_UP)

        FulfillmentService.inspect_return(
            ret, decision='ok', notes='Box intact', actor=self.seller_user
        )
        FulfillmentService.restock_return(ret)
        self.assertEqual(ret.status, ReturnStatus.RESTOCKED)
        self.assertEqual(ret.restock_warehouse_id, self.warehouse.pk)

        FulfillmentService.complete_return_refund(ret, amount=Decimal('499.00'))
        self.assertEqual(ret.status, ReturnStatus.REFUNDED)
        self.assertEqual(ret.refund_amount, Decimal('499.00'))

    def test_pickup_scheduling(self):
        pickup = FulfillmentService.schedule_pickup(self.shipment)
        self.assertIsInstance(pickup, PickupRequest)
        self.assertEqual(pickup.status, PickupStatus.CONFIRMED)
        self.assertTrue(pickup.reference)

    def test_cancel_shipment_marks_cancelled(self):
        FulfillmentService.cancel_shipment(self.shipment, reason='ops decision')
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, ShipmentStatus.CANCELLED)


class CodDeliveryTests(LogisticsTestCase):
    """A delivered COD shipment is when the platform collects the cash."""

    def setUp(self):
        super().setUp()
        self.product.stock = 10
        self.product.save()

    def test_delivered_cod_shipment_records_cash_collection(self):
        order = self.make_cod_order(Decimal('2000.00'))
        shipment = FulfillmentService.create_shipments_for_order(order)[0]
        self.assertTrue(shipment.is_cod)
        FulfillmentService.set_status(shipment, ShipmentStatus.DELIVERED)
        shipment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(shipment.status, ShipmentStatus.DELIVERED)
        self.assertTrue(order.paid)
        from payments.models import Payment
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, 'captured')
        self.assertEqual(payment.amount, Decimal('2000.00'))
        self.assertEqual(payment.razorpay_order_id, f'cod-{shipment.shipment_number}')

    def test_delivered_prepaid_shipment_does_not_collect_cash(self):
        shipment = FulfillmentService.create_shipments_for_order(self.order)[0]
        self.assertFalse(shipment.is_cod)
        FulfillmentService.set_status(shipment, ShipmentStatus.DELIVERED)
        from payments.models import Payment
        self.assertFalse(Payment.objects.filter(order=self.order).exists())

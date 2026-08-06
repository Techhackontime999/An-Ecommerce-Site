"""Canonical vocabulary shared across the LMS.

Courier adapters map their own raw statuses into these canonical values so the
entire platform (customer UI, analytics, dashboards) speaks one language.
"""


class ShipmentStatus:
    ORDER_CONFIRMED = 'order_confirmed'
    PACKED = 'packed'
    READY_FOR_PICKUP = 'ready_for_pickup'
    PICKED_UP = 'picked_up'
    IN_TRANSIT = 'in_transit'
    AT_ORIGIN_HUB = 'at_origin_hub'
    AT_DESTINATION_HUB = 'at_destination_hub'
    OUT_FOR_DELIVERY = 'out_for_delivery'
    DELIVERED = 'delivered'
    DELIVERY_FAILED = 'delivery_failed'
    CUSTOMER_UNAVAILABLE = 'customer_unavailable'
    RTO_INITIATED = 'rto_initiated'
    RETURNED = 'returned'
    CANCELLED = 'cancelled'
    LOST = 'lost'
    DAMAGED = 'damaged'

    CHOICES = [
        (ORDER_CONFIRMED, 'Order Confirmed'),
        (PACKED, 'Packed'),
        (READY_FOR_PICKUP, 'Ready For Pickup'),
        (PICKED_UP, 'Picked Up'),
        (IN_TRANSIT, 'In Transit'),
        (AT_ORIGIN_HUB, 'At Origin Hub'),
        (AT_DESTINATION_HUB, 'At Destination Hub'),
        (OUT_FOR_DELIVERY, 'Out For Delivery'),
        (DELIVERED, 'Delivered'),
        (DELIVERY_FAILED, 'Delivery Failed'),
        (CUSTOMER_UNAVAILABLE, 'Customer Unavailable'),
        (RTO_INITIATED, 'RTO Initiated'),
        (RETURNED, 'Returned'),
        (CANCELLED, 'Cancelled'),
        (LOST, 'Lost'),
        (DAMAGED, 'Damaged'),
    ]

    # Ordered timeline shown to customers. Anything not in this list is
    # rendered as a terminal/exception state.
    TIMELINE = [
        ORDER_CONFIRMED,
        PACKED,
        READY_FOR_PICKUP,
        PICKED_UP,
        AT_ORIGIN_HUB,
        IN_TRANSIT,
        AT_DESTINATION_HUB,
        OUT_FOR_DELIVERY,
        DELIVERED,
    ]

    LABELS = dict(CHOICES)

    @classmethod
    def is_terminal(cls, status):
        return status in {cls.DELIVERED, cls.RETURNED, cls.CANCELLED, cls.LOST, cls.DAMAGED}

    @classmethod
    def is_failed(cls, status):
        return status in {cls.DELIVERY_FAILED, cls.CUSTOMER_UNAVAILABLE, cls.LOST, cls.DAMAGED}

    @classmethod
    def timeline_index(cls, status):
        try:
            return cls.TIMELINE.index(status)
        except ValueError:
            return -1


class Zone:
    METRO = 'metro'
    URBAN = 'urban'
    RURAL = 'rural'

    CHOICES = [
        (METRO, 'Metro'),
        (URBAN, 'Urban'),
        (RURAL, 'Rural'),
    ]


class PaymentMode:
    PREPAID = 'prepaid'
    COD = 'cod'

    CHOICES = [
        (PREPAID, 'Prepaid'),
        (COD, 'Cash On Delivery'),
    ]


class DeliverySpeed:
    STANDARD = 'standard'
    EXPRESS = 'express'
    PRIORITY = 'priority'

    CHOICES = [
        (STANDARD, 'Standard'),
        (EXPRESS, 'Express'),
        (PRIORITY, 'Priority'),
    ]


class SelectionMethod:
    ENGINE = 'engine'
    MANUAL = 'manual'
    DEFAULT = 'default'

    CHOICES = [
        (ENGINE, 'Shipping Engine'),
        (MANUAL, 'Manual Override'),
        (DEFAULT, 'Default'),
    ]


class PickupStatus:
    REQUESTED = 'requested'
    SCHEDULED = 'scheduled'
    CONFIRMED = 'confirmed'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    FAILED = 'failed'

    CHOICES = [
        (REQUESTED, 'Requested'),
        (SCHEDULED, 'Scheduled'),
        (CONFIRMED, 'Confirmed'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
        (FAILED, 'Failed'),
    ]


class RateType:
    FORWARD = 'forward'
    REVERSE = 'reverse'
    RTO = 'rto'

    CHOICES = [
        (FORWARD, 'Forward'),
        (REVERSE, 'Reverse'),
        (RTO, 'RTO'),
    ]


class OwnerType:
    PLATFORM = 'platform'
    SELLER = 'seller'

    CHOICES = [
        (PLATFORM, 'Platform'),
        (SELLER, 'Seller'),
    ]


class NdrStatus:
    """Non-Delivery Report lifecycle."""
    OPEN = 'open'
    RESOLVED = 'resolved'
    CANCELLED = 'cancelled'

    CHOICES = [
        (OPEN, 'Open'),
        (RESOLVED, 'Resolved'),
        (CANCELLED, 'Cancelled'),
    ]


class NdrReason:
    CUSTOMER_UNREACHABLE = 'customer_unreachable'
    WRONG_ADDRESS = 'wrong_address'
    REFUSED_DELIVERY = 'refused_delivery'
    ADDRESS_INCOMPLETE = 'address_incomplete'
    PINCODE_MISMATCH = 'pincode_mismatch'
    OTHER = 'other'

    CHOICES = [
        (CUSTOMER_UNREACHABLE, 'Customer unreachable'),
        (WRONG_ADDRESS, 'Wrong address'),
        (REFUSED_DELIVERY, 'Delivery refused'),
        (ADDRESS_INCOMPLETE, 'Address incomplete'),
        (PINCODE_MISMATCH, 'PIN code mismatch'),
        (OTHER, 'Other'),
    ]


class ReturnType:
    REFUND = 'refund'
    EXCHANGE = 'exchange'

    CHOICES = [
        (REFUND, 'Refund'),
        (EXCHANGE, 'Exchange'),
    ]


class ReturnStatus:
    """Reverse logistics lifecycle."""
    REQUESTED = 'requested'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    PICKUP_SCHEDULED = 'pickup_scheduled'
    PICKED_UP = 'picked_up'
    IN_TRANSIT = 'in_transit'
    AT_WAREHOUSE = 'at_warehouse'
    INSPECTING = 'inspecting'
    RESTOCKED = 'restocked'
    REFUNDED = 'refunded'
    REPLACED = 'replaced'
    CANCELLED = 'cancelled'
    LOST = 'lost'
    DAMAGED = 'damaged'

    CHOICES = [
        (REQUESTED, 'Requested'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (PICKUP_SCHEDULED, 'Pickup Scheduled'),
        (PICKED_UP, 'Picked Up'),
        (IN_TRANSIT, 'In Transit'),
        (AT_WAREHOUSE, 'At Warehouse'),
        (INSPECTING, 'Inspecting'),
        (RESTOCKED, 'Restocked'),
        (REFUNDED, 'Refunded'),
        (REPLACED, 'Replaced'),
        (CANCELLED, 'Cancelled'),
        (LOST, 'Lost'),
        (DAMAGED, 'Damaged'),
    ]

    RESTOCKABLE = {AT_WAREHOUSE, INSPECTING, RESTOCKED}


class InspectionDecision:
    OK = 'ok'
    DAMAGED = 'damaged'
    USED = 'used'
    WRONG_ITEM = 'wrong_item'
    MISSING_PARTS = 'missing_parts'
    OTHER = 'other'

    CHOICES = [
        (OK, 'In good condition'),
        (DAMAGED, 'Damaged'),
        (USED, 'Used / not in original state'),
        (WRONG_ITEM, 'Wrong item returned'),
        (MISSING_PARTS, 'Missing parts / accessories'),
        (OTHER, 'Other'),
    ]

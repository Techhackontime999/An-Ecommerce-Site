from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from order.models import Order, OrderItem
from accounts.models import SellerProfile
from shop.models import Product, Category
from shipping.models import ShippingAddress
from core.encrypted_fields import EncryptedCharField

from .constants import (
    ShipmentStatus,
    Zone,
    PaymentMode,
    DeliverySpeed,
    SelectionMethod,
    PickupStatus,
    RateType,
    OwnerType,
    NdrStatus,
    NdrReason,
    ReturnType,
    ReturnStatus,
    InspectionDecision,
)


class Warehouse(models.Model):
    """A fulfilment location. A seller may own many warehouses; a platform
    (Amazon FBA style) warehouse serves many sellers. The owner_type field
    distinguishes the two models."""

    owner_type = models.CharField(max_length=10, choices=OwnerType.CHOICES, default=OwnerType.SELLER)
    seller = models.ForeignKey(
        SellerProfile, null=True, blank=True, on_delete=models.CASCADE,
        related_name='warehouses',
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, unique=True, help_text='Short unique code, e.g. BLR-01')
    address_line1 = models.CharField(max_length=250)
    address_line2 = models.CharField(max_length=250, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='India')
    pincode = models.CharField(max_length=20, db_index=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    extra_config = models.JSONField(default=dict, blank=True, help_text='Ops metadata, e.g. {"performance_score": 94}')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return f'{self.code} — {self.name} ({self.city})'

    @property
    def full_address(self):
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f'{self.city}, {self.state} - {self.pincode}')
        parts.append(self.country)
        return ', '.join(parts)


class CourierCompany(models.Model):
    """A registered courier partner. The `code` must match an adapter in the
    courier registry so that the platform can talk to it. Adding a new courier
    means: write an adapter, create a CourierCompany row with its code, enable
    it. No business logic changes."""

    name = models.CharField(max_length=150)
    code = models.CharField(
        max_length=50, unique=True,
        help_text='Adapter lookup key, e.g. "delhivery", "mock". Must match a registered adapter.',
    )
    description = models.TextField(blank=True)
    adapter_path = models.CharField(
        max_length=300, blank=True,
        help_text='Optional dotted path to a custom adapter class, e.g. "myapp.adapters.MyCourier".',
    )
    is_active = models.BooleanField(default=True)
    supports_cod = models.BooleanField(default=True)
    supports_rto = models.BooleanField(default=True)
    supports_reverse_pickup = models.BooleanField(default=False)
    supports_route_optimization = models.BooleanField(default=False)

    api_base_url = models.CharField(max_length=300, blank=True)
    api_key = EncryptedCharField(max_length=512, blank=True, help_text='Encrypted at rest.')
    api_secret = EncryptedCharField(max_length=512, blank=True, help_text='Encrypted at rest.')
    extra_config = models.JSONField(default=dict, blank=True)
    sandbox_mode = models.BooleanField(default=True)

    min_weight_g = models.PositiveIntegerField(default=0)
    max_weight_g = models.PositiveIntegerField(default=30000)
    base_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    per_kg_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cod_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    daily_cutoff_time = models.TimeField(null=True, blank=True, help_text='Latest time to book a same-day pickup.')
    max_capacity_per_day = models.PositiveIntegerField(default=0, help_text='0 = unlimited')
    logo = models.ImageField(upload_to='logistics/couriers/', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'Courier Companies'

    def __str__(self):
        return self.name

    @property
    def adapter(self):
        """Lazily resolve and instantiate the adapter for this courier."""
        from .couriers.registry import get_adapter
        adapter_class = get_adapter(self.code)
        if adapter_class is None and self.adapter_path:
            from django.utils.module_loading import import_string
            adapter_class = import_string(self.adapter_path)
        if adapter_class is None:
            raise AdapterNotFound(
                f'No adapter registered for courier code "{self.code}". '
                f'Implement logistics.couriers.base.BaseCourierAdapter and register it.'
            )
        return adapter_class(courier=self)

    @property
    def today_shipment_count(self):
        return self.shipments.filter(created_at__date=timezone.localdate()).count()

    @property
    def has_capacity(self):
        if self.max_capacity_per_day <= 0:
            return True
        return self.today_shipment_count < self.max_capacity_per_day

    def serviceability_for(self, pincode):
        try:
            return PincodeServiceability.objects.get(courier=self, pincode=str(pincode), is_active=True)
        except PincodeServiceability.DoesNotExist:
            return None


class AdapterNotFound(Exception):
    pass


class CourierService(models.Model):
    """A service tier offered by a courier (standard, express, priority, ...)."""

    courier = models.ForeignKey(CourierCompany, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    delivery_sla_days = models.PositiveIntegerField(default=5)
    delivery_speed = models.CharField(
        max_length=20, choices=DeliverySpeed.CHOICES, default=DeliverySpeed.STANDARD,
    )
    price_premium_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('delivery_sla_days',)
        unique_together = ('courier', 'code')

    def __str__(self):
        return f'{self.courier.name} — {self.name}'


class PincodeServiceability(models.Model):
    """Which couriers serve which PIN codes, plus COD rules and SLA estimates."""

    courier = models.ForeignKey(CourierCompany, on_delete=models.CASCADE, related_name='serviceability')
    pincode = models.CharField(max_length=20, db_index=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zone = models.CharField(max_length=20, choices=Zone.CHOICES, default=Zone.URBAN)
    is_cod_available = models.BooleanField(default=True)
    max_cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=50000)
    estimated_delivery_days = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'PIN Code Serviceability'
        unique_together = ('courier', 'pincode')

    def __str__(self):
        return f'{self.courier.name} → {self.pincode} ({self.get_zone_display()})'


class CourierRule(models.Model):
    """A hard override rule for courier selection, evaluated by priority.

    When all condition fields match, the rule *forces* the target courier (and
    optionally service) regardless of scoring. Rules are meant for ops
    decisions (e.g. "hazardous goods never go with mock", "COD over 20k only
    with mockexpress"). Leave a condition blank/None to mean "any"."""

    name = models.CharField(max_length=150)
    priority = models.PositiveIntegerField(default=100, help_text='Lower numbers are evaluated first.')
    is_active = models.BooleanField(default=True)

    # Conditions
    zone = models.CharField(max_length=20, choices=Zone.CHOICES, blank=True)
    delivery_speed = models.CharField(max_length=20, choices=DeliverySpeed.CHOICES, blank=True)
    payment_mode = models.CharField(max_length=20, choices=PaymentMode.CHOICES, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)
    is_hazardous = models.BooleanField(null=True, blank=True, help_text='Blank = any')
    min_weight_g = models.PositiveIntegerField(null=True, blank=True)
    max_weight_g = models.PositiveIntegerField(null=True, blank=True)
    min_cod_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_cod_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Action
    courier = models.ForeignKey(CourierCompany, on_delete=models.CASCADE, related_name='rules')
    service = models.ForeignKey(CourierService, null=True, blank=True, on_delete=models.CASCADE)

    note = models.TextField(blank=True)

    class Meta:
        ordering = ('priority', 'id')

    def __str__(self):
        return self.name

    def matches(self, context):
        """Return True when every non-blank condition matches the context dict."""
        if self.zone and context.get('zone') != self.zone:
            return False
        if self.delivery_speed and context.get('delivery_speed') != self.delivery_speed:
            return False
        if self.payment_mode and context.get('payment_mode') != self.payment_mode:
            return False
        if self.category_id and context.get('category_id') != self.category_id:
            return False
        if self.is_hazardous is not None and context.get('is_hazardous') != self.is_hazardous:
            return False
        weight = context.get('weight_g')
        if weight is not None:
            if self.min_weight_g is not None and weight < self.min_weight_g:
                return False
            if self.max_weight_g is not None and weight > self.max_weight_g:
                return False
        cod = context.get('cod_amount')
        if cod is not None:
            if self.min_cod_amount is not None and cod < self.min_cod_amount:
                return False
            if self.max_cod_amount is not None and cod > self.max_cod_amount:
                return False
        return True


class ShippingEngineConfig(models.Model):
    """Singleton configuration for the shipping decision engine."""

    name = models.CharField(max_length=50, default='default', unique=True)
    score_weights = models.JSONField(
        default=dict,
        help_text='Keys: cost, sla, performance, success_rate, capacity, return_rate. Higher = more important.',
    )
    ai_enabled = models.BooleanField(default=False)
    ai_confidence_threshold = models.DecimalField(max_digits=4, decimal_places=2, default=0.80)
    enable_rule_overrides = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    DEFAULT_WEIGHTS = {
        'cost': 1.0,
        'sla': 0.8,
        'performance': 0.7,
        'success_rate': 0.6,
        'capacity': 0.4,
        'return_rate': 0.5,
    }

    class Meta:
        verbose_name = 'Shipping Engine Config'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        config, _ = cls.objects.get_or_create(name='default', defaults={'score_weights': cls.DEFAULT_WEIGHTS})
        return config


class Shipment(models.Model):
    """A single package going from a seller/warehouse to a customer.

    One order can be split into several shipments (multi-warehouse). The
    status field holds the *canonical* status; the full timeline lives in
    TrackingEvent."""

    shipment_number = models.CharField(max_length=30, unique=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='logistics_shipments')
    seller = models.ForeignKey(
        SellerProfile, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='logistics_shipments',
    )
    warehouse = models.ForeignKey(
        Warehouse, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments',
    )
    courier = models.ForeignKey(
        CourierCompany, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments',
    )
    service = models.ForeignKey(
        CourierService, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='shipments',
    )

    status = models.CharField(
        max_length=30, choices=ShipmentStatus.CHOICES,
        default=ShipmentStatus.ORDER_CONFIRMED, db_index=True,
    )
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    courier_tracking_url = models.URLField(blank=True)
    external_shipment_id = models.CharField(max_length=100, blank=True, help_text='ID assigned by the courier')

    payment_mode = models.CharField(max_length=10, choices=PaymentMode.CHOICES, default=PaymentMode.PREPAID)
    cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    declared_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_hazardous = models.BooleanField(default=False)
    delivery_speed = models.CharField(
        max_length=20, choices=DeliverySpeed.CHOICES, default=DeliverySpeed.STANDARD,
    )

    # Package
    length_cm = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    width_cm = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    height_cm = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    weight_g = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    # Route
    source_pincode = models.CharField(max_length=20, blank=True)
    destination_pincode = models.CharField(max_length=20, db_index=True)
    destination_zone = models.CharField(max_length=20, choices=Zone.CHOICES, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)

    # Charges
    shipping_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    courier_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='INR')

    # Selection
    selected_by = models.CharField(max_length=10, choices=SelectionMethod.CHOICES, default=SelectionMethod.DEFAULT)
    selection_reason = models.TextField(blank=True)

    # Label
    label = models.FileField(upload_to='logistics/labels/%Y/%m/%d/', blank=True)

    # Ops
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_tracked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['courier', 'created_at']),
        ]

    def __str__(self):
        return f'{self.shipment_number or self.pk} — {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.shipment_number:
            prefix = getattr(settings, 'LOGISTICS_AWB_PREFIX', 'SSD')
            now = timezone.localtime()
            self.shipment_number = f'{prefix}-{now:%Y%m%d}-{now:%H%M%S}-{self.order_id or "X"}-{abs(hash(self.order_id or 0)) % 9999:04d}'
        super().save(*args, **kwargs)

    @property
    def is_cod(self):
        return self.payment_mode == PaymentMode.COD

    @property
    def is_terminal(self):
        return ShipmentStatus.is_terminal(self.status)

    @property
    def volumetric_weight_g(self):
        """Volumetric weight: (L×W×H in cm) / 5000 → grams."""
        vol = float(self.length_cm or 0) * float(self.width_cm or 0) * float(self.height_cm or 0)
        return (vol / 5000) * 1000

    @property
    def chargeable_weight_g(self):
        return max(float(self.weight_g), float(self.volumetric_weight_g))

    @property
    def tracking_url(self):
        if self.courier_tracking_url:
            return self.courier_tracking_url
        base = getattr(settings, 'LOGISTICS_TRACKING_BASE_URL', '')
        if base and self.tracking_number:
            sep = '&' if '?' in base else '?'
            return f'{base}{sep}q={self.tracking_number}'
        return ''

    @property
    def latest_event(self):
        return self.tracking_events.order_by('-timestamp', '-id').first()

    @property
    def progress(self):
        idx = ShipmentStatus.timeline_index(self.status)
        return idx if idx >= 0 else 0

    @property
    def timeline(self):
        return [ShipmentStatus.LABELS[s] for s in ShipmentStatus.TIMELINE]


class ShipmentItem(models.Model):
    """Snapshot of one ordered line inside a shipment (supports split shipments)."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, null=True, blank=True, on_delete=models.SET_NULL)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=250)
    sku = models.CharField(max_length=100, blank=True)
    hsn_code = models.CharField(max_length=20, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    weight_g = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.quantity}× {self.product_name}'

    @property
    def total_weight_g(self):
        return float(self.weight_g) * self.quantity


class TrackingEvent(models.Model):
    """One entry in the unified tracking timeline, independent of courier."""

    class Source:
        WEBHOOK = 'webhook'
        POLL = 'poll'
        MANUAL = 'manual'
        SYSTEM = 'system'

        CHOICES = [
            (WEBHOOK, 'Courier webhook'),
            (POLL, 'Courier poll'),
            (MANUAL, 'Manual override'),
            (SYSTEM, 'System'),
        ]

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    courier_status = models.CharField(max_length=100, blank=True, help_text='Raw status string from the courier')
    status = models.CharField(max_length=30, choices=ShipmentStatus.CHOICES, db_index=True)
    location = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=20, choices=Source.CHOICES, default=Source.SYSTEM, db_index=True)
    pod_url = models.URLField(blank=True, help_text='Delivery proof image/URL (POD), when provided by the courier')
    received_by = models.CharField(max_length=100, blank=True, help_text='Recipient name recorded on the delivery proof')
    is_current = models.BooleanField(default=False)
    raw_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('timestamp', 'id')
        indexes = [
            models.Index(fields=['shipment', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.shipment.shipment_number} — {self.get_status_display()} @ {self.location or "—"}'


class PickupRequest(models.Model):
    """A pickup booking with a courier for one shipment."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='pickup_requests')
    courier = models.ForeignKey(CourierCompany, null=True, blank=True, on_delete=models.SET_NULL)
    pickup_address = models.ForeignKey(ShippingAddress, null=True, blank=True, on_delete=models.SET_NULL)
    address_text = models.TextField(blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    slot = models.CharField(max_length=30, blank=True, help_text='e.g. 10:00-14:00')
    status = models.CharField(max_length=20, choices=PickupStatus.CHOICES, default=PickupStatus.REQUESTED)
    reference = models.CharField(max_length=100, blank=True, help_text='Courier pickup reference id')
    attempts = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Pickup {self.reference or self.id} — {self.get_status_display()}'


class ShippingRateQuote(models.Model):
    """A rate quote returned by a courier rate API (or locally estimated)."""

    courier = models.ForeignKey(CourierCompany, on_delete=models.CASCADE, related_name='rate_quotes')
    service = models.ForeignKey(CourierService, null=True, blank=True, on_delete=models.SET_NULL)
    shipment = models.ForeignKey(Shipment, null=True, blank=True, on_delete=models.CASCADE, related_name='rate_quotes')
    base_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cod_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fuel_surcharge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='INR')
    eta_days = models.PositiveIntegerField(default=5)
    rate_type = models.CharField(max_length=10, choices=RateType.CHOICES, default=RateType.FORWARD)
    valid_until = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.courier.name} — {self.total} {self.currency}'


class CourierPerformanceScore(models.Model):
    """Rolling performance score for the shipping engine's quality factors."""

    courier = models.ForeignKey(CourierCompany, on_delete=models.CASCADE, related_name='performance_scores')
    period = models.CharField(max_length=7, db_index=True, help_text='YYYY-MM')
    zone = models.CharField(max_length=20, choices=Zone.CHOICES, blank=True)
    total_shipments = models.PositiveIntegerField(default=0)
    delivered = models.PositiveIntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    avg_delivery_days = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    on_time_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    capacity_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    return_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    composite_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-period',)
        unique_together = ('courier', 'period', 'zone')

    def __str__(self):
        return f'{self.courier.name} {self.period} ({self.zone or "all"}) — {self.composite_score}'


class Holiday(models.Model):
    """Courier-specific or global (courier=None) holiday calendar. Used to
    compute realistic estimated delivery dates."""

    courier = models.ForeignKey(CourierCompany, null=True, blank=True, on_delete=models.CASCADE, related_name='holidays')
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('date',)
        unique_together = ('courier', 'date')

    def __str__(self):
        return f'{self.name} — {self.date}'


class NDRRecord(models.Model):
    """A Non-Delivery Report: a delivery that failed and needs a reattempt or
    an alternative resolution. Every NDR is linked to a shipment and carries
    the reported reason plus resolution steps (reattempt / address fix / RTO)."""

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='ndr_records')
    status = models.CharField(max_length=20, choices=NdrStatus.CHOICES, default=NdrStatus.OPEN, db_index=True)
    reason = models.CharField(max_length=30, choices=NdrReason.CHOICES, default=NdrReason.OTHER)
    courier_remarks = models.TextField(blank=True, help_text='Raw remarks from the courier, if any.')
    reattempt_requested = models.BooleanField(default=False)
    reattempt_at = models.DateTimeField(null=True, blank=True)
    corrected_address = models.TextField(blank=True)
    corrected_phone = models.CharField(max_length=20, blank=True)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'NDR {self.pk} — {self.shipment.shipment_number} ({self.get_status_display()})'

    def resolve(self, notes='', actor=None):
        self.status = NdrStatus.RESOLVED
        if notes:
            self.resolution_notes = notes
        self.resolved_by = actor
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolution_notes', 'resolved_by', 'resolved_at', 'updated_at'])
        AuditLog.log(AuditLog.ACTION_MANUAL, 'ndr', self.pk, {'resolution_notes': notes}, actor)


class ReturnShipment(models.Model):
    """Reverse logistics / return shipment.

    A customer return flows through approval → reverse pickup → inspection →
    restock → refund / replacement. Exchange requests are supported via
    ``return_type``. The original (forward) shipment stays untouched; a fresh
    reverse shipment is created against the original courier (or an explicitly
    chosen one).
    """

    return_number = models.CharField(max_length=30, unique=True, blank=True)
    original_shipment = models.ForeignKey(
        Shipment, on_delete=models.CASCADE, related_name='return_shipments',
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='logistics_returns')
    return_request = models.ForeignKey(
        'order.ReturnRequest', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='logistics_return_shipments',
    )
    return_type = models.CharField(max_length=10, choices=ReturnType.CHOICES, default=ReturnType.REFUND)
    status = models.CharField(
        max_length=20, choices=ReturnStatus.CHOICES, default=ReturnStatus.REQUESTED, db_index=True,
    )
    reason = models.CharField(max_length=30, choices=NdrReason.CHOICES, blank=True, default=NdrReason.OTHER)
    customer_notes = models.TextField(blank=True)

    courier = models.ForeignKey(CourierCompany, null=True, blank=True, on_delete=models.SET_NULL)
    tracking_number = models.CharField(max_length=100, blank=True, db_index=True)
    pickup_address = models.TextField(blank=True)
    pickup_scheduled_at = models.DateTimeField(null=True, blank=True)
    pickup_reference = models.CharField(max_length=100, blank=True)

    inspection_decision = models.CharField(
        max_length=20, choices=InspectionDecision.CHOICES, blank=True,
    )
    inspection_notes = models.TextField(blank=True)
    inspected_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    inspected_at = models.DateTimeField(null=True, blank=True)

    restock_warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.SET_NULL)
    restocked_at = models.DateTimeField(null=True, blank=True)

    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunded_at = models.DateTimeField(null=True, blank=True)

    exchange_shipment = models.ForeignKey(
        Shipment, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='created_by_exchange', help_text='New forward shipment created for an exchange.',
    )

    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.return_number or self.pk} — {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.return_number:
            now = timezone.localtime()
            self.return_number = f'RMA-{self.order_id or "X"}-{now:%Y%m%d}-{self.pk or abs(hash(self.original_shipment_id or 0)) % 9999:04d}'
        super().save(*args, **kwargs)


class WebhookEvent(models.Model):
    """A webhook call received from a courier. Payloads are logged for audit
    and replay before being applied to shipments."""

    courier = models.ForeignKey(CourierCompany, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=300, blank=True)
    dedupe_key = models.CharField(
        max_length=64, blank=True, null=True, db_index=True,
        help_text='SHA-256 of the raw request body — used to reject courier replays',
    )
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['courier', 'dedupe_key'],
                name='uniq_webhookevent_courier_dedupe',
            ),
        ]

    def __str__(self):
        return f'Webhook {self.id} — {self.event_type or "?"} ({self.created_at:%Y-%m-%d %H:%M})'


class AuditLog(models.Model):
    """Append-only audit trail for every mutating LMS operation."""

    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_STATUS = 'status'
    ACTION_CANCEL = 'cancel'
    ACTION_PICKUP = 'pickup'
    ACTION_ERROR = 'error'
    ACTION_WEBHOOK = 'webhook'
    ACTION_LABEL = 'label'
    ACTION_MANUAL = 'manual_override'

    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30, db_index=True)
    object_type = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=30, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['object_type', 'object_id', 'created_at']),
        ]

    def __str__(self):
        return f'{self.action} {self.object_type}#{self.object_id} ({self.created_at:%Y-%m-%d %H:%M})'

    @classmethod
    def log(cls, action, object_type, object_id='', details=None, actor=None):
        try:
            return cls.objects.create(
                action=action, object_type=object_type, object_id=str(object_id),
                details=details or {}, actor=actor,
            )
        except Exception:
            return None

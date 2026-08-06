"""Django admin for the Logistics Management System.

Provides operators and super admins with the full LMS toolkit:
shipments, couriers, warehouses, NDRs, returns, rate quotes, performance
scores, webhooks and the audit trail — plus one-click actions that call the
fulfilment service (create shipment, track, pickup, delivered, label, cancel).
"""

import io

from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from core.admin_actions import export_as_csv_action

from .constants import ShipmentStatus, ReturnStatus, NdrStatus, PickupStatus
from .models import (
    AuditLog,
    CourierCompany,
    CourierPerformanceScore,
    CourierRule,
    CourierService,
    Holiday,
    NDRRecord,
    PickupRequest,
    PincodeServiceability,
    ReturnShipment,
    Shipment,
    ShipmentItem,
    ShippingEngineConfig,
    ShippingRateQuote,
    TrackingEvent,
    Warehouse,
    WebhookEvent,
)
from .services.fulfillment import FulfillmentService


STATUS_TONES = {
    ShipmentStatus.ORDER_CONFIRMED: '#CA8A04',
    ShipmentStatus.PACKED: '#0E7490',
    ShipmentStatus.READY_FOR_PICKUP: '#7C3AED',
    ShipmentStatus.PICKED_UP: '#2563EB',
    ShipmentStatus.IN_TRANSIT: '#1D4ED8',
    ShipmentStatus.AT_ORIGIN_HUB: '#0284C7',
    ShipmentStatus.AT_DESTINATION_HUB: '#0284C7',
    ShipmentStatus.OUT_FOR_DELIVERY: '#0891B2',
    ShipmentStatus.DELIVERED: '#16A34A',
    ShipmentStatus.DELIVERY_FAILED: '#DC2626',
    ShipmentStatus.CUSTOMER_UNAVAILABLE: '#EA580C',
    ShipmentStatus.RTO_INITIATED: '#9333EA',
    ShipmentStatus.RETURNED: '#64748B',
    ShipmentStatus.CANCELLED: '#BE123C',
    ShipmentStatus.LOST: '#111827',
    ShipmentStatus.DAMAGED: '#B91C1C',
}


def status_badge(obj, tone_map=STATUS_TONES):
    tone = tone_map.get(obj.status, '#64748B')
    return format_html(
        '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        'font-size:11px;font-weight:600;color:{};background:{}33">{}</span>',
        tone, tone, obj.get_status_display(),
    )


@admin.register(CourierCompany)
class CourierCompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'adapter_ready', 'is_active', 'supports_cod', 'sandbox_mode',
                    'base_charge', 'per_kg_charge', 'cod_charge_percent', 'today_shipment_count', 'has_capacity']
    list_filter = ['is_active', 'supports_cod', 'supports_rto', 'sandbox_mode']
    search_fields = ['name', 'code', 'api_base_url']
    fieldsets = (
        (None, {'fields': ('name', 'code', 'description', 'is_active')}),
        ('Capabilities', {'fields': (
            ('supports_cod', 'supports_rto', 'supports_reverse_pickup'),
            'supports_route_optimization',
        )}),
        ('Credentials', {'fields': ('adapter_path', 'api_base_url', 'api_key', 'api_secret', 'extra_config', 'sandbox_mode')}),
        ('Pricing', {'fields': (
            ('min_weight_g', 'max_weight_g'),
            ('base_charge', 'per_kg_charge', 'cod_charge_percent'),
        )}),
        ('Operations', {'fields': ('daily_cutoff_time', 'max_capacity_per_day', 'logo')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']
    actions = ['enable', 'disable', export_as_csv_action(
        description='Export couriers as CSV',
        fields=['name', 'code', 'is_active', 'supports_cod', 'base_charge', 'per_kg_charge', 'cod_charge_percent'],
    )]

    @admin.display(boolean=True, description='Adapter')
    def adapter_ready(self, obj):
        try:
            obj.adapter
            return True
        except Exception:
            return False

    @admin.action(description='Enable selected couriers')
    def enable(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} courier(s) enabled.')

    @admin.action(description='Disable selected couriers')
    def disable(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f'{n} courier(s) disabled.')


@admin.register(CourierService)
class CourierServiceAdmin(admin.ModelAdmin):
    list_display = ['courier', 'name', 'code', 'delivery_speed', 'delivery_sla_days', 'price_premium_percent', 'is_default', 'is_active']
    list_filter = ['delivery_speed', 'is_default', 'is_active', 'courier']
    search_fields = ['name', 'code']


@admin.register(PincodeServiceability)
class PincodeServiceabilityAdmin(admin.ModelAdmin):
    list_display = ['courier', 'pincode', 'city', 'state', 'zone', 'is_cod_available', 'max_cod_amount', 'estimated_delivery_days', 'is_active']
    list_filter = ['courier', 'zone', 'is_cod_available', 'is_active']
    search_fields = ['pincode', 'city', 'state']


@admin.register(CourierRule)
class CourierRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'priority', 'courier', 'service', 'is_active', 'zone', 'payment_mode', 'delivery_speed']
    list_filter = ['is_active', 'zone', 'payment_mode', 'delivery_speed', 'courier']
    search_fields = ['name', 'note']


@admin.register(ShippingEngineConfig)
class ShippingEngineConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'ai_enabled', 'ai_confidence_threshold', 'enable_rule_overrides', 'updated_at']


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'seller', 'owner_type', 'city', 'state', 'pincode', 'is_active', 'open_shipments']
    list_filter = ['owner_type', 'is_active', 'state', 'country']
    search_fields = ['code', 'name', 'city', 'pincode', 'seller__shop_name']
    fieldsets = (
        (None, {'fields': ('owner_type', 'seller', 'name', 'code', 'is_active')}),
        ('Address', {'fields': ('address_line1', 'address_line2', 'city', 'state', 'country', 'pincode')}),
        ('Geo', {'fields': ('latitude', 'longitude')}),
        ('Contact', {'fields': ('contact_name', 'contact_phone')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = ['created_at', 'updated_at']
    actions = ['enable', 'disable']

    @admin.display(description='Open shipments')
    def open_shipments(self, obj):
        return obj.shipments.filter(status__in=ShipmentStatus.TIMELINE).count()

    @admin.action(description='Enable selected warehouses')
    def enable(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_active=True)} warehouse(s) enabled.')

    @admin.action(description='Disable selected warehouses')
    def disable(self, request, queryset):
        self.message_user(request, f'{queryset.update(is_active=False)} warehouse(s) disabled.')


class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0
    readonly_fields = ['product_name', 'sku', 'quantity', 'weight_g', 'unit_price']


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0
    readonly_fields = ['courier_status', 'status', 'location', 'description', 'timestamp', 'is_current', 'raw_payload']
    can_delete = False
    ordering = ('timestamp',)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['shipment_number', 'order_link', 'warehouse', 'courier', 'tracking_number',
                    'status_badge', 'payment_mode', 'destination_pincode', 'estimated_delivery_date',
                    'created_at']
    list_filter = ['status', 'payment_mode', 'delivery_speed', 'selected_by', 'courier', 'warehouse', 'created_at']
    search_fields = ['shipment_number', 'tracking_number', 'external_shipment_id', 'order__first_name',
                     'order__last_name', 'order__email', 'destination_pincode']
    list_select_related = ['order', 'courier', 'warehouse']
    date_hierarchy = 'created_at'
    raw_id_fields = ['order', 'seller', 'warehouse', 'courier', 'service']
    readonly_fields = ['shipment_number', 'created_at', 'updated_at', 'label_preview', 'courier_charge',
                       'progress_display', 'tracking_url', 'volumetric_weight', 'chargeable_weight']
    inlines = [ShipmentItemInline, TrackingEventInline]
    fieldsets = (
        (None, {'fields': ('shipment_number', 'order', 'seller', 'warehouse', 'status', 'progress_display')}),
        ('Courier', {'fields': ('courier', 'service', 'tracking_number', 'courier_tracking_url',
                                'external_shipment_id', 'selected_by', 'selection_reason', 'tracking_url')}),
        ('Route', {'fields': (('source_pincode', 'destination_pincode'), 'destination_zone', 'distance_km',
                              'estimated_delivery_date', 'picked_up_at', 'delivered_at', 'last_tracked_at')}),
        ('Package', {'fields': (('length_cm', 'width_cm', 'height_cm', 'weight_g'),
                                'volumetric_weight', 'chargeable_weight')}),
        ('Payment & Value', {'fields': (('payment_mode', 'cod_amount'), 'declared_value', 'is_hazardous',
                                        'delivery_speed', ('shipping_charge', 'courier_charge', 'currency'))}),
        ('Label', {'fields': ('label', 'label_preview')}),
        ('Ops', {'fields': ('error_message', 'retry_count')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    actions = [
        'fulfil_shipments',
        'pull_tracking',
        'mark_picked_up',
        'mark_delivered',
        'schedule_pickups',
        'generate_labels',
        'cancel_shipments',
        export_as_csv_action(
            description='Export shipments as CSV',
            fields=['shipment_number', 'order', 'warehouse', 'courier', 'tracking_number', 'status',
                    'payment_mode', 'cod_amount', 'declared_value', 'weight_g', 'destination_pincode',
                    'estimated_delivery_date', 'shipping_charge', 'courier_charge', 'selected_by',
                    'created_at', 'delivered_at'],
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order', 'courier', 'warehouse', 'service')

    def status_badge(self, obj):
        return status_badge(obj)

    @admin.display(description='Order')
    def order_link(self, obj):
        url = reverse('admin:order_order_change', args=[obj.order_id])
        return format_html('<a href="{}">#{}</a>', url, obj.order_id)

    @admin.display(description='Volumetric')
    def volumetric_weight(self, obj):
        return f'{float(obj.volumetric_weight_g or 0):.0f} g'

    @admin.display(description='Chargeable')
    def chargeable_weight(self, obj):
        return f'{float(obj.chargeable_weight_g or 0):.0f} g'

    @admin.display(description='Progress')
    def progress_display(self, obj):
        idx = obj.progress
        total = len(ShipmentStatus.TIMELINE)
        return f'{idx}/{total} — {obj.get_status_display()}'

    @admin.display(description='Label')
    def label_preview(self, obj):
        if not obj.label:
            return '—'
        return format_html('<a href="{}" target="_blank">Open PDF</a>', obj.label.url)

    def _run_service_action(self, request, queryset, method, label, statuses=None):
        ok, failed = 0, 0
        for shipment in queryset:
            if statuses and shipment.status in statuses:
                continue
            try:
                getattr(FulfillmentService, method)(shipment, actor=request.user)
                ok += 1
            except Exception as exc:
                failed += 1
                self.message_user(request, f'{shipment.shipment_number}: {exc}', level='ERROR')
        self.message_user(request, f'{label}: {ok} succeeded, {failed} failed.')

    @admin.action(description='Create shipments at courier (fulfil)')
    def fulfil_shipments(self, request, queryset):
        self._run_service_action(request, queryset.filter(tracking_number=''), 'create_shipment',
                                 'Fulfilment', statuses=())

    @admin.action(description='Pull tracking from courier')
    def pull_tracking(self, request, queryset):
        self._run_service_action(request, queryset.exclude(tracking_number=''), 'track',
                                 'Tracking pull', statuses=())

    @admin.action(description='Mark picked up')
    def mark_picked_up(self, request, queryset):
        self._run_service_action(request, queryset, 'mark_picked_up', 'Mark picked up',
                                 statuses={ShipmentStatus.PICKED_UP, ShipmentStatus.DELIVERED})

    @admin.action(description='Mark delivered')
    def mark_delivered(self, request, queryset):
        ok, failed = 0, 0
        for shipment in queryset.exclude(status=ShipmentStatus.DELIVERED):
            try:
                FulfillmentService.set_status(
                    shipment, ShipmentStatus.DELIVERED,
                    description='Marked delivered from admin.', actor=request.user,
                )
                ok += 1
            except Exception as exc:
                failed += 1
                self.message_user(request, f'{shipment.shipment_number}: {exc}', level='ERROR')
        self.message_user(request, f'Mark delivered: {ok} succeeded, {failed} failed.')

    @admin.action(description='Schedule pickups')
    def schedule_pickups(self, request, queryset):
        self._run_service_action(request, queryset.exclude(courier=None), 'schedule_pickup',
                                 'Pickup scheduling')

    @admin.action(description='Generate shipping labels')
    def generate_labels(self, request, queryset):
        self._run_service_action(request, queryset, 'attach_label', 'Label generation')

    @admin.action(description='Cancel shipments')
    def cancel_shipments(self, request, queryset):
        self._run_service_action(
            request,
            queryset.exclude(status__in=[ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED,
                                         ShipmentStatus.CANCELLED, ShipmentStatus.LOST,
                                         ShipmentStatus.DAMAGED]),
            'cancel_shipment', 'Cancellation',
        )


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ['shipment', 'status', 'courier_status', 'location', 'is_current', 'timestamp']
    list_filter = ['status', 'is_current', 'timestamp']
    search_fields = ['shipment__shipment_number', 'courier_status', 'location']
    readonly_fields = ['created_at']


@admin.register(PickupRequest)
class PickupRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'shipment', 'courier', 'scheduled_at', 'slot', 'status', 'reference', 'attempts']
    list_filter = ['status', 'created_at']
    search_fields = ['shipment__shipment_number', 'reference']
    raw_id_fields = ['shipment', 'courier']
    actions = ['cancel_selected_pickups']

    @admin.action(description='Cancel selected pickups')
    def cancel_selected_pickups(self, request, queryset):
        n = 0
        for pickup in queryset:
            try:
                FulfillmentService.cancel_pickup(pickup, actor=request.user)
                n += 1
            except Exception as exc:
                self.message_user(request, f'Pickup #{pickup.pk}: {exc}', level='ERROR')
        self.message_user(request, f'{n} pickup(s) cancelled.')


@admin.register(ShippingRateQuote)
class ShippingRateQuoteAdmin(admin.ModelAdmin):
    list_display = ['courier', 'shipment', 'service', 'base_charge', 'cod_charge', 'fuel_surcharge',
                    'total', 'eta_days', 'rate_type', 'created_at']
    list_filter = ['rate_type', 'courier', 'created_at']
    search_fields = ['shipment__shipment_number', 'courier__name']


@admin.register(CourierPerformanceScore)
class CourierPerformanceScoreAdmin(admin.ModelAdmin):
    list_display = ['courier', 'period', 'zone', 'total_shipments', 'success_rate', 'avg_delivery_days',
                    'on_time_rate', 'capacity_score', 'return_rate', 'composite_score', 'computed_at']
    list_filter = ['courier', 'period', 'zone']


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ['courier', 'date', 'name', 'is_active']
    list_filter = ['courier', 'is_active', 'date']


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'courier', 'event_type', 'processed', 'signature', 'created_at', 'processed_at']
    list_filter = ['processed', 'courier', 'created_at']
    search_fields = ['event_type', 'signature']
    readonly_fields = ['payload', 'created_at', 'processed_at', 'error']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'object_type', 'object_id', 'created_at']
    list_filter = ['action', 'object_type', 'created_at']
    search_fields = ['object_id', 'details', 'actor__username']
    readonly_fields = ['actor', 'action', 'object_type', 'object_id', 'details', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(NDRRecord)
class NDRRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'shipment', 'status', 'reason', 'reattempt_requested', 'corrected_address',
                    'resolved_by', 'created_at']
    list_filter = ['status', 'reason', 'reattempt_requested', 'created_at']
    search_fields = ['shipment__shipment_number', 'courier_remarks', 'resolution_notes']
    raw_id_fields = ['shipment', 'resolved_by']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['resolve_selected']

    @admin.action(description='Resolve selected NDRs')
    def resolve_selected(self, request, queryset):
        n = queryset.filter(status=NdrStatus.OPEN).count()
        for record in queryset.filter(status=NdrStatus.OPEN):
            record.resolve('Resolved from admin.', actor=request.user)
        self.message_user(request, f'{n} NDR(s) resolved.')


@admin.register(ReturnShipment)
class ReturnShipmentAdmin(admin.ModelAdmin):
    list_display = ['return_number', 'original_shipment', 'order', 'return_type', 'status',
                    'reason', 'tracking_number', 'pickup_scheduled_at', 'created_at']
    list_filter = ['status', 'return_type', 'reason', 'courier', 'created_at']
    search_fields = ['return_number', 'original_shipment__shipment_number', 'order__id', 'tracking_number']
    raw_id_fields = ['original_shipment', 'order', 'return_request', 'courier', 'restock_warehouse',
                     'exchange_shipment', 'inspected_by']
    readonly_fields = ['return_number', 'created_at', 'updated_at']
    actions = [
        'approve_returns',
        'schedule_pickups',
        'mark_picked_up',
        'inspect_ok',
        'restock_returns',
        export_as_csv_action(
            description='Export returns as CSV',
            fields=['return_number', 'original_shipment', 'return_type', 'status', 'reason',
                    'inspection_decision', 'refund_amount', 'created_at', 'updated_at'],
        ),
    ]

    def _action(self, request, queryset, method, label, **kwargs):
        ok, failed = 0, 0
        for ret in queryset:
            try:
                getattr(FulfillmentService, method)(ret, actor=request.user, **kwargs)
                ok += 1
            except Exception as exc:
                failed += 1
                self.message_user(request, f'{ret.return_number}: {exc}', level='ERROR')
        self.message_user(request, f'{label}: {ok} succeeded, {failed} failed.')

    @admin.action(description='Approve selected returns')
    def approve_returns(self, request, queryset):
        self._action(request, queryset, 'approve_return', 'Approval', reschedule=False)

    @admin.action(description='Schedule reverse pickups')
    def schedule_pickups(self, request, queryset):
        self._action(request, queryset, 'schedule_return_pickup', 'Pickup scheduling')

    @admin.action(description='Mark picked up')
    def mark_picked_up(self, request, queryset):
        self._action(request, queryset, 'mark_return_picked_up', 'Mark picked up')

    @admin.action(description='Inspect (good condition)')
    def inspect_ok(self, request, queryset):
        from .constants import InspectionDecision
        self._action(request, queryset, 'inspect_return', 'Inspection',
                     decision=InspectionDecision.OK, notes='Inspected from admin.')

    @admin.action(description='Restock into warehouse')
    def restock_returns(self, request, queryset):
        self._action(request, queryset, 'restock_return', 'Restock')

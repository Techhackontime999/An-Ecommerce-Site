from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
import logging

from core.admin_actions import export_as_csv_action
from notifications.models import Notification
from notifications.services import notify
from .models import Order, OrderAuditLog, OrderItem, Refund, ReturnRequest

logger = logging.getLogger(__name__)


STATUS_TONES = {
    Order.Status.PENDING: '#CA8A04',
    Order.Status.PROCESSING: '#0E7490',
    Order.Status.SHIPPED: '#1D4ED8',
    Order.Status.DELIVERED: '#16A34A',
    Order.Status.CANCELLED: '#BE123C',
    Order.Status.REFUNDED: '#7C3AED',
}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    readonly_fields = ['price', 'quantity']


class OrderAuditLogInline(admin.TabularInline):
    model = OrderAuditLog
    extra = 0
    can_delete = False
    readonly_fields = ['from_status', 'to_status', 'action', 'note', 'actor', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'first_name', 'last_name', 'city', 'status_badge', 'paid', 'shipment_link', 'total', 'created']
    list_filter = ['status', 'paid', 'created', 'updated', 'city']
    search_fields = ['order_number', 'first_name', 'last_name', 'email', 'user__username']
    inlines = [OrderItemInline, OrderAuditLogInline]
    list_select_related = ['user']
    date_hierarchy = 'created'
    readonly_fields = ['created', 'updated', 'shipment_link']
    actions = [
        'mark_as_paid',
        'mark_as_processing',
        'mark_as_shipped',
        'mark_as_delivered',
        'mark_as_cancelled',
        'mark_as_refunded',
        export_as_csv_action(
            description='Export selected orders as CSV',
            fields=[
                'order_number', 'first_name', 'last_name', 'email', 'address',
                'postal_code', 'city', 'paid', 'status', 'shipping_cost',
                'shipping_method_name', 'created', 'updated',
            ],
        ),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'shipment').prefetch_related('logistics_shipments')

    def total(self, obj):
        return obj.get_total_cost()
    total.short_description = 'Total (₹)'

    @admin.display(empty_value='—', description='Status')
    def status_badge(self, obj):
        tone = STATUS_TONES.get(obj.status, '#64748B')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'font-size:11px;font-weight:600;color:{};background:{}33">{}</span>',
            tone, tone, obj.get_status_display(),
        )

    @admin.display(empty_value='—', description='Shipment')
    def shipment_link(self, obj):
        shipment = obj.logistics_shipments.first()
        if shipment is not None:
            url = reverse('admin:logistics_shipment_change', args=[shipment.pk])
            return format_html(
                '<a href="{}">LMS #{} · {}</a>',
                url, shipment.pk, shipment.get_status_display(),
            )
        shipment = getattr(obj, 'shipment', None)
        if shipment is None:
            return None
        url = reverse('admin:shipping_shipment_change', args=[shipment.pk])
        return format_html(
            '<a href="{}">#{} · {}</a>',
            url, shipment.pk, shipment.get_status_display(),
        )

    def mark_as_paid(self, request, queryset):
        updated = queryset.filter(paid=False).update(paid=True)
        self.message_user(request, f'{updated} order(s) marked as paid.')
    mark_as_paid.short_description = 'Mark selected orders as paid'

    def _apply_status(self, request, order, status, message, payment_status=''):
        from order.state import set_order_status
        ok, _ = set_order_status(
            order, status, actor=request.user, note=message, force=True,
        )
        if not ok:
            return False
        if payment_status:
            self._sync_payment(order, payment_status)
        notify(
            order.user, Notification.Category.ORDER,
            f'Order #{order.order_number} {message}',
            self._status_notice(status),
            link=reverse('order:my_orders'), icon='box',
        )
        return True

    @staticmethod
    def _status_notice(status):
        return {
            Order.Status.PROCESSING: 'Your order is being prepared for dispatch.',
            Order.Status.SHIPPED: 'Your order is on its way.',
            Order.Status.DELIVERED: 'Your order has been delivered. Enjoy!',
            Order.Status.CANCELLED: 'Your order has been cancelled. Refunds, if any, will be processed soon.',
            Order.Status.REFUNDED: 'Your refund for this order has been processed.',
        }.get(status, '')

    @admin.action(description='Set status to Processing')
    def mark_as_processing(self, request, queryset):
        updated = 0
        for order in queryset.select_related('user'):
            if self._apply_status(request, order, Order.Status.PROCESSING, 'is being processed'):
                updated += 1
        self.message_user(request, f'{updated} order(s) moved to processing.')

    @admin.action(description='Set status to Shipped')
    def mark_as_shipped(self, request, queryset):
        updated = 0
        for order in queryset.select_related('user'):
            if self._apply_status(request, order, Order.Status.SHIPPED, 'has been shipped'):
                updated += 1
        self.message_user(request, f'{updated} order(s) marked as shipped.')

    @admin.action(description='Set status to Delivered')
    def mark_as_delivered(self, request, queryset):
        updated = 0
        for order in queryset.select_related('user'):
            if self._apply_status(request, order, Order.Status.DELIVERED, 'delivered'):
                updated += 1
        self.message_user(request, f'{updated} order(s) marked as delivered.')

    @admin.action(description='Set status to Cancelled')
    def mark_as_cancelled(self, request, queryset):
        updated = 0
        for order in queryset.select_related('user'):
            if self._apply_status(request, order, Order.Status.CANCELLED, 'cancelled', payment_status='cancelled'):
                updated += 1
        self.message_user(request, f'{updated} order(s) marked as cancelled.')

    @admin.action(description='Set status to Refunded')
    def mark_as_refunded(self, request, queryset):
        updated = 0
        for order in queryset.select_related('user'):
            if self._apply_status(request, order, Order.Status.REFUNDED, 'refunded', payment_status='refunded'):
                updated += 1
        self.message_user(request, f'{updated} order(s) marked as refunded.')

    @staticmethod
    def _sync_payment(order, order_status):
        """Reconcile the order's payment after an admin status change.

        Only ``refunded`` is a valid Payment status — the old code wrote the
        order's ``cancelled`` state into Payment.status, which is not one of the
        model's choices. Captured payments are refunded through the gateway.
        """
        from payments.models import Payment
        payment = Payment.objects.filter(order=order).first()
        if payment is None:
            return
        if payment.status == 'refunded':
            return
        if payment.status == 'captured':
            from order.stock import release_stock
            from payments.services import refund_payment
            release_stock(order)
            try:
                refund_payment(
                    payment,
                    note=f'Order {order.order_number} {order_status}',
                )
                return
            except Exception as exc:
                logger.exception('Gateway refund failed for order %s during admin %s: %s',
                                 order.id, order_status, exc)
        if order_status == 'refunded' and payment.status != 'refunded':
            payment.status = 'refunded'
            payment.save(update_fields=['status', 'updated_at'])


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'user', 'reason', 'status_badge', 'requested_at', 'processed_at']
    list_filter = ['status', 'reason', 'requested_at']
    search_fields = ['order__id', 'user__username', 'details']
    list_select_related = ['order', 'user']
    raw_id_fields = ['order', 'user', 'processed_by']
    date_hierarchy = 'requested_at'
    readonly_fields = ['requested_at', 'updated']
    actions = [
        'approve_returns',
        'reject_returns',
        'mark_refunded',
        export_as_csv_action(
            description='Export selected return requests as CSV',
            fields=['id', 'order', 'user', 'reason', 'status', 'details', 'requested_at', 'processed_at'],
        ),
    ]

    @admin.display(description='Status')
    def status_badge(self, obj):
        tones = {'pending': '#CA8A04', 'approved': '#0E7490', 'rejected': '#BE123C',
                 'refunded': '#16A34A', 'closed': '#64748B'}
        tone = tones.get(obj.status, '#64748B')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'font-size:11px;font-weight:600;color:{};background:{}33">{}</span>',
            tone, tone, obj.get_status_display(),
        )

    def _set_status(self, request, queryset, status):
        updated = queryset.exclude(status=status).update(
            status=status,
            processed_by=request.user,
            processed_at=timezone.now(),
        )
        self.message_user(request, f'{updated} return request(s) updated.')

    @admin.action(description='Approve selected return requests')
    def approve_returns(self, request, queryset):
        self._set_status(request, queryset, ReturnRequest.Status.APPROVED)

    @admin.action(description='Reject selected return requests')
    def reject_returns(self, request, queryset):
        self._set_status(request, queryset, ReturnRequest.Status.REJECTED)

    @admin.action(description='Mark selected return requests refunded')
    def mark_refunded(self, request, queryset):
        self._set_status(request, queryset, ReturnRequest.Status.REFUNDED)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'return_request', 'amount', 'method', 'status_badge', 'transaction_id', 'created_at']
    list_filter = ['status', 'method', 'created_at']
    search_fields = ['order__id', 'transaction_id', 'reason']
    list_select_related = ['order', 'return_request', 'initiated_by']
    raw_id_fields = ['order', 'return_request', 'initiated_by']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']
    actions = [
        'mark_as_processing',
        'mark_as_completed',
        'mark_as_failed',
        export_as_csv_action(
            description='Export selected refunds as CSV',
            fields=['id', 'order', 'return_request', 'amount', 'method', 'status',
                    'transaction_id', 'reason', 'created_at', 'processed_at'],
        ),
    ]

    @admin.display(description='Status')
    def status_badge(self, obj):
        tones = {'pending': '#CA8A04', 'processing': '#0E7490', 'completed': '#16A34A', 'failed': '#BE123C'}
        tone = tones.get(obj.status, '#64748B')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'font-size:11px;font-weight:600;color:{};background:{}33">{}</span>',
            tone, tone, obj.get_status_display(),
        )

    def _set_status(self, request, queryset, status):
        updated = queryset.exclude(status=status).update(
            status=status,
            processed_at=timezone.now(),
        )
        self.message_user(request, f'{updated} refund(s) updated.')

    @admin.action(description='Mark selected refunds as processing')
    def mark_as_processing(self, request, queryset):
        self._set_status(request, queryset, Refund.Status.PROCESSING)

    @admin.action(description='Mark selected refunds as completed')
    def mark_as_completed(self, request, queryset):
        self._set_status(request, queryset, Refund.Status.COMPLETED)

    @admin.action(description='Mark selected refunds as failed')
    def mark_as_failed(self, request, queryset):
        self._set_status(request, queryset, Refund.Status.FAILED)


@admin.register(OrderAuditLog)
class OrderAuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'from_status', 'to_status', 'action', 'actor', 'created_at']
    list_filter = ['action', 'from_status', 'to_status', 'created_at']
    search_fields = ['order__order_number', 'order__id', 'actor__username', 'note']
    list_select_related = ['order', 'actor']
    raw_id_fields = ['order', 'actor']
    date_hierarchy = 'created_at'
    readonly_fields = ['order', 'from_status', 'to_status', 'action', 'note', 'actor', 'created_at']
    actions = [export_as_csv_action(
        description='Export selected audit entries as CSV',
        fields=['order', 'from_status', 'to_status', 'action', 'note', 'actor', 'created_at'],
    )]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

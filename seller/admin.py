from django.contrib import admin
from django.utils import timezone

from .models import SellerProduct, SellerLedgerEntry, SellerPayout
from .services import fail_payout, mark_payout_paid


@admin.register(SellerProduct)
class SellerProductAdmin(admin.ModelAdmin):
    list_display = ['seller', 'product', 'price', 'quantity', 'deals', 'is_active_seller', 'created_at']
    list_filter = ['is_active_seller', 'deals']
    search_fields = ['seller__shop_name', 'product__name']
    list_select_related = ['seller', 'product']
    list_editable = ['price', 'quantity', 'is_active_seller']


@admin.register(SellerLedgerEntry)
class SellerLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ['seller', 'entry_type', 'gross_amount', 'commission_amount', 'net_amount', 'status', 'payout', 'created_at']
    list_filter = ['entry_type', 'status', 'created_at']
    search_fields = ['seller__shop_name', 'seller__user__username', 'reference', 'order_item__product__name']
    list_select_related = ['seller', 'order_item__product', 'payout']
    date_hierarchy = 'created_at'
    readonly_fields = ['seller', 'order_item', 'entry_type', 'gross_amount', 'commission_rate', 'commission_amount', 'net_amount', 'created_at']


@admin.register(SellerPayout)
class SellerPayoutAdmin(admin.ModelAdmin):
    list_display = ['seller', 'amount', 'status', 'reference', 'initiated_by', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at']
    search_fields = ['seller__shop_name', 'seller__user__username', 'reference', 'notes']
    list_select_related = ['seller', 'initiated_by']
    readonly_fields = ['seller', 'amount', 'status', 'initiated_by', 'created_at', 'updated_at']
    actions = ['mark_paid', 'mark_failed']

    @admin.action(description='Mark selected payouts as paid')
    def mark_paid(self, request, queryset):
        count = 0
        for payout in queryset.filter(status=SellerPayout.Status.PROCESSING):
            mark_payout_paid(payout, actor=request.user, reference=payout.reference)
            count += 1
        self.message_user(request, f'{count} payout(s) marked paid.')

    @admin.action(description='Fail selected payouts (release funds back)')
    def mark_failed(self, request, queryset):
        count = 0
        for payout in queryset.filter(status=SellerPayout.Status.PROCESSING):
            fail_payout(payout, actor=request.user, note='Marked failed from admin.')
            count += 1
        self.message_user(request, f'{count} payout(s) marked failed; funds released.')

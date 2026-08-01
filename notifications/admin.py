from django.contrib import admin

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'recipient', 'role', 'category', 'is_read', 'created_at']
    list_filter = ['role', 'category', 'is_read', 'created_at']
    search_fields = ['title', 'message', 'recipient__username']
    readonly_fields = ['created_at']
    list_select_related = ['recipient']
    actions = ['mark_read', 'mark_unread']

    @admin.action(description='Mark selected as read')
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description='Mark selected as unread')
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'order_enabled', 'payment_enabled', 'shipping_enabled',
                    'deal_enabled', 'review_enabled', 'account_enabled',
                    'system_enabled', 'promo_enabled', 'email_enabled']
    list_filter = ['order_enabled', 'payment_enabled', 'shipping_enabled',
                   'deal_enabled', 'review_enabled', 'account_enabled',
                   'system_enabled', 'promo_enabled']
    search_fields = ['user__username', 'user__email']

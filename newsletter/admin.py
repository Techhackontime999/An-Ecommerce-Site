from django.contrib import admin, messages

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'is_confirmed', 'confirmed_at', 'created_at')
    list_filter = ('is_active', 'is_confirmed', 'created_at')
    search_fields = ('email',)
    ordering = ('-created_at',)
    list_editable = ('is_active',)

    actions = ['confirm_subscribers', 'deactivate_subscribers', 'reactivate_subscribers']

    @admin.action(description='Confirm selected subscribers (double opt-in)')
    def confirm_subscribers(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_confirmed=False).update(
            is_confirmed=True, is_active=True, confirmed_at=timezone.now(),
        )
        self.message_user(request, f'{count} subscriber(s) confirmed.', messages.SUCCESS)

    @admin.action(description='Deactivate selected subscribers')
    def deactivate_subscribers(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} subscriber(s) deactivated.', messages.SUCCESS)

    @admin.action(description='Reactivate selected subscribers')
    def reactivate_subscribers(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(is_confirmed=True).update(is_active=True)
        self.message_user(request, f'{count} confirmed subscriber(s) reactivated.', messages.SUCCESS)

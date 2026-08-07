from django.contrib import admin, messages

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email',)
    ordering = ('-created_at',)
    list_editable = ('is_active',)

    actions = ['deactivate_subscribers', 'reactivate_subscribers']

    @admin.action(description='Deactivate selected subscribers')
    def deactivate_subscribers(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} subscriber(s) deactivated.', messages.SUCCESS)

    @admin.action(description='Reactivate selected subscribers')
    def reactivate_subscribers(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} subscriber(s) reactivated.', messages.SUCCESS)

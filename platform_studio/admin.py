from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'label', 'group', 'field_type', 'value_preview', 'is_active', 'updated_at')
    list_filter = ('group', 'field_type', 'is_active')
    search_fields = ('key', 'label', 'value')
    list_editable = ('is_active',)
    ordering = ('group', 'ordering', 'key')
    fieldsets = (
        (None, {
            'fields': ('key', 'label', 'group', 'field_type'),
        }),
        ('Value', {
            'fields': ('value', 'help_text'),
        }),
    )
    readonly_fields = ('key',)

    def value_preview(self, obj):
        preview = obj.value or '(default)'
        if obj.field_type == 'boolean':
            preview = 'Yes' if obj.value in ('1', 'true') else ('No' if obj.value in ('0', 'false') else preview)
        if len(preview) > 60:
            preview = preview[:57] + '...'
        return format_html('<code>{}</code>', preview)

    value_preview.short_description = 'Value'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['studio_url'] = reverse('admin:platform_studio')
        return super().changelist_view(request, extra_context=extra_context)

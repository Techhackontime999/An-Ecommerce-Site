from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import LoaderConfig


@admin.register(LoaderConfig)
class LoaderConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'enabled', 'initial_type', 'navigation_type', 'version', 'updated_at')
    list_editable = ('enabled',)
    readonly_fields = ('version', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('enabled',),
        }),
        ('Basic', {
            'fields': ('initial_type', 'navigation_type', 'logo_image', 'logo_text',
                       'background_color', 'accent_color', 'duration_ms',
                       'exit_animation', 'show_on'),
        }),
        ('Display', {
            'fields': ('device_desktop', 'device_tablet', 'device_mobile'),
        }),
        ('Performance', {
            'fields': ('lightweight_mobile', 'respect_reduced_motion', 'network_fallback'),
        }),
        ('System', {
            'classes': ('collapse',),
            'fields': ('version', 'updated_at'),
        }),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['studio_url'] = reverse('admin:loader_studio')
        return super().changelist_view(request, extra_context=extra_context)

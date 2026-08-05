from django.conf import settings
from django.contrib import admin
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.html import format_html

from core.admin_actions import export_as_csv_action
from .models import ContactMessage

STATUS_TONES = {
    ContactMessage.Status.NEW: '#CA8A04',
    ContactMessage.Status.IN_PROGRESS: '#0E7490',
    ContactMessage.Status.RESOLVED: '#16A34A',
    ContactMessage.Status.CLOSED: '#64748B',
}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'status_badge', 'handled_by', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message', 'reply']
    list_filter = ['status', 'handled_at', 'created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at', 'replied_at', 'handled_at']
    list_select_related = ['handled_by']
    actions = [
        'mark_in_progress',
        'mark_resolved',
        'mark_closed',
        'send_reply_email',
        export_as_csv_action(
            description='Export selected messages as CSV',
            fields=['id', 'name', 'email', 'subject', 'message', 'status',
                    'handled_by', 'reply', 'replied_at', 'handled_at', 'created_at'],
        ),
    ]

    @admin.display(description='Status')
    def status_badge(self, obj):
        tone = STATUS_TONES.get(obj.status, '#64748B')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'font-size:11px;font-weight:600;color:{};background:{}33">{}</span>',
            tone, tone, obj.get_status_display(),
        )

    def _set_status(self, request, queryset, status):
        updated = 0
        for msg in queryset:
            if msg.status == status and msg.handled_by:
                continue
            msg.status = status
            msg.handled_by = request.user
            msg.handled_at = timezone.now()
            msg.save(update_fields=['status', 'handled_by', 'handled_at'])
            updated += 1
        self.message_user(request, f'{updated} message(s) updated.')

    @admin.action(description='Mark selected as in progress')
    def mark_in_progress(self, request, queryset):
        self._set_status(request, queryset, ContactMessage.Status.IN_PROGRESS)

    @admin.action(description='Mark selected as resolved')
    def mark_resolved(self, request, queryset):
        self._set_status(request, queryset, ContactMessage.Status.RESOLVED)

    @admin.action(description='Mark selected as closed')
    def mark_closed(self, request, queryset):
        self._set_status(request, queryset, ContactMessage.Status.CLOSED)

    @admin.action(description='Send reply email to selected')
    def send_reply_email(self, request, queryset):
        sent = 0
        skipped = 0
        for msg in queryset:
            if not msg.reply.strip():
                skipped += 1
                continue
            try:
                send_mail(
                    f'Re: {msg.subject}',
                    f'Dear {msg.name},\n\n{msg.reply}\n\n— Shop-Seed Support',
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'Shop-Seed <no-reply@shop-seed.com>'),
                    [msg.email],
                    fail_silently=False,
                )
            except Exception:
                skipped += 1
                continue
            msg.replied_at = timezone.now()
            msg.status = ContactMessage.Status.RESOLVED
            msg.handled_by = request.user
            msg.handled_at = timezone.now()
            msg.save(update_fields=['replied_at', 'status', 'handled_by', 'handled_at'])
            sent += 1
        msg = f'{sent} reply email(s) sent.'
        if skipped:
            msg += f' {skipped} skipped (empty reply or send failure).'
        self.message_user(request, msg)

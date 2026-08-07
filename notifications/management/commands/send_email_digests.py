"""Send a daily email digest of unread notifications to opted-in users.

Users must have ``NotificationPreference.email_enabled`` turned on in
:mod:`notifications.views.notification_settings`. Only notifications that have
not yet been emailed and are still unread are included. Delivered notifications
are stamped with ``emailed_at`` so they are never sent twice.

Schedule this once per day, e.g. on Render add a cron/worker that runs::

    python manage.py send_email_digests
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.emails import send_notification_digest
from notifications.models import Notification


class Command(BaseCommand):
    help = 'Email unread notification digests to users with email_enabled=True.'

    def handle(self, *args, **options):
        sent = 0
        users = (
            User.objects.filter(
                is_active=True,
                notification_preference__email_enabled=True,
            )
            .exclude(email='')
            .iterator(chunk_size=500)
        )
        for user in users:
            notifications = list(
                Notification.objects.filter(
                    recipient=user,
                    is_read=False,
                    emailed_at__isnull=True,
                ).order_by('-created_at')[:20]
            )
            if not notifications:
                continue
            if send_notification_digest(user, notifications):
                Notification.objects.filter(id__in=[n.id for n in notifications]).update(
                    emailed_at=timezone.now(),
                )
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} notification digest email(s).'))

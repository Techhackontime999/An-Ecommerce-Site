"""Scheduled courier tracking sync.

Polls the courier APIs for the newest tracking events of active shipments and
applies them to the unified timeline. Designed to be run on a schedule (cron /
Celery beat / Render cron) rather than from request handling:

    manage.py sync_tracking_status [--limit 100] [--min-age-hours 1]

Only shipments that are still moving (not delivered / cancelled / returned /
lost / damaged) and that have a courier AWB are touched, so the job stays
idempotent and cheap.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from logistics.constants import ShipmentStatus
from logistics.models import Shipment
from logistics.services.fulfillment import FulfillmentService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pull the latest tracking status for in-flight shipments.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100, help='Max shipments to poll (default 100).')
        parser.add_argument(
            '--min-age-hours', type=int, default=1,
            help='Only poll shipments last tracked at least this many hours ago (default 1).',
        )

    def handle(self, *args, **options):
        limit = max(1, int(options['limit']))
        min_age = timedelta(hours=max(0, int(options['min_age_hours'])))

        cutoff = timezone.now() - min_age
        shipments = (
            Shipment.objects.filter(
                status__in=ShipmentStatus.TIMELINE,
                courier__isnull=False,
            )
            .exclude(status__in=ShipmentStatus.TERMINAL)
            .exclude(tracking_number='')
            .exclude(tracking_number__isnull=True)
            .filter(
                models.Q(last_tracked_at__isnull=True, created_at__lte=cutoff)
                | models.Q(last_tracked_at__lte=cutoff)
            )
            .order_by('last_tracked_at')
            .select_related('courier')[:limit]
        )

        total = 0
        updated = 0
        failed = 0
        for shipment in shipments:
            total += 1
            try:
                new_events = FulfillmentService.track(shipment) or []
            except Exception as exc:  # noqa: BLE001 - one bad shipment must not kill the batch
                failed += 1
                logger.warning('Tracking sync failed for %s: %s', shipment.shipment_number, exc)
                continue
            if new_events:
                updated += 1
                self.stdout.write(
                    f'  {shipment.shipment_number}: {len(new_events)} event(s) '
                    f'→ {shipment.status}'
                )

        self.stdout.write(self.style.SUCCESS(
            f'Tracking sync finished: {updated}/{total} shipment(s) updated, '
            f'{failed} failed.'
        ))

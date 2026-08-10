"""Safety-net job reconciliation.

Re-arms jobs the worker cannot self-heal so the queue keeps moving even if
every worker was down at the wrong moment:

- ``running`` jobs whose lease expired (crashed worker) are requeued.
- Optionally re-arms ``dead`` jobs for a second chance (--requeue-dead).

Run from cron every few minutes::

    python manage.py reconcile_jobs
    python manage.py reconcile_jobs --requeue-dead
"""

from django.core.management.base import BaseCommand

from jobs.models import Job
from jobs.services import enqueue, requeue_stuck_jobs


class Command(BaseCommand):
    help = 'Re-arm stuck or dead async jobs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--requeue-dead', action='store_true',
            help='Also re-enqueue jobs that exhausted their retries (dead).',
        )

    def handle(self, *args, **options):
        stuck = requeue_stuck_jobs()
        self.stdout.write(f'{stuck} stuck job(s) requeued.')

        requeued_dead = 0
        if options['requeue_dead']:
            for job in Job.objects.filter(status=Job.Status.DEAD).order_by('created_at')[:500]:
                enqueue(
                    job.kind,
                    job.payload,
                    max_attempts=job.max_attempts,
                    dedupe_key=job.dedupe_key,
                )
                requeued_dead += 1
            self.stdout.write(f'{requeued_dead} dead job(s) requeued for another attempt.')

        self.stdout.write(self.style.SUCCESS('Job reconciliation complete.'))

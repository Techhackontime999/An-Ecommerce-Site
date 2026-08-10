"""Long-running async worker for the DB-backed job queue.

Processes jobs created by ``jobs.services.enqueue`` (emails, fulfilment,
gateway refunds). Claims are compare-and-set against the DB so several workers
can run in parallel; leases time crashed jobs back into the queue; failures
retry with exponential backoff before going ``dead``.

Run on Render as a background worker (or from cron with ``--once``)::

    python manage.py run_worker --poll 5 --limit 25
    python manage.py run_worker --once --limit 200
"""

import logging
import signal
import time

from django.core.management.base import BaseCommand

from jobs.handlers import RetryableJobError, get_handler
from jobs.services import claim_due_jobs, mark_succeeded, retry_or_dead

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process queued async jobs (emails, fulfilment, refunds).'

    def add_arguments(self, parser):
        parser.add_argument('--poll', type=float, default=5, help='Seconds between polls (default 5).')
        parser.add_argument('--limit', type=int, default=25, help='Max jobs claimed per poll (default 25).')
        parser.add_argument('--once', action='store_true', help='Process a single batch then exit (cron-friendly).')
        parser.add_argument('--max-runtime', type=int, default=0, help='Exit after this many seconds (0 = run forever).')

    def handle(self, *args, **options):
        poll = max(0.5, float(options['poll']))
        limit = max(1, int(options['limit']))
        once = options['once']
        max_runtime = max(0, int(options['max_runtime']))

        self._stop = False
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
        except ValueError:  # pragma: no cover - non-main thread / restricted env
            pass

        started = time.monotonic()
        processed = 0
        while not self._stop:
            jobs = claim_due_jobs(limit)
            for job in jobs:
                if self._stop:
                    break
                self._execute(job)
                processed += 1
            if once:
                break
            if max_runtime and (time.monotonic() - started) > max_runtime:
                break
            if not jobs:
                time.sleep(poll)

        self.stdout.write(self.style.SUCCESS(f'Worker stopped after {processed} job(s).'))

    def _execute(self, job):
        handler = get_handler(job.kind)
        if handler is None:
            retry_or_dead(job, f'No handler registered for job kind {job.kind!r}')
            return
        try:
            result = handler(job.payload)
        except RetryableJobError as exc:
            retry_or_dead(job, str(exc))
        except Exception as exc:  # noqa: BLE001 - one bad job must not kill the worker
            logger.exception('Job %s (%s) raised %s', job.pk, job.kind, type(exc).__name__)
            retry_or_dead(job, f'{type(exc).__name__}: {exc}')
        else:
            mark_succeeded(job)
            self.stdout.write(f'  job {job.pk} [{job.kind}] ok: {result}')

    def _handle_signal(self, signum, frame):  # noqa: ARG002 - signal handler signature
        self._stop = True

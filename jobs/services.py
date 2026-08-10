"""Queue mechanics: enqueue, claim, retry, and reconciliation helpers.

The worker is *at-least-once*: a crash between claim and completion, or a
lease that expires while a job is still running, can re-run a handler. Handlers
must therefore be idempotent (duplicate emails are acceptable, ``refund_payment``
returns ``already_refunded``, fulfilment skips shipments it already created).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import Job

logger = logging.getLogger(__name__)


def lease_seconds():
    return max(1, int(getattr(settings, 'JOB_LEASE_SECONDS', 300)))


def backoff_seconds():
    return max(0, int(getattr(settings, 'JOB_BACKOFF_SECONDS', 30)))


def enqueue(kind, payload=None, *, run_at=None, max_attempts=None, dedupe_key=None):
    """Queue a job for the async worker. Returns the created ``Job``.

    When ``dedupe_key`` is given and an identical job is still pending/running,
    that job is returned instead of creating a duplicate — so a double-delivered
    webhook or callback can never queue the same side effect twice. Terminal
    jobs (succeeded/failed/dead) do not block re-enqueueing.
    """
    payload = dict(payload or {})
    if dedupe_key:
        existing = Job.objects.filter(
            dedupe_key=dedupe_key,
            status__in=(Job.Status.PENDING, Job.Status.RUNNING),
        ).first()
        if existing is not None:
            return existing
    run_at = run_at or timezone.now()
    return Job.objects.create(
        kind=kind,
        payload=payload,
        run_at=run_at,
        next_run_at=run_at,
        max_attempts=max_attempts or Job.default_max_attempts(),
        dedupe_key=dedupe_key or None,
    )


def claim_due_jobs(limit=25):
    """Atomically claim up to ``limit`` jobs that are due.

    Covers new work (``pending`` and ``next_run_at`` reached) and crash recovery
    (``running`` jobs whose lease expired). Each claim is a compare-and-set
    UPDATE guarded on the job's current status, so multiple workers can run in
    parallel and never execute the same job at the same moment.

    Returns the list of claimed ``Job`` instances (status=running, lease held).
    """
    now = timezone.now()
    candidates = (
        Job.objects.filter(
            Q(status=Job.Status.PENDING, next_run_at__lte=now)
            | Q(status=Job.Status.RUNNING, locked_until__lte=now)
        )
        .order_by('next_run_at', 'id')[:limit]
    )
    claimed = []
    for job in candidates:
        if _try_claim(job, now):
            job.refresh_from_db()
            claimed.append(job)
    return claimed


def _try_claim(job, now):
    qs = Job.objects.filter(pk=job.pk, status=job.status)
    if job.status == Job.Status.PENDING:
        qs = qs.filter(next_run_at__lte=now)
    else:
        qs = qs.filter(locked_until__lte=now)
    updated = qs.update(
        status=Job.Status.RUNNING,
        attempts=job.attempts + 1,
        last_run_at=now,
        locked_until=now + timedelta(seconds=lease_seconds()),
        updated_at=now,
    )
    return updated == 1


def mark_succeeded(job):
    Job.objects.filter(pk=job.pk).update(
        status=Job.Status.SUCCEEDED,
        locked_until=None,
        last_error='',
        updated_at=timezone.now(),
    )


def retry_or_dead(job, error):
    """After a failed attempt, either schedule a backoff retry or give up.

    ``job.attempts`` already counts the failed run (it was incremented on
    claim). Once attempts >= max_attempts the job is marked ``dead`` and left
    in the admin for manual review.
    """
    now = timezone.now()
    if job.attempts >= job.max_attempts:
        Job.objects.filter(pk=job.pk).update(
            status=Job.Status.DEAD,
            locked_until=None,
            last_error=error,
            updated_at=now,
        )
        logger.error(
            'Job %s (%s) exhausted %d attempt(s): %s',
            job.pk, job.kind, job.max_attempts, error,
        )
        return
    backoff = backoff_seconds() * (2 ** (job.attempts - 1))
    run_at = now + timedelta(seconds=backoff)
    Job.objects.filter(pk=job.pk).update(
        status=Job.Status.PENDING,
        run_at=run_at,
        next_run_at=run_at,
        locked_until=None,
        last_error=error,
        updated_at=now,
    )
    logger.warning(
        'Job %s (%s) attempt %d/%d failed: %s — retrying in %ds',
        job.pk, job.kind, job.attempts, job.max_attempts, error, backoff,
    )


def requeue_stuck_jobs():
    """Re-arm jobs stranded in ``running`` by a crashed worker.

    ``claim_due_jobs`` already reclaims expired leases, so this is a safety net
    for the scheduled ``reconcile_jobs`` cron that runs even when no worker is
    alive. Returns the number of jobs requeued.
    """
    return Job.objects.filter(
        status=Job.Status.RUNNING,
        locked_until__lte=timezone.now(),
    ).update(status=Job.Status.PENDING, locked_until=None, updated_at=timezone.now())

"""Durable, DB-backed async job queue.

Requests that touch slow external systems (SMTP, courier APIs, payment
gateway refunds) enqueue a ``Job`` here instead of blocking the HTTP request.
A worker process polls for due jobs, claims them atomically, runs an
idempotent handler and — on failure — retries with exponential backoff before
giving up and marking the job ``dead`` for manual review.

Why a DB-backed queue instead of Celery/Redis?
-----------------------------------------------
The store deploys on Render's free plan where Redis is optional and the
codebase already schedules background work as Django management commands.
A Job row in Postgres gives at-least-once delivery, crash-safe leases and
retry/backoff without any new infrastructure; ``run_worker`` can be replaced
by Celery later without changing the call sites.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Job(models.Model):
    """A single unit of async work (one email, one fulfilment run, ...)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        DEAD = 'dead', 'Dead'

    kind = models.CharField(
        max_length=50,
        db_index=True,
        help_text='Handler key, e.g. "send_email", "fulfil_order", "refund_payment".',
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveIntegerField(
        default=0,
        help_text='Number of times the worker has claimed this job.',
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        help_text='Giving up: attempts >= max_attempts moves the job to dead.',
    )
    run_at = models.DateTimeField(
        default=timezone.now,
        help_text='Earliest time this job may run.',
    )
    next_run_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text='When the worker should pick this up next (drives retry backoff).',
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Lease held by a worker; another worker may reclaim the job after this.',
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    dedupe_key = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text='Optional idempotency key: an identical in-flight job is not queued twice.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('next_run_at', 'id')
        indexes = [
            models.Index(fields=['status', 'next_run_at']),
        ]

    def __str__(self):
        return f'Job {self.pk} [{self.kind}] ({self.status})'

    @property
    def is_terminal(self):
        return self.status in (self.Status.SUCCEEDED, self.Status.FAILED, self.Status.DEAD)

    @staticmethod
    def default_max_attempts():
        return max(1, int(getattr(settings, 'JOB_MAX_ATTEMPTS', 5)))

"""Tests for the DB-backed async job queue."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from jobs.handlers import RetryableJobError, register
from jobs.models import Job
from jobs.services import (
    claim_due_jobs,
    enqueue,
    mark_succeeded,
    requeue_stuck_jobs,
    retry_or_dead,
)
from jobs.management.commands.run_worker import Command as RunWorkerCommand


class EnqueueTests(TestCase):
    def test_creates_pending_job_with_defaults(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        self.assertEqual(job.kind, 'send_email')
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertEqual(job.payload, {'kind': 'order_confirmation', 'order_id': 1})
        self.assertEqual(job.attempts, 0)
        self.assertEqual(job.max_attempts, Job.default_max_attempts())

    def test_dedupe_skips_duplicate_in_flight_jobs(self):
        first = enqueue('refund_payment', {'payment_id': 9}, dedupe_key='refund-payment:9')
        second = enqueue('refund_payment', {'payment_id': 9}, dedupe_key='refund-payment:9')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Job.objects.count(), 1)

    def test_dedupe_allows_requeue_after_terminal(self):
        job = enqueue('refund_payment', {'payment_id': 9}, dedupe_key='refund-payment:9')
        mark_succeeded(job)
        retry = enqueue('refund_payment', {'payment_id': 9}, dedupe_key='refund-payment:9')
        self.assertNotEqual(job.pk, retry.pk)
        self.assertEqual(Job.objects.count(), 2)

    def test_future_run_at_not_claimed(self):
        enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1},
                run_at=timezone.now() + timedelta(hours=1))
        self.assertEqual(claim_due_jobs(10), [])
        self.assertEqual(Job.objects.filter(status=Job.Status.PENDING).count(), 1)


class ClaimTests(TestCase):
    def test_claim_marks_running_and_holds_lease(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claimed = claim_due_jobs(10)
        self.assertEqual(len(claimed), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.RUNNING)
        self.assertEqual(job.attempts, 1)
        self.assertIsNotNone(job.locked_until)
        self.assertGreater(job.locked_until, timezone.now())
        # Already claimed → not claimed a second time.
        self.assertEqual(claim_due_jobs(10), [])

    def test_claimed_job_is_not_claimed_by_second_worker(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claim_due_jobs(10)
        self.assertEqual(claim_due_jobs(10), [])

    def test_expired_lease_is_reclaimed(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claim_due_jobs(10)
        Job.objects.filter(pk=job.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        claimed = claim_due_jobs(10)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0].pk, job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.RUNNING)
        self.assertEqual(job.attempts, 2)


class RetryTests(TestCase):
    def test_retry_or_dead_schedules_backoff(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claim_due_jobs(10)
        job.refresh_from_db()
        retry_or_dead(job, 'boom')
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertIn('boom', job.last_error)
        self.assertGreater(job.next_run_at, timezone.now())

    def test_retry_or_dead_gives_up_at_max_attempts(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1}, max_attempts=2)
        with self.settings(JOB_BACKOFF_SECONDS=0):
            for _ in range(2):
                claim_due_jobs(10)
                job.refresh_from_db()
                retry_or_dead(job, 'boom')
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.DEAD)
        self.assertIn('boom', job.last_error)


class RequeueStuckTests(TestCase):
    def test_requeues_expired_running_jobs(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claim_due_jobs(10)
        Job.objects.filter(pk=job.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
        self.assertEqual(requeue_stuck_jobs(), 1)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.PENDING)
        self.assertIsNone(job.locked_until)

    def test_leaves_fresh_leases_alone(self):
        job = enqueue('send_email', {'kind': 'order_confirmation', 'order_id': 1})
        claim_due_jobs(10)
        self.assertEqual(requeue_stuck_jobs(), 0)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.RUNNING)


class WorkerTests(TestCase):
    def test_worker_runs_handler_and_marks_succeeded(self):
        calls = {}

        @register('test_tracked_handler')
        def handler(payload):
            calls['value'] = payload['value']
            return 'done'

        job = enqueue('test_tracked_handler', {'value': 42})
        command = RunWorkerCommand(stdout=self._capture())
        command.handle(once=True, poll=0.5, limit=10, max_runtime=0)
        job.refresh_from_db()
        self.assertEqual(calls.get('value'), 42)
        self.assertEqual(job.status, Job.Status.SUCCEEDED)

    def test_worker_retries_then_succeeds_on_transient_failure(self):
        attempts = []

        @register('test_flaky_handler')
        def handler(payload):
            attempts.append(1)
            if len(attempts) < 2:
                raise RetryableJobError('transient')
            return 'eventually ok'

        job = enqueue('test_flaky_handler', {}, max_attempts=3)
        command = RunWorkerCommand(stdout=self._capture())
        with self.settings(JOB_BACKOFF_SECONDS=0):
            command.handle(once=True, poll=0, limit=10, max_runtime=0)
            job.refresh_from_db()
            self.assertEqual(job.status, Job.Status.PENDING)
            self.assertIn('transient', job.last_error)

            command.handle(once=True, poll=0, limit=10, max_runtime=0)
            job.refresh_from_db()
            self.assertEqual(job.status, Job.Status.SUCCEEDED)
        self.assertEqual(len(attempts), 2)

    def test_worker_deads_when_handler_unavailable(self):
        job = enqueue('no_such_kind', {}, max_attempts=1)
        command = RunWorkerCommand(stdout=self._capture())
        command.handle(once=True, poll=0, limit=10, max_runtime=0)
        job.refresh_from_db()
        self.assertEqual(job.status, Job.Status.DEAD)
        self.assertIn('No handler registered', job.last_error)

    @staticmethod
    def _capture():
        from io import StringIO
        return StringIO()

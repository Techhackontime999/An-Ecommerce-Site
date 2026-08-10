from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'kind', 'status', 'attempts', 'max_attempts', 'next_run_at', 'locked_until', 'created_at']
    list_filter = ['status', 'kind', 'created_at']
    search_fields = ['kind', 'payload', 'last_error']
    date_hierarchy = 'created_at'
    readonly_fields = ['kind', 'payload', 'status', 'attempts', 'max_attempts',
                       'run_at', 'next_run_at', 'locked_until', 'last_run_at',
                       'last_error', 'dedupe_key', 'created_at', 'updated_at']
    actions = ['requeue_dead_jobs']

    @admin.action(description='Requeue selected dead jobs')
    def requeue_dead_jobs(self, request, queryset):
        from jobs.services import enqueue
        requeued = 0
        for job in queryset.filter(status=Job.Status.DEAD):
            enqueue(
                job.kind,
                job.payload,
                max_attempts=job.max_attempts,
                dedupe_key=job.dedupe_key,
            )
            requeued += 1
        self.message_user(request, f'{requeued} dead job(s) requeued.')

    def has_add_permission(self, request):
        return False

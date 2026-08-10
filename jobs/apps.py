from django.apps import AppConfig


class JobsConfig(AppConfig):
    name = 'jobs'
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = 'Async Jobs'

from django.apps import AppConfig


class LogisticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logistics'
    verbose_name = 'Logistics Management System'

    def ready(self):
        # Importing the courier modules registers every adapter in the registry.
        from logistics.couriers import registry  # noqa: F401
        from logistics.couriers import mock  # noqa: F401
        from logistics.couriers import delhivery  # noqa: F401

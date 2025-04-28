from django.apps import AppConfig
from django.contrib.auth.models import Group


class ShopConfig(AppConfig):
    name = 'shop'


    def ready(self):
        # Create 'customers' group if it doesn't exist
        from django.db.models import signals
        from django.contrib.auth.models import Group

        # Ensure the group is created when the app is ready
        group, created = Group.objects.get_or_create(name='customers')
        group, created = Group.objects.get_or_create(name='sellers')
        group, created = Group.objects.get_or_create(name='webadmin')

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Create default groups'

    def handle(self, *args, **kwargs):
        group_names = ['customers', 'sellers', 'admins']  # Your 3 groups
        
        for name in group_names:
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Group '{name}' created successfully."))
            else:
                self.stdout.write(self.style.WARNING(f"Group '{name}' already exists."))
 # signal to add group customers
            customers_group, created = Group.objects.get_or_create(name='customers')
            customers_group.user_set.add(user)
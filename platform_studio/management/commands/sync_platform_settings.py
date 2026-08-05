from django.core.management.base import BaseCommand

from platform_studio.utils import seed_defaults


class Command(BaseCommand):
    help = 'Create a SiteSetting row for every Platform Studio setting (does not overwrite existing values).'

    def handle(self, *args, **options):
        seed_defaults()
        from platform_studio.models import SiteSetting

        self.stdout.write(self.style.SUCCESS(
            f'Platform Studio defaults synced. {SiteSetting.objects.count()} setting(s) stored.'
        ))

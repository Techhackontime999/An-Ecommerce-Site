from django.core.management.base import BaseCommand

from preferences.exchange import get_rates, rates_updated_at


class Command(BaseCommand):
    help = 'Refresh the cached live exchange rates used for price conversion.'

    def handle(self, *args, **options):
        rates = get_rates(refresh=True)
        updated = rates_updated_at()
        self.stdout.write(self.style.SUCCESS(
            f'Refreshed {len(rates)} currency rates '
            f'(last successful API update: {updated}).'
        ))

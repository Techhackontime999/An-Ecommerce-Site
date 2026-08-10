from django.core.management.base import BaseCommand, CommandError

from accounts.models import SellerProfile
from seller.services import reconcile_seller_earnings


class Command(BaseCommand):
    help = (
        'Reconcile seller ledger earnings from paid, delivered orders. '
        'Idempotent: safe to run on any schedule. When --seller is given, only '
        'that seller is reconciled.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--seller', type=int, default=None,
            help='PK of a single SellerProfile to reconcile.',
        )

    def handle(self, *args, **options):
        seller = None
        if options['seller']:
            try:
                seller = SellerProfile.objects.get(pk=options['seller'])
            except SellerProfile.DoesNotExist:
                raise CommandError('No seller with that pk.')

        result = reconcile_seller_earnings(seller)
        scope = f' for {seller.shop_name}' if seller else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'Reconciled{scope}: {result["sale"]} sale entry(ies), '
                f'{result["refund"]} refund entry(ies).'
            )
        )

# from django.db import models
# from shop.models import Product
# from deals.models import Deal
# from accounts.models import SellerProfile
# # Create your models here.

# # this below model is essential for management of same products for different seller and then map this model where you want to display products instead of shop.product model
# class SellerProduct(models.Model):
#     seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE) 
#     product = models.ForeignKey(Product, on_delete=models.CASCADE)       
#     deals = models.ForeignKey(Deal, on_delete=models.CASCADE)     
#     quantity = models.PositiveIntegerField()     
#     price = models.DecimalField(max_digits=10, decimal_places=2)

#     def __str__(self):
#         return f"{self.seller.user.username} - {self.product.name}"                         




from django.db import models
from shop.models import Product
from deals.models import Deal  # adjust import based on your structure
from accounts.models import SellerProfile
from django.utils import timezone

class SellerProduct(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name="seller_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="seller_products")
    deals = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_products")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # This field is_active_seller tells you whether the seller is currently offering the product for sale or not.
    is_active_seller = models.BooleanField(default=True)  # useful for deactivating listings
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('seller', 'product')  # seller can't list same product twice

    def __str__(self):
        return f"{self.seller.shop_name} sells {self.product.name}"


class SellerLedgerEntry(models.Model):
    """Immutable earnings/refund record for a seller.

    Credits (SALE) are created only after the order is paid *and* delivered;
    refunds generate matching REFUND debits so money is never overpaid. A
    payout marks the covered entries PAYOUT_PENDING, then PAID once the admin
    confirms the transfer.
    """

    class EntryType(models.TextChoices):
        SALE = 'sale', 'Sale'
        REFUND = 'refund', 'Refund / clawback'
        ADJUSTMENT = 'adjustment', 'Admin adjustment'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available to pay out'
        PAYOUT_PENDING = 'payout_pending', 'Included in a payout'
        PAID = 'paid', 'Paid'

    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='ledger_entries',
    )
    order_item = models.ForeignKey(
        'order.OrderItem', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='seller_ledger_entries',
    )
    payout = models.ForeignKey(
        'seller.SellerPayout', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
    )
    entry_type = models.CharField(max_length=12, choices=EntryType.choices)
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.AVAILABLE, db_index=True,
    )
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['seller', 'order_item', 'entry_type'],
                condition=models.Q(entry_type__in=['sale', 'refund']),
                name='uniq_sale_refund_per_item',
            ),
        ]

    def __str__(self):
        return f'{self.get_entry_type_display()} {self.net_amount} — {self.seller.shop_name}'


class SellerPayout(models.Model):
    """A batch payout of a seller's available balance to their bank account."""

    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Processing'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'

    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, related_name='payouts',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PROCESSING, db_index=True,
    )
    reference = models.CharField(
        max_length=200, blank=True,
        help_text='Bank/UTR reference entered by the admin when the payout is paid.',
    )
    notes = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='seller_payouts_initiated',
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Payout {self.pk} — {self.seller.shop_name} ({self.amount})'

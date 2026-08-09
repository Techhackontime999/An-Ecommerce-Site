from django.conf import settings
from django.db import models
from order.models import Order


class Payment(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('captured', 'Captured'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_payment_link_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_link_url = models.URLField(max_length=500, blank=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"Payment {self.razorpay_order_id} - {self.order.id}"


class PaymentAuditLog(models.Model):
    """Immutable record of every payment status change.

    Append-only (no ``save`` override is needed because status transitions go
    through the service layer) so any dispute can be traced end-to-end.
    """

    payment = models.ForeignKey(
        Payment, on_delete=models.CASCADE, related_name='audit_logs',
    )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    source = models.CharField(
        max_length=50, blank=True,
        help_text='Where the change originated: callback, webhook, verify, admin, system.',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='payment_audit_logs',
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f'Payment {self.payment_id}: {self.old_status} → {self.new_status}'

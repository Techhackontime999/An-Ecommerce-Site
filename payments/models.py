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
    razorpay_order_id = models.CharField(max_length=255, unique=True)
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

from decimal import Decimal
from django.db import models
from django.utils import timezone
from shop.models import Product, ProductVariant
from django.contrib.auth.models import User


def _generate_order_number(order_id):
    year = timezone.localdate().year
    return 'SEED-{}-{:06d}'.format(year, order_id)


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')  # 👈 Add this line

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, help_text='Delivery contact number')
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, default='India')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    paid = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text='Current fulfilment state of the order.',
    )
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    shipping_method_name = models.CharField(max_length=100, blank=True)
    order_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        editable=False,
        db_index=True,
        help_text='Human-friendly public order reference.',
    )

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return 'Order {}'.format(self.order_number or self.id)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_number:
            self.order_number = _generate_order_number(self.pk)
            self.save(update_fields=['order_number'])

    def get_total_cost(self):
        total = sum(item.get_cost() for item in self.items.all())
        return total + self.shipping_cost

class ReturnRequest(models.Model):
    class Reason(models.TextChoices):
        WRONG_ITEM = 'wrong_item', 'Wrong item received'
        DAMAGED = 'damaged', 'Damaged in transit'
        DEFECTIVE = 'defective', 'Defective / not working'
        NOT_AS_DESCRIBED = 'not_as_described', 'Not as described'
        CHANGED_MIND = 'changed_mind', 'Changed my mind'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        REFUNDED = 'refunded', 'Refunded'
        CLOSED = 'closed', 'Closed'

    order = models.ForeignKey(Order, related_name='return_requests', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='return_requests', on_delete=models.CASCADE)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    processed_by = models.ForeignKey(
        User, null=True, blank=True, related_name='processed_returns',
        on_delete=models.SET_NULL,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-requested_at',)

    def __str__(self):
        return f'Return #{self.id} — Order {self.order.order_number} ({self.get_status_display()})'


class Refund(models.Model):
    class Method(models.TextChoices):
        ORIGINAL_PAYMENT = 'original_payment', 'Original payment method'
        STORE_CREDIT = 'store_credit', 'Store credit'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    order = models.ForeignKey(Order, related_name='refunds', on_delete=models.CASCADE)
    return_request = models.OneToOneField(
        ReturnRequest, null=True, blank=True, related_name='refund',
        on_delete=models.SET_NULL,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.ORIGINAL_PAYMENT)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    reason = models.TextField(blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    initiated_by = models.ForeignKey(
        User, null=True, blank=True, related_name='refunds_initiated',
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Refund #{self.id} — Order {self.order.order_number} ({self.get_status_display()})'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, related_name='order_items',
                                on_delete=models.SET_NULL, null=True, blank=True)
    variant_name = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    deal_applied = models.BooleanField(default=False)  # ✅ New field
    
    def __str__(self):
        return '{}'.format(self.id)

    def get_cost(self):
        return self.price * self.quantity

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class Notification(models.Model):
    """A single notification delivered to one user (or broadcast to a role)."""

    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        SELLER = 'seller', 'Seller'
        ADMIN = 'admin', 'Admin'

    class Category(models.TextChoices):
        ORDER = 'order', 'Order'
        PAYMENT = 'payment', 'Payment'
        SHIPPING = 'shipping', 'Shipping'
        DEAL = 'deal', 'Deals & Promotions'
        REVIEW = 'review', 'Reviews'
        ACCOUNT = 'account', 'Account'
        SYSTEM = 'system', 'System'
        PROMO = 'promo', 'Marketing'

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
        help_text='Target user. Leave empty to broadcast to a whole role.',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        help_text='Audience this notification is meant for.',
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.SYSTEM,
    )
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=30, blank=True, help_text='Font Awesome icon, e.g. "box"')
    is_read = models.BooleanField(default=False)
    emailed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When this notification was included in an email digest.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
        ]

    CATEGORY_ICONS = {
        Category.ORDER: 'box',
        Category.PAYMENT: 'credit-card',
        Category.SHIPPING: 'truck-fast',
        Category.DEAL: 'tags',
        Category.REVIEW: 'star',
        Category.ACCOUNT: 'user-shield',
        Category.SYSTEM: 'bell',
        Category.PROMO: 'gift',
    }

    @property
    def display_icon(self):
        return self.icon or self.CATEGORY_ICONS.get(self.category, 'bell')

    def __str__(self):
        return f'{self.title} ({self.get_role_display()})'

    def get_absolute_url(self):
        if self.link:
            return self.link
        return reverse('notifications:list')


class NotificationPreference(models.Model):
    """Per-user control over which notification categories are delivered."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    order_enabled = models.BooleanField(default=True, verbose_name='Order updates')
    payment_enabled = models.BooleanField(default=True, verbose_name='Payment updates')
    shipping_enabled = models.BooleanField(default=True, verbose_name='Shipping updates')
    deal_enabled = models.BooleanField(default=True, verbose_name='Deals & promotions')
    review_enabled = models.BooleanField(default=True, verbose_name='Reviews & ratings')
    account_enabled = models.BooleanField(default=True, verbose_name='Account security')
    system_enabled = models.BooleanField(default=True, verbose_name='System & service')
    promo_enabled = models.BooleanField(default=True, verbose_name='Marketing offers')
    email_enabled = models.BooleanField(default=False, verbose_name='Email summary')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} notification preferences'

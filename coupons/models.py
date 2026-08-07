from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    discount = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    active = models.BooleanField(default=True)

    # --- Limits -------------------------------------------------------------
    max_uses = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total number of times this coupon may ever be used. Leave blank for unlimited.',
    )
    per_user_limit = models.PositiveIntegerField(
        default=1,
        help_text='Maximum number of orders one customer can apply this coupon to.',
    )
    min_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Minimum cart total (before discount) required to use this coupon.',
    )
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Optional cap on the rupee value of the discount.',
    )

    # --- Scoping ------------------------------------------------------------
    seller = models.ForeignKey(
        'accounts.SellerProfile', null=True, blank=True, on_delete=models.CASCADE,
        related_name='coupons',
        help_text='Restrict this coupon to carts that contain this seller\'s products.',
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='allowed_coupons',
        help_text='Optional whitelist of customers allowed to use this coupon. Empty = everyone.',
    )

    def __str__(self):
        return self.code

    def is_expired(self):
        from django.utils import timezone
        return self.valid_to < timezone.now()

    def used_count(self):
        return self.redemptions.count()

    @property
    def remaining_uses(self):
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.used_count())


class CouponRedemption(models.Model):
    """A durable record of one coupon use. Written at order creation (inside
    the same transaction that locks the coupon row), so global and per-user
    limits are enforced atomically and a coupon can never be double-redeemed
    for the same order."""

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='coupon_redemptions',
    )
    order = models.ForeignKey(
        'order.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='coupon_redemptions',
    )
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-redeemed_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['coupon', 'order'], name='unique_coupon_redemption_per_order',
            ),
        ]

    def __str__(self):
        return f'{self.coupon.code} → {self.user.username} ({self.redeemed_at:%Y-%m-%d})'

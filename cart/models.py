from django.conf import settings
from django.db import models
from shop.models import Product, ProductVariant


class CartItem(models.Model):
    """Database copy of a signed-in user's cart so it survives logout/device change.

    ``key`` mirrors the session cart key (``product_id`` or ``product_id:variant_id``)
    and avoids NULL-uniqueness pitfalls of a nullable variant FK.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='cart_items',
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, null=True, blank=True,
        related_name='cart_items',
    )
    key = models.CharField(max_length=40)
    quantity = models.PositiveIntegerField(default=1)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'key')
        ordering = ('-updated',)

    def __str__(self):
        return f'{self.user.username} — {self.product.name} x{self.quantity}'

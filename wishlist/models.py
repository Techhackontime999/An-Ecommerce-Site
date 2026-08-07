from django.conf import settings
from django.db import models
from shop.models import Product


class WishlistItem(models.Model):
    """A product saved by a user for later (bookmark, no stock reservation)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE,
        related_name='wishlist_items',
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ('-created',)

    def __str__(self):
        return f'{self.user.username} — {self.product.name}'

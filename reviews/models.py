from django.db import models
from django.contrib.auth.models import User
from shop.models import Product
class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 to 5 stars
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'user')  # Prevent multiple reviews per product by the same user

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}★)"


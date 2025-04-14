from django.db import models
from shop.models import Product
from django.utils import timezone

class Deal(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    def __str__(self):
        return f"Deal for {self.product.name}"

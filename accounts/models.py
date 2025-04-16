# accounts/models.py

from django.contrib.auth.models import User
from django.db import models

class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=15, blank=True, null=True)  # Optional GST field

    phone = models.CharField(max_length=15)
    address = models.TextField()
    description = models.TextField(blank=True)
    # add methods to verify seller make it defaut false for testing i do it true
    is_verified = models.BooleanField(default=True)  # Admin verifies sellers
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.shop_name} ({self.user.username})"

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()

    def __str__(self):
        return self.user.username

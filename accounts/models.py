# accounts/models.py

from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify
from django.db.models import Avg

class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    gst_number = models.CharField(max_length=15, blank=True, null=True)  # Optional GST field
    bank_account = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    description = models.TextField(blank=True)
    # add methods to verify seller make it defaut false for testing i do it true
    is_verified = models.BooleanField(default=True)  # Admin verifies sellers
    created_at = models.DateTimeField(auto_now_add=True)
    profile_picture = models.ImageField(upload_to='seller_profiles/', null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
  # ⚠️ temporarily remove unique=True
 

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.shop_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_name} ({self.user.username})"


    # def average_rating(self):
    #     from shop.models import Product
    #     from reviews.models import Review

    #     product_ids = Product.objects.filter(seller=self).values_list('id', flat=True)
    #     avg_rating = Review.objects.filter(product_id__in=product_ids).aggregate(avg=Avg('rating'))['avg']

    #     return round(avg_rating or 0, 2)

    # def total_reviews(self):
    #     from shop.models import Product
    #     from reviews.models import Review

    #     product_ids = Product.objects.filter(seller=self).values_list('id', flat=True)
    #     return Review.objects.filter(product_id__in=product_ids).count()









class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    profile_picture = models.ImageField(upload_to='customer_profiles/', null=True, blank=True)

    def __str__(self):
        return self.user.username

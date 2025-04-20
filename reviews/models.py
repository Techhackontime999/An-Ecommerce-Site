from django.db import models
from django.contrib.auth.models import User
from shop.models import Product

from accounts.models import SellerProfile,CustomerProfile
from django.db.models.signals import post_save
from django.dispatch import receiver

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

    def save(self, *args, **kwargs):
        from .models import SellerReview  # import here to avoid circular import

        super().save(*args, **kwargs)

        # Update seller's rating after saving a product review
        seller = self.product.seller

        # Create or update the seller review
        try:
            customer = CustomerProfile.objects.get(user=self.user)
            SellerReview.objects.update_or_create(
                seller_profile=seller,
                customer=customer,
                defaults={'rating': self.rating}
            )
        except CustomerProfile.DoesNotExist:
            pass  # Skip if CustomerProfile is not found 

        # Now update seller's overall rating
        seller.update_rating()

class SellerReview(models.Model):
        seller_profile=models.ForeignKey(SellerProfile, related_name='seller_reviews', on_delete=models.CASCADE)
        customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE)
        rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
        
        # def update_rating(self):
        #     avg_rating = Product.objects.filter(seller=self.seller_profile).aggregate(Avg('reviews__rating'))
        #     self.rating = avg_rating['reviews__rating__avg'] or 0.00
        #     self.save()

        def save(self, *args, **kwargs):
            super().save(*args, **kwargs)
            self.seller_profile.update_rating()

        def __str__(self):
            return f"{self.seller_profile} ({self.rating}) ({self.customer})"
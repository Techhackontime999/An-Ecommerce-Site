from django.db import models
from django.contrib.auth.models import User
from shop.models import Product

from accounts.models import SellerProfile,CustomerProfile
from django.db.models.signals import post_save
from django.dispatch import receiver


def has_paid_order(user, product):
    from order.models import OrderItem
    return OrderItem.objects.filter(
        order__user=user,
        product=product,
        order__paid=True,
    ).exists()

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


class ProductReview(models.Model):
    MAX_IMAGES = 3

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    class ReportReason(models.TextChoices):
        FAKE = 'fake', 'Fake or fraudulent'
        INAPPROPRIATE = 'inappropriate', 'Inappropriate content'
        WRONG_PRODUCT = 'wrong_product', 'Wrong product'
        BIASED = 'biased', 'Paid or biased'
        OTHER = 'other', 'Other'

    reviewer = models.ForeignKey(
        User,
        related_name='product_reviews',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='product_reviews',
        on_delete=models.CASCADE,
    )
    overall_rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    performance = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    value = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    quality = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)], null=True, blank=True)
    recommendation_rating = models.PositiveSmallIntegerField(default=0, help_text='0–100: how likely you are to recommend this.')
    pros = models.TextField(blank=True)
    cons = models.TextField(blank=True)
    review_text = models.TextField(blank=True)
    verified_purchase = models.BooleanField(default=False)
    is_verified_reviewer = models.BooleanField(default=False)
    helpful_votes = models.ManyToManyField(
        User,
        related_name='helpful_product_reviews',
        blank=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.APPROVED,
        db_index=True,
    )
    image = models.ImageField(upload_to='reviews/%Y/%m/%d', blank=True)
    video_url = models.URLField(blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)
        unique_together = ('product', 'reviewer')
        indexes = [
            models.Index(fields=['product', 'status', '-created']),
        ]

    def __str__(self):
        return f"{self.reviewer} — {self.product} ({self.overall_rating}★)"

    @property
    def helpful_count(self):
        return self.helpful_votes.count()

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    def save(self, *args, **kwargs):
        if self.overall_rating:
            self.performance = self.performance or self.overall_rating
            self.value = self.value or self.overall_rating
            self.quality = self.quality or self.overall_rating
        self.verified_purchase = self._has_paid_order()
        self.is_verified_reviewer = self._is_verified_reviewer()
        super().save(*args, **kwargs)

    def _has_paid_order(self):
        return has_paid_order(self.reviewer, self.product)

    def _is_verified_reviewer(self):
        if self.reviewer.is_staff:
            return True
        return SellerReview.objects.filter(customer__user=self.reviewer).exists()


class ProductReviewImage(models.Model):
    review = models.ForeignKey(
        ProductReview,
        related_name='images',
        on_delete=models.CASCADE,
    )
    image = models.ImageField(upload_to='reviews/%Y/%m/%d')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for review #{self.review_id}"


class ReviewReport(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        DISMISSED = 'dismissed', 'Dismissed'

    review = models.ForeignKey(
        ProductReview,
        related_name='reports',
        on_delete=models.CASCADE,
    )
    reporter = models.ForeignKey(
        User,
        related_name='review_reports',
        on_delete=models.CASCADE,
    )
    reason = models.CharField(max_length=20, choices=ProductReview.ReportReason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"{self.reporter} reported review #{self.review_id}"

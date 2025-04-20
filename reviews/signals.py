from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Review,SellerReview
from accounts.models import SellerProfile,CustomerProfile
from shop.models import Product
@receiver(post_save, sender=Review)
def create_or_update_seller_review(sender, instance, **kwargs):
    product = instance.product
    user = instance.user

    try:
        customer = CustomerProfile.objects.get(user=user)
    except CustomerProfile.DoesNotExist:
        return  # Exit if no customer profile exists for this user

    seller = product.seller

    # Create or update SellerReview
    seller_review, created = SellerReview.objects.update_or_create(
        seller_profile=seller,
        customer=customer,
        defaults={'rating': instance.rating}
    )

@receiver(post_save, sender=Review)
def update_seller_rating(sender, instance, **kwargs):
    if instance.product and instance.product.seller:
        instance.product.seller.update_rating()

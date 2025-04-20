from django.contrib import admin
from .models import Review
from .models import SellerReview


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'product__name', 'comment')

@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ['seller_profile','customer', 'rating']
    search_fields = ['seller_profile__user__username']  # if SellerProfile is linked to a User
    list_filter = ['rating']
    
from django.contrib import admin
from .models import Review, SellerReview


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'stars', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'product__name', 'comment']
    list_select_related = ['user', 'product']
    date_hierarchy = 'created_at'

    def stars(self, obj):
        return '⭐' * obj.rating
    stars.short_description = ''


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ['seller_profile', 'customer', 'rating']
    search_fields = ['seller_profile__user__username', 'customer__username']
    list_filter = ['rating']
    list_select_related = ['seller_profile', 'customer']

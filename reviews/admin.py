from django.contrib import admin
from .models import Review, SellerReview, ProductReview, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'stars', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'product__name', 'comment']
    list_select_related = ['user', 'product']
    date_hierarchy = 'created_at'

    def stars(self, obj):
        return '★' * obj.rating
    stars.short_description = ''


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ['seller_profile', 'customer', 'rating']
    search_fields = ['seller_profile__user__username', 'customer__username']
    list_filter = ['rating']
    list_select_related = ['seller_profile', 'customer']


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('reviewer', 'product', 'overall_rating', 'recommendation_rating', 'verified_purchase', 'is_verified_reviewer', 'status', 'created')
    list_filter = ('status', 'verified_purchase', 'is_verified_reviewer')
    search_fields = ('reviewer__username', 'product__name', 'review_text', 'pros', 'cons')
    list_select_related = ('reviewer', 'product')
    raw_id_fields = ('reviewer', 'product')
    filter_horizontal = ('helpful_votes',)
    actions = ('approve_reviews', 'reject_reviews', 'mark_verified_reviewer')

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(status=ProductReview.Status.APPROVED)
        self.message_user(request, f'{updated} review(s) approved.')

    @admin.action(description='Reject selected reviews')
    def reject_reviews(self, request, queryset):
        updated = queryset.update(status=ProductReview.Status.REJECTED)
        self.message_user(request, f'{updated} review(s) rejected.')

    @admin.action(description='Mark selected reviewers as verified')
    def mark_verified_reviewer(self, request, queryset):
        updated = queryset.update(is_verified_reviewer=True)
        self.message_user(request, f'{updated} review(s) marked verified.')


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ('review', 'reporter', 'reason', 'status', 'created')
    list_filter = ('status', 'reason')
    search_fields = ('review__reviewer__username', 'reporter__username')
    raw_id_fields = ('review', 'reporter')
    actions = ('mark_reviewed', 'dismiss_reports')

    @admin.action(description='Mark selected reports reviewed')
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(status=ReviewReport.Status.REVIEWED)
        self.message_user(request, f'{updated} report(s) marked reviewed.')

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        updated = queryset.update(status=ReviewReport.Status.DISMISSED)
        self.message_user(request, f'{updated} report(s) dismissed.')

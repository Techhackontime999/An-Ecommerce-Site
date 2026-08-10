from django.contrib import admin
from django.urls import reverse

from core.admin_actions import export_as_csv_action
from notifications.services import notify
from .models import SellerReview, ProductReview, ProductReviewImage, ReviewReport


class ProductReviewImageInline(admin.TabularInline):
    model = ProductReviewImage
    extra = 0


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
    inlines = [ProductReviewImageInline]
    actions = ('approve_reviews', 'reject_reviews', 'mark_verified_reviewer', 'export_csv')

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        for review in queryset.select_related('product__seller__user'):
            review.status = ProductReview.Status.APPROVED
            review.save(update_fields=['status', 'updated'])
            seller = getattr(review.product, 'seller', None)
            if seller and seller.user_id and seller.user != review.reviewer:
                notify(
                    seller.user,
                    'review',
                    f'New {review.overall_rating}-star review for {review.product.name}',
                    f'{review.reviewer.username} reviewed your product. See what they said.',
                    link=reverse('reviews:product_review_detail', args=[review.pk]),
                    icon='star',
                )
        self.message_user(request, f'{queryset.count()} review(s) approved.')

    @admin.action(description='Reject selected reviews')
    def reject_reviews(self, request, queryset):
        for review in queryset:
            review.status = ProductReview.Status.REJECTED
            review.save(update_fields=['status', 'updated'])
        self.message_user(request, f'{queryset.count()} review(s) rejected.')

    @admin.action(description='Mark selected reviewers as verified')
    def mark_verified_reviewer(self, request, queryset):
        updated = queryset.update(is_verified_reviewer=True)
        self.message_user(request, f'{updated} review(s) marked verified.')

    export_csv = export_as_csv_action(
        description='Export selected reviews as CSV',
        fields=['id', 'reviewer', 'product', 'overall_rating', 'performance',
                'value', 'quality', 'recommendation_rating', 'verified_purchase',
                'is_verified_reviewer', 'status', 'created'],
    )


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

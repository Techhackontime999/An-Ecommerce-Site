"""Merge the legacy ``Review`` model into ``ProductReview``.

Legacy reviews are copied into ``ProductReview`` (product + reviewer + overall
rating + review text + moderation status), skipping any pair that already has a
modern review so the ``unique_together`` constraint is never violated. After
this runs, the legacy table is dropped by a follow-up migration.
"""

from django.db import migrations


def merge_legacy_reviews(apps, schema_editor):
    Review = apps.get_model('reviews', 'Review')
    ProductReview = apps.get_model('reviews', 'ProductReview')
    SellerReview = apps.get_model('reviews', 'SellerReview')
    OrderItem = apps.get_model('order', 'OrderItem')

    existing = set(
        ProductReview.objects.values_list('product_id', 'reviewer_id'),
    )
    reviewer_verified = set(
        SellerReview.objects.values_list('customer__user_id', flat=True),
    )

    for review in Review.objects.select_related('product', 'user').iterator():
        if (review.product_id, review.user_id) in existing:
            continue
        has_paid = OrderItem.objects.filter(
            order__user_id=review.user_id,
            product_id=review.product_id,
            order__paid=True,
        ).exists()
        ProductReview.objects.create(
            product_id=review.product_id,
            reviewer_id=review.user_id,
            overall_rating=review.rating,
            performance=review.rating,
            value=review.rating,
            quality=review.rating,
            review_text=review.comment,
            verified_purchase=has_paid,
            is_verified_reviewer=review.user.is_staff or review.user_id in reviewer_verified,
            status='approved',
            created=review.created_at,
        )
        existing.add((review.product_id, review.user_id))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0003_productreviewimage'),
    ]

    operations = [
        migrations.RunPython(merge_legacy_reviews, noop),
    ]

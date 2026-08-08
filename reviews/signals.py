# Keep this module importable — signal wiring used to live here.
#
# Seller-review sync is now handled directly in ``ProductReview.save()``
# (see ``sync_seller_review`` in reviews.models); the legacy ``Review`` model
# was merged into ``ProductReview`` and its post_save receivers removed.

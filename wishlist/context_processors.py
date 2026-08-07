def wishlist(request):
    """Context for nav heart badge. Adds ``wishlist_count``."""
    if not request.user.is_authenticated:
        return {'wishlist_count': 0}
    return {'wishlist_count': request.user.wishlist_items.count()}

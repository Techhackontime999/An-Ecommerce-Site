"""Exposes the loader configuration to every storefront template.

Templates receive ``loader_config`` (a JSON-serializable dict) and
``loader_version``. When loaders are disabled the config is ``None`` and the
storefront renders nothing. ``loader_skeleton_type`` is always available so the
page can tag itself for the page-specific skeleton.
"""

from .services import get_config_dict

# (app_name, url_name) -> skeleton page type. Anything not listed falls back
# to the generic 'default' layout.
SKELETON_PAGE_MAP = {
    ('shop', 'home'): 'home',
    ('shop', 'product_list'): 'shop',
    ('shop', 'product_list_by_category'): 'shop',
    ('shop', 'product_search'): 'shop',
    ('shop', 'product_detail'): 'product',
    ('cart', 'cart_detail'): 'cart',
    ('wishlist', 'wishlist_detail'): 'cart',
    ('order', 'order_create'): 'checkout',
    ('order', 'my_orders'): 'checkout',
    ('order', 'order_detail'): 'checkout',
    ('blogs', 'blog_home'): 'blog',
    ('blogs', 'post_detail'): 'blog',
    ('blogs', 'post_search'): 'blog',
    ('blogs', 'posts_by_tag'): 'blog',
    ('blogs', 'author_dashboard'): 'blog',
    ('blogs', 'author_posts'): 'blog',
    ('blogs', 'profile'): 'blog',
    ('blogs', 'profile_tab'): 'blog',
    ('blogs', 'trending'): 'blog',
    ('blogs', 'picks'): 'blog',
    ('blogs', 'leaderboard'): 'blog',
    ('blogs', 'activity_feed'): 'blog',
    ('accounts', 'login'): 'auth',
    ('accounts', 'signup'): 'auth',
    ('accounts', 'seller_register'): 'auth',
    ('accounts', 'become_seller'): 'auth',
    ('accounts', 'profile'): 'auth',
    ('accounts', 'verify'): 'auth',
    ('accounts', 'password_reset'): 'auth',
    ('accounts', 'password_reset_confirm'): 'auth',
    ('accounts', 'password_reset_done'): 'auth',
    ('accounts', 'password_reset_complete'): 'auth',
}

SKELETON_PAGE_TYPES = [
    ('home', 'Home'),
    ('shop', 'Shop / Category / Search'),
    ('product', 'Product detail'),
    ('cart', 'Cart & Wishlist'),
    ('checkout', 'Checkout & Orders'),
    ('auth', 'Login / Signup / Account'),
    ('blog', 'Blog'),
    ('default', 'Other pages'),
]


def get_skeleton_page_type(request):
    """Resolve the current page's skeleton layout type from the URL match."""
    try:
        match = request.resolver_match
        if match is None:
            return 'default'
        key = (match.app_name or '', match.url_name or '')
        return SKELETON_PAGE_MAP.get(key, 'default')
    except Exception:
        return 'default'


def loader_context(request):
    config = get_config_dict()
    skeleton_type = get_skeleton_page_type(request)
    if not config.get('enabled'):
        return {
            'loader_config': None,
            'loader_version': 0,
            'loader_skeleton_type': skeleton_type,
        }
    return {
        'loader_config': config,
        'loader_version': config.get('version', 0),
        'loader_skeleton_type': skeleton_type,
    }

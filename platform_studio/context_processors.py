"""Exposes Platform Studio settings to every template.

Templates use ``{{ platform_settings.site_name }}`` and so on. A few common
values are also injected as shorthand (``SITE_NAME``, ``SITE_TAGLINE``).
"""

from .utils import get_site_settings


def platform_settings_context(request):
    settings = get_site_settings()
    return {
        'platform_settings': settings,
        'SITE_NAME': settings.get('site_name', 'Shop-Seed'),
        'SITE_TAGLINE': settings.get('site_tagline', 'Premium E-Commerce'),
    }

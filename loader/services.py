"""Reading / caching helpers for the Loader Experience System.

The engine never waits on a network request to start: the configuration is
rendered inline into the page by the context processor and versioned. The
public JSON endpoint exists so the engine (and future client-side navigation)
can refresh the cached copy from ``localStorage`` when the version changes.
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import LoaderConfig

CACHE_KEY = 'loader:config:v1'


def config_to_dict(config=None):
    config = config or LoaderConfig.get_solo()
    return {
        'version': config.version,
        'enabled': config.enabled,
        'initial_type': config.initial_type,
        'navigation_type': config.navigation_type,
        'logo_text': config.logo_text,
        'logo_image': config.logo_image.url if config.logo_image else '',
        'background_color': config.background_color,
        'accent_color': config.accent_color,
        'duration_ms': config.duration_ms,
        'exit_animation': config.exit_animation,
        'show_on': config.show_on,
        'device_desktop': config.device_desktop,
        'device_tablet': config.device_tablet,
        'device_mobile': config.device_mobile,
        'lightweight_mobile': config.lightweight_mobile,
        'respect_reduced_motion': config.respect_reduced_motion,
        'network_fallback': config.network_fallback,
        'skeleton_enabled': config.skeleton_enabled,
        'skeleton_pages': config.skeleton_pages or {},
    }


def get_config_dict():
    """Return the active loader config as a dict, cached for an hour."""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    data = config_to_dict()
    cache.set(CACHE_KEY, data, 3600)
    return data


def invalidate():
    cache.delete(CACHE_KEY)


@receiver(post_save, sender=LoaderConfig)
@receiver(post_delete, sender=LoaderConfig)
def _invalidate_loader_cache(sender, **kwargs):
    invalidate()

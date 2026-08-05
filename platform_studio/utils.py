"""Reading + writing helpers for site-wide Platform Studio settings.

``get_site_settings()`` merges the schema defaults with any overrides stored in
the database and returns one flat dict. The result is memoized in-process and
invalidated whenever a setting is saved, so edits appear instantly.
"""

from django.core.cache import cache

from .settings_definitions import ALL_SETTINGS

CACHE_KEY = 'platform_studio:all'

_cache = None
_cache_dirty = True


def seed_defaults():
    """Create a row for every schema setting (does not overwrite existing)."""
    from .models import SiteSetting

    existing = set(SiteSetting.objects.values_list('key', flat=True))
    to_create = []
    for s in ALL_SETTINGS:
        if s['key'] in existing:
            continue
        to_create.append(SiteSetting(
            key=s['key'],
            label=s['label'],
            value=s['default'],
            group=s['group'],
            field_type=s['field_type'],
            help_text=s['help_text'],
        ))
    SiteSetting.objects.bulk_create(to_create)
    invalidate()


def _load():
    from .models import SiteSetting

    merged = {}
    for s in ALL_SETTINGS:
        merged[s['key']] = s['default']
    try:
        for obj in SiteSetting.objects.filter(is_active=True):
            merged[obj.key] = obj.value
    except Exception:
        pass
    return merged


def get_site_settings():
    """Return every active setting as ``{key: value}`` (merged with defaults)."""
    global _cache, _cache_dirty
    if _cache_dirty:
        _cache = _load()
        _cache_dirty = False
    return dict(_cache or {})


def get_setting(key, default=None):
    return get_site_settings().get(key, default)


def get_boolean(key, default=False):
    value = get_setting(key)
    if value is None:
        return bool(default)
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def invalidate():
    global _cache, _cache_dirty
    _cache = None
    _cache_dirty = True
    cache.delete(CACHE_KEY)


def store_setting(key, value):
    """Persist one setting (creating/updating its row) and refresh the cache."""
    from .models import SiteSetting

    definition = next((s for s in ALL_SETTINGS if s['key'] == key), None)
    if definition is None:
        return
    SiteSetting.objects.update_or_create(
        key=key,
        defaults={
            'label': definition['label'],
            'value': str(value),
            'group': definition['group'],
            'field_type': definition['field_type'],
            'help_text': definition['help_text'],
        },
    )
    invalidate()

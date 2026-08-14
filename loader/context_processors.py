"""Exposes the loader configuration to every storefront template.

Templates receive ``loader_config`` (a JSON-serializable dict) and
``loader_version``. When loaders are disabled the config is ``None`` and the
storefront renders nothing.
"""

from .services import get_config_dict


def loader_context(request):
    config = get_config_dict()
    if not config.get('enabled'):
        return {'loader_config': None, 'loader_version': 0}
    return {
        'loader_config': config,
        'loader_version': config.get('version', 0),
    }

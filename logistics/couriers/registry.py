"""Courier adapter registry.

Adapters register themselves by decorating their class with ``@register``
(or simply importing them — module import triggers the decorator). The
registry maps ``CourierCompany.code`` → adapter class.
"""

_registry = {}


def register(cls):
    """Class decorator that adds an adapter to the registry."""
    if not cls.code:
        raise ValueError(f'Adapter {cls.__name__} must define a non-empty "code".')
    _registry[cls.code] = cls
    return cls


def get_adapter(code):
    """Return the adapter *class* for a courier code, or None."""
    return _registry.get(code)


def adapter_class_for(courier):
    """Return the adapter class for a CourierCompany row, honouring an
    optional custom adapter_path override."""
    from django.utils.module_loading import import_string
    cls = get_adapter(courier.code)
    if cls is None and courier.adapter_path:
        cls = import_string(courier.adapter_path)
    return cls


def registered_codes():
    return sorted(_registry.keys())


def all_adapters():
    return list(_registry.values())

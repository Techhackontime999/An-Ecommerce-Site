"""Template filters that enforce site-wide output sanitization.

``|richtext`` is registered as a template *builtin* (see the ``builtins``
entry in TEMPLATES OPTIONS) so every template can use it without an explicit
``{% load %}``. It sanitizes rich-text HTML before it is marked safe, which is
the authoritative layer that stops stored XSS even for content already in the
database.
"""

from django import template
from django.utils.safestring import mark_safe

from core.sanitizers import sanitize_html

register = template.Library()


@register.filter(name='richtext', is_safe=True)
def richtext(value):
    """Sanitize database HTML and mark the result safe for rendering."""
    return mark_safe(sanitize_html(value))

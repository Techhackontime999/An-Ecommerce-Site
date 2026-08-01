from django import template

from ..currencies import DEFAULT_CURRENCY
from ..exchange import currency_info

register = template.Library()


def _format(value, code):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    info = currency_info(code or DEFAULT_CURRENCY)
    amount = value * info['rate']
    try:
        formatted = f"{amount:,.{info['decimals']}f}"
    except (KeyError, ValueError):
        formatted = f"{amount:,.2f}"
    symbol = info.get('symbol', '')
    if symbol.endswith(' '):
        return symbol + formatted
    return f"{symbol}{formatted}"


@register.filter
def currency(value, code='USD'):
    """Convert a USD-stored value into the given currency and format it."""
    return _format(value, code or DEFAULT_CURRENCY)


@register.simple_tag(takes_context=True)
def price(context, value):
    """Convert a USD-stored value into the visitor's active currency.

    A tag (filters cannot take context) so templates write ``{% price x %}``.
    """
    code = context.get('CURRENCY_CODE')
    return _format(value, code)

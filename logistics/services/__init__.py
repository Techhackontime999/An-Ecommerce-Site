"""Shipment planning utilities used by the shipping engine and label service.
"""

from decimal import Decimal, ROUND_HALF_UP


def round_money(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def parse_pincode(raw):
    digits = ''.join(ch for ch in str(raw or '') if ch.isdigit())
    return digits or (str(raw or ''))


def zone_for_pincode(pincode, serviceability=None):
    """Return the delivery zone for a pincode from serviceability data, else
    a sensible default (Indian pincodes starting 1-8 are considered metro/urban
    for demo purposes)."""
    if serviceability and serviceability.zone:
        return serviceability.zone
    return 'urban'

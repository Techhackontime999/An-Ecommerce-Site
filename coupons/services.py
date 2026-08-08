"""Coupon validation and discounting.

A coupon is only usable when *every* check passes: active + within dates,
global usage limit, per-user limit, user whitelist, seller scoping and minimum
cart total. The same validator runs at apply time, when the cart is rendered,
and again (under a row lock) at the final moment of order creation so a coupon
can never be used after it is exhausted or expired.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import Coupon


def _cents(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def validate_coupon(coupon, *, user=None, cart_total=Decimal('0'), seller_ids=None):
    """Validate a coupon for a specific cart context.

    Returns ``(ok, reason)``. ``user`` may be None for guests, in which case
    user-specific checks are skipped. ``seller_ids`` is the set of seller ids
    present in the cart.
    """
    if not isinstance(coupon, Coupon):
        return False, 'Unknown coupon.'
    now = timezone.now()
    if not coupon.active:
        return False, 'This coupon is no longer active.'
    if coupon.valid_from > now:
        return False, 'This coupon is not valid yet.'
    if coupon.valid_to < now:
        return False, 'This coupon has expired.'
    if coupon.max_uses is not None and coupon.used_count() >= coupon.max_uses:
        return False, 'This coupon has reached its usage limit.'
    if user is not None and user.is_authenticated:
        user_uses = coupon.redemptions.filter(user=user).count()
        limit = coupon.per_user_limit or 1
        if user_uses >= limit:
            return False, 'You have already used this coupon.'
        if coupon.allowed_users.exists() and not coupon.allowed_users.filter(pk=user.pk).exists():
            return False, 'This coupon is not available to you.'
    if coupon.seller_id is not None:
        if not seller_ids or coupon.seller_id not in seller_ids:
            return False, 'This coupon is not valid for the items in your cart.'
    if cart_total < coupon.min_amount:
        return False, f'Add items worth at least ₹{coupon.min_amount} to use this coupon.'
    return True, ''


def discount_for(coupon, cart_total):
    """Compute the rupee discount for a cart, honouring the optional cap."""
    if coupon is None:
        return Decimal('0')
    amount = Decimal(cart_total) * (Decimal(coupon.discount) / Decimal(100))
    if coupon.max_discount_amount is not None:
        amount = min(amount, coupon.max_discount_amount)
    amount = min(amount, Decimal(cart_total))
    return _cents(amount)

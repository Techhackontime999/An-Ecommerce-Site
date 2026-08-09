"""Session-based access control for guest (anonymous) checkout.

Guest checkout lets shoppers place an order without an account. Order access
(shipping selection, payment, tracking, invoice) is granted through the session
instead of a user FK: the order id is recorded in the session at creation time,
so the same browser can follow the order through to completion. Signed-in users
keep the normal user-based access.
"""

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Order

GUEST_ORDERS_SESSION_KEY = 'guest_order_ids'

# Email links stay valid for this long before they expire.
GUEST_ACCESS_TOKEN_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def can_access_order(request, order):
    """True when the caller may view/operate on ``order``.

    Either a signed-in user owns the order, or the order id is recorded in the
    caller's session (guest checkout).
    """
    if order.user_id and getattr(request, 'user', None) is not None:
        user = request.user
        if user.is_authenticated and order.user_id == user.pk:
            return True
    return order.id in get_guest_order_ids(request)


def get_guest_order_ids(request):
    return set(request.session.get(GUEST_ORDERS_SESSION_KEY, []))


def grant_guest_access(request, order):
    """Record the order in the session so the guest can follow it."""
    ids = set(request.session.get(GUEST_ORDERS_SESSION_KEY, []))
    ids.add(order.id)
    request.session[GUEST_ORDERS_SESSION_KEY] = sorted(ids)


def get_order_for_request(request, order_id, queryset=None, token=None):
    """Fetch an order the caller is allowed to see, or 404.

    ``queryset`` lets callers attach prefetch/select_related while keeping the
    access check in one place. ``token`` is the signed link from the guest order
    confirmation email: a valid token proves the caller is the guest who placed
    the order, grants access for this browser session, and lets the link work
    even from a different device than the one used to check out.
    """
    qs = queryset if queryset is not None else Order.objects.all()
    order = get_object_or_404(qs, id=order_id)
    if can_access_order(request, order):
        return order
    if token and order.user_id is None and _valid_guest_token(order, token):
        grant_guest_access(request, order)
        return order
    raise Http404


def make_guest_access_token(order):
    """Signed, expiring token that lets a guest reach their order from email."""
    return TimestampSigner().sign('{}:{}'.format(order.id, order.email))


def order_id_from_guest_token(token):
    """The ``(order_id, email)`` a valid guest token names, else ``None``."""
    if not token:
        return None
    try:
        value = TimestampSigner().unsign(token, max_age=GUEST_ACCESS_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    order_id, sep, email = value.partition(':')
    if not sep or not order_id.isdigit() or not email:
        return None
    return int(order_id), email


def _valid_guest_token(order, token):
    """True when ``token`` is an unexpired, untampered link for this order."""
    result = order_id_from_guest_token(token)
    if result is None:
        return False
    order_id, email = result
    return order_id == order.id and email == order.email

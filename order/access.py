"""Session-based access control for guest (anonymous) checkout.

Guest checkout lets shoppers place an order without an account. Order access
(shipping selection, payment, tracking, invoice) is granted through the session
instead of a user FK: the order id is recorded in the session at creation time,
so the same browser can follow the order through to completion. Signed-in users
keep the normal user-based access.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404

from .models import Order

GUEST_ORDERS_SESSION_KEY = 'guest_order_ids'


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


def get_order_for_request(request, order_id, queryset=None):
    """Fetch an order the caller is allowed to see, or 404.

    ``queryset`` lets callers attach prefetch/select_related while keeping the
    access check in one place.
    """
    qs = queryset if queryset is not None else Order.objects.all()
    order = get_object_or_404(qs, id=order_id)
    if not can_access_order(request, order):
        raise Http404
    return order

"""Shared security helpers: safe redirects and request IP resolution."""

from django.utils.http import url_has_allowed_host_and_scheme


def client_ip(request):
    """Best-effort client IP, honouring a single X-Forwarded-For hop."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
    return request.META.get('REMOTE_ADDR', '')


def safe_next_url(request, param='next'):
    """Return a same-host, same-scheme ``next`` URL or None.

    Prevents open-redirect attacks from ``next`` parameters (POST or GET).
    """
    url = request.POST.get(param) or request.GET.get(param) or ''
    if not url:
        return None
    allowed = url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    return url if allowed else None

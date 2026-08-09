"""Cache-backed request rate limiting (dependency-free).

Defends signup, password reset, contact forms, newsletters and similar
high-value POST endpoints against abuse / spam / credential stuffing. Keys are
scoped per (endpoint, client IP) and stored as digests so raw IPs never appear
in the cache.
"""

import hashlib
import time

from django.core.cache import cache
from django.http import HttpResponse

from core.security import client_ip


def _key(endpoint, value):
    digest = hashlib.sha256(str(value).encode('utf-8', 'ignore')).hexdigest()
    return f'rate-limit:{endpoint}:{digest}'


def throttle(endpoint, *, max_requests, window_seconds):
    """Return a decorator limiting ``endpoint`` to ``max_requests`` per window.

    Applies per client IP. When the limit is exceeded the view is not called
    and an HTTP 429 response is returned instead. Used as:
        @throttle('signup', max_requests=5, window_seconds=3600)
        def signup(request): ...
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            key = _key(endpoint, client_ip(request))
            now = int(time.time())
            window_start = now - (now % window_seconds)
            cache_key = f'{key}:{window_start}'
            count = int(cache.get(cache_key, 0) or 0)

            if request.method == 'POST':
                if count >= max_requests:
                    return HttpResponse(
                        'Too many requests. Please try again later.', status=429
                    )
                cache.set(cache_key, count + 1, window_seconds)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

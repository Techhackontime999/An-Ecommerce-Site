"""Core infrastructure endpoints (health checks)."""

from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness/readiness probe for load balancers and uptime monitors.

    Reports database and cache status without any auth. Returns 200 only when
    both backends respond, so a dead Redis or DB flips this to 503 and takes
    the instance out of rotation. The cache check also covers Redis-backed
    sessions, since they share the same connection.
    """
    checks = {}
    ok = True

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = 'ok'
    except Exception as exc:  # noqa: BLE001 - any backend failure = unhealthy
        ok = False
        checks['database'] = 'error: {}'.format(exc)

    try:
        from django.core.cache import cache
        cache.set('healthz', '1', timeout=5)
        checks['cache'] = 'ok' if cache.get('healthz') == '1' else 'error: cache read-back failed'
    except Exception as exc:  # noqa: BLE001
        ok = False
        checks['cache'] = 'error: {}'.format(exc)

    return JsonResponse(
        {'status': 'ok' if ok else 'error', 'checks': checks},
        status=200 if ok else 503,
    )

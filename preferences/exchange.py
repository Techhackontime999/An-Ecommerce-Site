"""Live exchange-rate fetching with caching and graceful fallback.

All product prices on the site are stored in USD. This module fetches fresh
rates from a free exchange-rate API (open.er-api.com by default — no key
required, updated daily) and caches them so conversions stay *real and current*
without hammering the API on every request.

If the API is unreachable the static table in ``currencies.py`` is used as a
fallback so the site keeps working offline.

The request path never blocks on the network: on a cache miss it serves the
static fallback immediately and refreshes the live rates in a background
thread. Run the management command ``manage.py update_currency_rates`` to force
a synchronous refresh.
"""

import json
import logging
import threading
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .currencies import CURRENCIES, DEFAULT_CURRENCY

logger = logging.getLogger(__name__)

RATES_CACHE_KEY = 'shopseed:exchange_rates'
RATES_TS_CACHE_KEY = 'shopseed:exchange_rates_ts'


def _cache_hours():
    try:
        return max(1, int(getattr(settings, 'EXCHANGE_RATE_CACHE_HOURS', 12)))
    except (TypeError, ValueError):
        return 12


def _fetch_live():
    """Hit the API and return ``(rates_map, unix_timestamp)``.

    Raises on any transport / parse failure so callers can fall back.
    """
    base = DEFAULT_CURRENCY
    template = (
        getattr(settings, 'EXCHANGE_RATE_API_URL', '')
        or 'https://open.er-api.com/v6/latest/{base}'
    )
    url = template.format(base=urllib.parse.quote(base))
    api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')
    if api_key:
        sep = '&' if '?' in url else '?'
        url = f'{url}{sep}apikey={urllib.parse.quote(api_key)}'

    request = urllib.request.Request(
        url,
        headers={'User-Agent': 'Shop-Seed/1.0 (e-commerce)'},
    )
    with urllib.request.urlopen(request, timeout=12) as resp:
        data = json.loads(resp.read().decode('utf-8'))

    rates = data.get('rates') or {}
    if not rates:
        raise ValueError('exchange-rate API returned no rates')

    timestamp = (
        data.get('time_last_update_unix')
        or data.get('time_last_updated')
        or int(time.time())
    )
    try:
        timestamp = int(timestamp)
    except (TypeError, ValueError):
        timestamp = int(time.time())
    return rates, timestamp


def _static_rates():
    """Return the fallback ``{code: rate}`` table from ``currencies.py``."""
    return {code: float(info['rate']) for code, info in CURRENCIES.items()}


def _fetch_and_store():
    """Synchronous fetch + cache write. Returns rates, or ``None`` on failure.

    Never raises: failures are logged and the caller keeps whatever it had.
    """
    try:
        live, timestamp = _fetch_live()
    except Exception as exc:  # noqa: BLE001 - must never break the shop
        logger.warning('Exchange-rate fetch failed (%s); keeping existing rates.', exc)
        return None

    rates = {}
    for code, info in CURRENCIES.items():
        rate = live.get(code)
        rates[code] = float(rate) if rate else float(info['rate'])

    timeout = _cache_hours() * 3600
    cache.set(RATES_CACHE_KEY, rates, timeout)
    cache.set(RATES_TS_CACHE_KEY, timestamp, timeout)
    return rates


def _start_background_refresh():
    """Kick off a daemon refresh thread so requests never block on the API."""

    def worker():
        try:
            _fetch_and_store()
        except Exception:  # noqa: BLE001
            logger.exception('Background exchange-rate refresh failed.')

    try:
        thread = threading.Thread(
            target=worker, daemon=True, name='exchange-rate-refresh'
        )
        thread.start()
    except Exception:  # noqa: BLE001
        logger.exception('Could not start background exchange-rate refresh.')


def get_rates(refresh=False):
    """Return ``{code: usd_rate}`` for every supported currency (cached).

    ``refresh=True`` forces a *synchronous* fetch (used by the management
    command). Otherwise a cold cache returns the static fallback immediately
    and refreshes live rates in a background thread.
    """
    cached = cache.get(RATES_CACHE_KEY)
    if cached is not None and not refresh:
        return cached

    if refresh:
        rates = _fetch_and_store()
        if rates is not None:
            return rates
        return _static_rates()

    # Cache missing: serve the fallback now, refresh in the background. The
    # static value is negative-cached so a dead API isn't retried per request;
    # a successful background fetch (which runs afterwards) overwrites it with
    # live rates.
    rates = _static_rates()
    cache.set(RATES_CACHE_KEY, rates, 60 * 60)
    _start_background_refresh()
    return rates


def rates_updated_at():
    """Unix timestamp of the last successful live fetch (may be ``None``)."""
    return cache.get(RATES_TS_CACHE_KEY)


def currency_info(code):
    """Return the currency entry for ``code`` with the current live rate."""
    info = dict(CURRENCIES.get(code) or CURRENCIES[DEFAULT_CURRENCY])
    info['rate'] = float(get_rates().get(code, info['rate']))
    return info


def all_currencies():
    """Return the full ``CURRENCIES`` dict with live rates applied."""
    rates = get_rates()
    result = {}
    for code, info in CURRENCIES.items():
        item = dict(info)
        item['rate'] = float(rates.get(code, info['rate']))
        result[code] = item
    return result

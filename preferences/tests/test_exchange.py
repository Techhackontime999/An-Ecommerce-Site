import time
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from preferences.exchange import (
    RATES_CACHE_KEY,
    RATES_TS_CACHE_KEY,
    get_rates,
    rates_updated_at,
)
from preferences.currencies import CURRENCIES, DEFAULT_CURRENCY


def _static():
    return {code: float(info['rate']) for code, info in CURRENCIES.items()}


def _wait_for(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class ExchangeRateTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cached_rates_returned_without_fetch(self):
        cache.set(RATES_CACHE_KEY, {'USD': 1.0}, 3600)
        with mock.patch('preferences.exchange._fetch_and_store') as fetch:
            rates = get_rates()
        self.assertEqual(rates, {'USD': 1.0})
        fetch.assert_not_called()

    def test_cold_cache_returns_fallback_and_refreshes_async(self):
        live_rates = {'USD': 1.0, 'EUR': 0.85, 'INR': 83.0}
        with mock.patch(
            'preferences.exchange._fetch_live',
            return_value=(live_rates, 1234567890),
        ):
            rates = get_rates()
            # Serves the static fallback immediately — no blocking.
            self.assertEqual(rates, _static())
            # Background refresh populates the real rates shortly after.
            self.assertTrue(
                _wait_for(lambda: cache.get(RATES_TS_CACHE_KEY) == 1234567890),
                'background refresh did not complete',
            )
        self.assertEqual(get_rates(), {
            code: float(live_rates.get(code, info['rate']))
            for code, info in CURRENCIES.items()
        })

    def test_refresh_is_synchronous_and_returns_live_rates(self):
        live_rates = {'USD': 1.0, 'EUR': 0.9}
        with mock.patch(
            'preferences.exchange._fetch_live',
            return_value=(live_rates, 999),
        ):
            rates = get_rates(refresh=True)
        self.assertEqual(rates['EUR'], 0.9)
        self.assertEqual(rates_updated_at(), 999)

    def test_failed_refresh_falls_back_to_static(self):
        with mock.patch(
            'preferences.exchange._fetch_live',
            side_effect=OSError('network down'),
        ):
            rates = get_rates(refresh=True)
        self.assertEqual(rates, _static())
        self.assertIsNone(rates_updated_at())

    def test_failed_background_refresh_leaves_static_fallback(self):
        with mock.patch(
            'preferences.exchange._fetch_live',
            side_effect=OSError('network down'),
        ):
            rates = get_rates()
        self.assertEqual(rates, _static())
        self.assertTrue(_wait_for(lambda: cache.get(RATES_CACHE_KEY) is not None))

    def test_all_currencies_uses_cached_rates(self):
        from preferences.exchange import all_currencies

        cache.set(RATES_CACHE_KEY, {DEFAULT_CURRENCY: 1.0}, 3600)
        result = all_currencies()
        self.assertEqual(result[DEFAULT_CURRENCY]['rate'], 1.0)
        self.assertEqual(set(result), set(CURRENCIES))

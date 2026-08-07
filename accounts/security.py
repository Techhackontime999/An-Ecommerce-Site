"""Brute-force / lockout helpers backed by Django's cache.

Keys are keyed by a SHA-256 digest so usernames/IPs never appear verbatim in
the cache. Cache size and lockout windows are intentionally small; the primary
defence is per-account lockout, which an attacker rotating IPs cannot escape.
"""

import hashlib

from django.core.cache import cache

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
OTP_MAX_ATTEMPTS = 5


def _key(kind, value):
    digest = hashlib.sha256(str(value).encode('utf-8', 'ignore')).hexdigest()
    return f'auth-lock:{kind}:{digest}'


def record_failure(kind, value):
    key = _key(kind, value)
    count = int(cache.get(key, 0) or 0) + 1
    cache.set(key, count, LOGIN_LOCKOUT_SECONDS)
    return count


def failure_count(kind, value):
    return int(cache.get(_key(kind, value), 0) or 0)


def is_locked(kind, value, max_attempts=LOGIN_MAX_ATTEMPTS):
    return failure_count(kind, value) >= max_attempts


def reset(kind, value):
    cache.delete(_key(kind, value))

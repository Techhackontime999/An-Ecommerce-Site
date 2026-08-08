"""Encrypted-at-rest model fields.

Uses Fernet (AES-128-CBC + HMAC, from the ``cryptography`` package) so the
database never holds secrets in plaintext. A single ``FIELD_ENCRYPTION_KEY``
env var (a base64 Fernet key) is shared by all fields; generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

The key must be set in production (mirroring ``SECRET_KEY``). Rotating the key
requires re-encrypting stored values (a data migration), not just swapping the
env var.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

logger = logging.getLogger(__name__)

_fernet = None


def get_fernet():
    """Return a cached ``Fernet`` instance built from ``FIELD_ENCRYPTION_KEY``."""
    global _fernet
    if _fernet is not None:
        return _fernet
    raw = getattr(settings, 'FIELD_ENCRYPTION_KEY', '') or ''
    if not raw:
        raise ImproperlyConfigured(
            'FIELD_ENCRYPTION_KEY is not set. Generate one with '
            '`python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"` and export it (production '
            'requires it, exactly like SECRET_KEY).'
        )
    try:
        _fernet = Fernet(raw.encode())
    except Exception as exc:
        raise ImproperlyConfigured(f'Invalid FIELD_ENCRYPTION_KEY: {exc}') from exc
    return _fernet


class EncryptedCharField(models.CharField):
    """A CharField that transparently encrypts values at rest.

    Plaintext is written and read by application code; the database column only
    ever holds Fernet ciphertext. Empty values are stored as empty strings
    (encrypting an empty value would turn it into a non-empty token).

    Equality lookups against ciphertext are intentionally not supported
    (Fernet is non-deterministic), so never filter on an encrypted column.
    """

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def to_python(self, value):
        if value in (None, ''):
            return value
        try:
            return get_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Legacy plaintext that predates encryption. Return it as-is so the
            # row stays usable; the next save re-encrypts it (self-healing).
            return value
        except Exception as exc:  # noqa: BLE001 - a decrypt bug must not 500 the request
            logger.error('Failed to decrypt encrypted field value: %s', exc, exc_info=True)
            return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ''):
            return value
        return get_fernet().encrypt(value.encode()).decode()

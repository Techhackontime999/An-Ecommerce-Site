"""Sentry error tracking bootstrap.

Initialises the Sentry SDK from the environment. No-op (and imports nothing
from ``sentry_sdk``) when ``SENTRY_DSN`` is unset, so local dev and tests run
without Sentry installed or configured.
"""

import logging
import os


def init_sentry(*, environment):
    dsn = os.getenv('SENTRY_DSN', '').strip()
    if not dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv('SENTRY_ENVIRONMENT', environment),
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        send_default_pii=False,
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        release=os.getenv('GIT_SHA') or os.getenv('RENDER_GIT_COMMIT') or None,
    )
    return True

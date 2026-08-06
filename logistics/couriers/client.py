"""Resilient HTTP client for courier APIs.

Features:
- Configurable timeout per request.
- Retry with exponential backoff on network errors and retryable status codes
  (429, 5xx), capped at LOGISTICS_COURIER_MAX_RETRIES.
- Idempotency key support: send the same key on retries so the courier does
  not create duplicate shipments.
- Failures are persisted to the audit log for post-mortem analysis.
"""

import hashlib
import logging
import time

import requests

from django.conf import settings

from logistics.models import AuditLog
from .base import CourierAPIError

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class CourierClient:
    def __init__(
        self,
        base_url,
        *,
        headers=None,
        timeout=None,
        max_retries=None,
        retry_backoff=None,
        courier_code='',
        idempotency_header='X-Idempotency-Key',
    ):
        self.base_url = (base_url or '').rstrip('/')
        self.headers = dict(headers or {})
        self.timeout = timeout if timeout is not None else getattr(settings, 'LOGISTICS_COURIER_TIMEOUT_SECONDS', 30)
        self.max_retries = max_retries if max_retries is not None else getattr(settings, 'LOGISTICS_COURIER_MAX_RETRIES', 3)
        self.retry_backoff = retry_backoff if retry_backoff is not None else getattr(settings, 'LOGISTICS_COURIER_RETRY_BACKOFF', 2)
        self.courier_code = courier_code
        self.idempotency_header = idempotency_header

    # ------------------------------------------------------------------ core
    def request(
        self,
        method,
        path,
        *,
        json=None,
        params=None,
        data=None,
        idempotency_key=None,
        retry_on=RETRYABLE_STATUS_CODES,
        extra_headers=None,
    ):
        """Perform an HTTP request with retries.

        Returns the parsed JSON payload (or None). Raises CourierAPIError on
        terminal failure after exhausting retries.
        """
        url = f'{self.base_url}/{path.lstrip("/")}' if self.base_url else path
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        if idempotency_key and self.idempotency_header:
            headers[self.idempotency_header] = idempotency_key

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(
                    method.upper(),
                    url,
                    json=json,
                    params=params,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
                body = self._parse_response(response)
                if response.status_code >= 400 and response.status_code not in retry_on:
                    raise CourierAPIError(
                        f'Courier {self.courier_code} returned {response.status_code} for {method} {path}: {body}',
                        status_code=response.status_code,
                        payload=body,
                    )
                if response.status_code in retry_on or response.status_code >= 500:
                    raise CourierAPIError(
                        f'Courier {self.courier_code} retryable status {response.status_code} for {method} {path}',
                        status_code=response.status_code,
                        payload=body,
                    )
                return body

            except CourierAPIError as exc:
                last_exc = exc
                if exc.status_code in retry_on or exc.status_code >= 500:
                    self._backoff(attempt, method, path, exc)
                    continue
                raise
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                self._backoff(attempt, method, path, exc)

        self._log_failure(method, path, last_exc)
        raise CourierAPIError(
            f'Courier {self.courier_code} request failed after {self.max_retries} attempts: {last_exc}'
        ) from last_exc

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)

    def put(self, path, **kwargs):
        return self.request('PUT', path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request('PATCH', path, **kwargs)

    # ---------------------------------------------------------------- utils
    @staticmethod
    def _parse_response(response):
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type or content_type == '':
            try:
                return response.json()
            except ValueError:
                pass
        return response.text

    def _backoff(self, attempt, method, path, exc):
        delay = self.retry_backoff * (2 ** (attempt - 1))
        logger.warning(
            'Courier %s retry %d/%d for %s %s after %r; sleeping %.1fs',
            self.courier_code, attempt, self.max_retries, method, path, exc, delay,
        )
        time.sleep(delay)

    def _log_failure(self, method, path, exc):
        AuditLog.log(
            action=AuditLog.ACTION_ERROR,
            object_type='courier',
            object_id=self.courier_code,
            details={'method': method, 'path': path, 'error': str(exc)},
        )

    @staticmethod
    def make_idempotency_key(*parts):
        key = '|'.join(str(p) for p in parts)
        return hashlib.sha256(key.encode('utf-8')).hexdigest()

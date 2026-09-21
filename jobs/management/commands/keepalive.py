"""Lightweight keep-alive ping for Render free web services.

Render's free tier spins a Web service down after ~15 minutes without
inbound traffic, so the next visitor pays a ~1 minute cold start. This
command is meant to run OUTSIDE the web process (as a cron job), pinging
the service's health URL on a cadence shorter than the spin-down window.

It deliberately lives in the existing ``jobs`` cron architecture instead of
introducing a new dependency, and never runs inside the web request path::

    python manage.py keepalive --url https://your-app.onrender.com/healthz
    python manage.py keepalive                          # uses $KEEPALIVE_URL

Exits 0 only when the target answered HTTP 200. Timeouts, network errors
and non-200 responses exit non-zero with a clear line, so a service that
goes down shows up as a failed cron run instead of a silent green one.
"""

import os
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Ping a health URL so a Render free web service does not spin down.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            default=os.getenv('KEEPALIVE_URL', ''),
            help='Full health URL to ping (default: $KEEPALIVE_URL).',
        )
        parser.add_argument(
            '--timeout',
            type=float,
            default=10.0,
            help='Request timeout in seconds (default 10).',
        )

    def handle(self, *args, **options):
        url = (options['url'] or '').strip()
        if not url:
            raise CommandError(
                'No keep-alive URL: pass --url or set the KEEPALIVE_URL env var.'
            )

        timeout = options['timeout']
        if timeout <= 0:
            raise CommandError('--timeout must be a positive number of seconds.')

        try:
            request = urllib.request.Request(
                url, method='GET', headers={'User-Agent': 'shopseed-keepalive/1.0'}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                code = response.getcode()
                if code != 200:
                    raise CommandError(
                        f'keep-alive ping {url} -> HTTP {code}'
                    )
        except urllib.error.HTTPError as exc:
            raise CommandError(f'keep-alive ping {url} -> HTTP {exc.code}')
        except OSError as exc:
            raise CommandError(f'keep-alive ping {url} failed: {exc}')

        self.stdout.write(self.style.SUCCESS(f'keep-alive OK: {url} -> 200'))
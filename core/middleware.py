"""Response-level security headers.

Adds Content-Security-Policy, Permissions-Policy and belt-and-braces
X-Content-Type-Options on every response. Settings live in
``SECURITY_CSP`` / ``SECURITY_PERMISSIONS_POLICY`` (see local.py / production.py).

The policy is tuned to the site's existing inline-style/script templates and
its third-party scripts (Google Analytics, Font Awesome, Google Fonts,
Razorpay Checkout), so it blocks injected *external* scripts, plugins, frames
and navigation tricks without breaking the storefront. Combined with the
``|richtext`` sanitizer (the primary stored-XSS defence), the CSP is the
second layer.
"""

from django.conf import settings


class SecurityHeadersMiddleware:
    """Append strict-but-compatible security headers to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['Content-Security-Policy'] = getattr(
            settings, 'SECURITY_CSP', ''
        )
        response['Permissions-Policy'] = getattr(
            settings, 'SECURITY_PERMISSIONS_POLICY', ''
        )
        response.setdefault('X-Content-Type-Options', 'nosniff')
        return response

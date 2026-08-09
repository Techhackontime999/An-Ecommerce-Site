from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from core.sanitizers import sanitize_html
from core.templatetags.core_security import richtext
from core.validators import (
    MAX_UPLOAD_BYTES,
    validate_document_file,
    validate_image_file,
)
from core.views import healthz


class SanitizerTests(SimpleTestCase):
    """Stored-XSS payloads must be stripped by sanitize_html/|richtext."""

    def test_strips_script_tags(self):
        html = '<p>Hello <script>alert(1)</script></p>'
        out = sanitize_html(html)
        self.assertNotIn('<script', out)
        self.assertNotIn('</script>', out)
        # Text content survives as inert text; the tag itself is removed.
        self.assertIn('alert(1)', out)

    def test_strips_event_handlers(self):
        html = '<img src="x" onerror="alert(1)"><p onmouseover="evil()">hi</p>'
        out = sanitize_html(html)
        self.assertNotIn('onerror', out)
        self.assertNotIn('onmouseover', out)

    def test_strips_javascript_urls(self):
        html = '<a href="javascript:alert(1)">click</a>'
        out = sanitize_html(html)
        self.assertNotIn('javascript:', out)

    def test_strips_iframes_objects_embeds(self):
        html = (
            '<iframe src="https://evil.example"></iframe>'
            '<object data="x"></object>'
            '<embed src="y">'
        )
        out = sanitize_html(html)
        self.assertNotIn('iframe', out)
        self.assertNotIn('object', out)
        self.assertNotIn('embed', out)

    def test_strips_style_blocks(self):
        html = '<style>body{display:none}</style><p>ok</p>'
        out = sanitize_html(html)
        self.assertNotIn('style', out)
        self.assertIn('ok', out)

    def test_keeps_safe_richtext(self):
        html = '<h2>Title</h2><p>Some <strong>bold</strong> text with <a href="https://example.com" rel="noopener">a link</a>.</p>'
        out = sanitize_html(html)
        self.assertIn('<h2>', out)
        self.assertIn('<strong>bold</strong>', out)
        self.assertIn('<a href="https://example.com"', out)

    def test_strips_comments(self):
        html = '<p>ok</p><!-- stealtoken -->'
        self.assertNotIn('stealtoken', sanitize_html(html))

    def test_none_and_empty(self):
        self.assertIsNone(sanitize_html(None))
        self.assertEqual(sanitize_html(''), '')


class HealthzTests(TestCase):
    def test_healthz_reports_ok(self):
        response = Client().get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')
        self.assertEqual(response.json()['checks']['database'], 'ok')

    def test_healthz_resolves_to_core_view(self):
        from django.urls import resolve
        match = resolve('/healthz')
        self.assertEqual(match.func, healthz)


class SecurityHeadersTests(TestCase):
    def test_security_headers_present(self):
        response = Client().get('/robots.txt')
        csp = response['Content-Security-Policy']
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("default-src 'self'", csp)
        self.assertIn('base-uri', csp)
        self.assertIn("form-action 'self'", csp)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('camera=()', response['Permissions-Policy'])

    def test_csp_allows_site_scripts_and_payment(self):
        csp = Client().get('/robots.txt')['Content-Security-Policy']
        self.assertIn('checkout.razorpay.com', csp)
        self.assertIn('googletagmanager.com', csp)


class ThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_newsletter_subscribe_limits_requests(self):
        client = Client()
        for _ in range(10):
            resp = client.post('/newsletter/subscribe/', {'email': 'nope@'})
        resp = client.post('/newsletter/subscribe/', {'email': 'nope@'})
        self.assertEqual(resp.status_code, 429)

    def test_signup_limits_requests(self):
        client = Client()
        for _ in range(5):
            client.post('/accounts/signup/', {'username': 'x'})
        resp = client.post('/accounts/signup/', {'username': 'x'})
        self.assertEqual(resp.status_code, 429)


class NewsletterRedirectTests(TestCase):
    def test_no_open_redirect_via_referer(self):
        client = Client()
        resp = client.post(
            '/newsletter/subscribe/',
            {'email': 'not-an-email'},
            HTTP_REFERER='https://evil.example/phish',
        )
        self.assertNotIn('evil.example', resp.get('Location', ''))


class UploadValidatorTests(SimpleTestCase):
    def _upload(self, name, content):
        return SimpleUploadedFile(name, content, content_type='application/octet-stream')

    def test_rejects_executable_documents(self):
        with self.assertRaises(ValidationError):
            validate_document_file(self._upload('virus.exe', b'MZ'))

    def test_rejects_svg_images(self):
        with self.assertRaises(ValidationError):
            validate_image_file(self._upload('logo.svg', b'<svg/>'))

    def test_rejects_oversized_files(self):
        big = self._upload('big.png', b'\x00' * (MAX_UPLOAD_BYTES + 1))
        with self.assertRaises(ValidationError):
            validate_document_file(big)

    def test_accepts_pdf_documents(self):
        validate_document_file(self._upload('proof.pdf', b'%PDF-1.4'))

    def test_accepts_png_images(self):
        validate_image_file(self._upload('photo.png', b'\x89PNG'))

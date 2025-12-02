"""
Tests for CSP middleware.
"""

from django.test import TestCase, RequestFactory
from games.csp_middleware import CSPMiddleware


class CSPMiddlewareTest(TestCase):
    """Test CSP middleware functionality."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = CSPMiddleware(lambda request: self.get_response(request))

    def get_response(self, request):
        """Mock response."""
        from django.http import HttpResponse

        return HttpResponse("Test response")

    def test_csp_header_present(self):
        """Test that CSP header is added to response."""
        request = self.factory.get("/")
        response = self.middleware(request)

        self.assertIn("Content-Security-Policy", response)

    def test_nonce_added_to_request(self):
        """Test that nonce is added to request object."""
        request = self.factory.get("/")
        self.middleware(request)

        self.assertTrue(hasattr(request, "csp_nonce"))
        self.assertIsNotNone(request.csp_nonce)
        self.assertGreater(len(request.csp_nonce), 0)

    def test_nonce_in_csp_header(self):
        """Test that nonce is included in CSP header."""
        request = self.factory.get("/")
        response = self.middleware(request)

        csp_header = response["Content-Security-Policy"]
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp_header)

    def test_csp_includes_object_src_none(self):
        """Test that object-src is set to none."""
        request = self.factory.get("/")
        response = self.middleware(request)

        csp_header = response["Content-Security-Policy"]
        self.assertIn("object-src 'none'", csp_header)

    def test_csp_includes_strict_dynamic(self):
        """Test that strict-dynamic is included."""
        request = self.factory.get("/")
        response = self.middleware(request)

        csp_header = response["Content-Security-Policy"]
        self.assertIn("'strict-dynamic'", csp_header)

    def test_csp_allows_unsafe_eval(self):
        """Test that unsafe-eval is allowed (required for Alpine.js)."""
        request = self.factory.get("/")
        response = self.middleware(request)

        csp_header = response["Content-Security-Policy"]
        self.assertIn("'unsafe-eval'", csp_header)

    def test_csp_allows_required_domains(self):
        """Test that required external domains are allowed."""
        request = self.factory.get("/")
        response = self.middleware(request)

        csp_header = response["Content-Security-Policy"]
        self.assertIn("https://unpkg.com", csp_header)
        self.assertIn("https://cdn.jsdelivr.net", csp_header)
        self.assertIn("https://www.googletagmanager.com", csp_header)

    def test_unique_nonces_per_request(self):
        """Test that each request gets a unique nonce."""
        request1 = self.factory.get("/")
        request2 = self.factory.get("/")

        self.middleware(request1)
        self.middleware(request2)

        self.assertNotEqual(request1.csp_nonce, request2.csp_nonce)

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


class CSPNonceContextProcessorTest(TestCase):
    """Test csp_nonce context processor."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_nonce_when_present(self):
        """Test that csp_nonce returns the nonce from request."""
        from games.context_processors import csp_nonce

        request = self.factory.get("/")
        request.csp_nonce = "test-nonce-12345"

        result = csp_nonce(request)

        self.assertEqual(result, {"csp_nonce": "test-nonce-12345"})

    def test_returns_empty_string_when_no_nonce(self):
        """Test that csp_nonce returns empty string when nonce is not set."""
        from games.context_processors import csp_nonce

        request = self.factory.get("/")
        # Don't set csp_nonce attribute

        result = csp_nonce(request)

        self.assertEqual(result, {"csp_nonce": ""})


class FeatureFlagsContextProcessorTest(TestCase):
    """Test feature_flags context processor."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_feature_flags(self):
        """Test that feature_flags returns expected flags."""
        from games.context_processors import feature_flags

        request = self.factory.get("/")

        result = feature_flags(request)

        # Should contain BOOKS_ENABLED flag (value depends on settings)
        self.assertIn("BOOKS_ENABLED", result)
        self.assertIsInstance(result["BOOKS_ENABLED"], bool)

    def test_returns_dict_type(self):
        """Test that feature_flags returns a dict type."""
        from games.context_processors import feature_flags

        request = self.factory.get("/")

        result = feature_flags(request)

        self.assertIsInstance(result, dict)

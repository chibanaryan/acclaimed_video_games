"""Tests for RateLimitMiddleware."""

import time
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from games.config import (
    RATE_LIMIT_CACHE_PREFIX,
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_PER_MINUTE,
)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class RateLimitMiddlewareTest(TestCase):
    """Test rate limiting middleware."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _seed_minute_count(self, ip="127.0.0.1", count=RATE_LIMIT_PER_MINUTE):
        """Pre-seed the per-minute counter to just at the limit."""
        now = int(time.time())
        key = f"{RATE_LIMIT_CACHE_PREFIX}:min:{ip}:{now // 60}"
        cache.set(key, count, timeout=60)

    def _seed_hour_count(self, ip="127.0.0.1", count=RATE_LIMIT_PER_HOUR):
        """Pre-seed the per-hour counter to just at the limit."""
        now = int(time.time())
        key = f"{RATE_LIMIT_CACHE_PREFIX}:hr:{ip}:{now // 3600}"
        cache.set(key, count, timeout=3600)

    def _block_ip(self, ip="127.0.0.1"):
        """Simulate a blocked IP."""
        cache.set(f"{RATE_LIMIT_CACHE_PREFIX}:block:{ip}", True, timeout=300)

    def test_normal_request_passes(self):
        """Normal requests should return 200."""
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)

    def test_exempt_paths_not_rate_limited(self):
        """Requests to exempt paths should never be rate limited."""
        exempt_paths = [
            "/robots.txt",
            "/sitemap.xml",
            "/favicon.ico",
            "/admin/login/",
            "/static/test.css",
            "/accounts/login/",
        ]
        for path in exempt_paths:
            self._block_ip()
            response = self.client.get(path)
            self.assertNotEqual(
                response.status_code, 429, f"Exempt path {path} was rate limited"
            )
            cache.clear()

    def test_per_minute_rate_limit_allows_up_to_threshold(self):
        """Requests at the per-minute limit should pass."""
        self._seed_minute_count(count=RATE_LIMIT_PER_MINUTE - 1)
        response = self.client.get("/")
        self.assertNotEqual(response.status_code, 429)

    def test_per_minute_rate_limit_blocks_over_threshold(self):
        """Exceeding per-minute threshold should trigger 429."""
        self._seed_minute_count(count=RATE_LIMIT_PER_MINUTE)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("Rate limit", response.content.decode())

    def test_blocked_ip_stays_blocked(self):
        """Once blocked, subsequent requests should also get 429."""
        self._block_ip()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 429)

        response = self.client.get("/games/")
        self.assertEqual(response.status_code, 429)

    def test_per_hour_rate_limit(self):
        """Exceeding per-hour threshold should trigger 429."""
        self._seed_hour_count(count=RATE_LIMIT_PER_HOUR)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 429)

    def test_x_forwarded_for_ip_extraction(self):
        """Should use X-Forwarded-For header for IP extraction."""
        bot_ip = "45.148.10.143"
        self._block_ip(bot_ip)

        # Request from bot IP via X-Forwarded-For should be blocked
        response = self.client.get("/", HTTP_X_FORWARDED_FOR=f"{bot_ip}, 10.0.0.1")
        self.assertEqual(response.status_code, 429)

        # Request from different IP should NOT be blocked
        response = self.client.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4")
        self.assertNotEqual(response.status_code, 429)

    def test_different_ips_tracked_separately(self):
        """Rate limits should be per-IP, not global."""
        ip1 = "10.0.0.1"
        self._seed_minute_count(ip=ip1, count=RATE_LIMIT_PER_MINUTE)

        # IP 1 should be blocked
        response = self.client.get("/", HTTP_X_FORWARDED_FOR=ip1)
        self.assertEqual(response.status_code, 429)

        # IP 2 should still work
        response = self.client.get("/", HTTP_X_FORWARDED_FOR="10.0.0.2")
        self.assertNotEqual(response.status_code, 429)

    def test_cache_failure_allows_request(self):
        """If cache is unavailable, requests should pass through."""
        with patch("games.middleware.cache") as mock_cache:
            mock_cache.get.side_effect = Exception("Cache unavailable")
            response = self.client.get("/")
            # Should not be 429 - graceful degradation
            self.assertNotEqual(response.status_code, 429)

    def test_block_key_created_on_exceed(self):
        """Block cache key should be set when limit is exceeded."""
        ip = "127.0.0.1"
        self._seed_minute_count(ip=ip, count=RATE_LIMIT_PER_MINUTE)

        # Trigger the block
        self.client.get("/")

        # Verify block key exists
        block_key = f"{RATE_LIMIT_CACHE_PREFIX}:block:{ip}"
        self.assertTrue(cache.get(block_key))

    def test_429_response_format(self):
        """429 response should have correct content type and message."""
        self._block_ip()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertIn("Rate limit exceeded", response.content.decode())

    def test_non_exempt_path_is_rate_limited(self):
        """Non-exempt paths should be subject to rate limiting."""
        self._block_ip()
        response = self.client.get("/games/")
        self.assertEqual(response.status_code, 429)

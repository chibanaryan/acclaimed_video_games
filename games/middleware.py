"""
Middleware for HTMX history support and rate limiting.
"""

import logging
import time

from django.core.cache import cache
from django.http import HttpResponse

from games.config import (
    RATE_LIMIT_BLOCK_DURATION,
    RATE_LIMIT_CACHE_PREFIX,
    RATE_LIMIT_PER_HOUR,
    RATE_LIMIT_PER_MINUTE,
)

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
RATE_LIMIT_EXEMPT_PREFIXES = (
    "/robots.txt",
    "/sitemap.xml",
    "/favicon.ico",
    "/admin/",
    "/static/",
    "/accounts/",
)


class RateLimitMiddleware:
    """
    Fixed-window rate limiting per IP address.

    Blocks IPs that exceed per-minute or per-hour thresholds.
    Uses Django's cache backend (Redis in production).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Skip rate limiting for exempt paths
        if any(path.startswith(prefix) for prefix in RATE_LIMIT_EXEMPT_PREFIXES):
            return self.get_response(request)

        ip = self._get_client_ip(request)
        block_key = f"{RATE_LIMIT_CACHE_PREFIX}:block:{ip}"

        try:
            # Check if IP is currently blocked
            if cache.get(block_key):
                return HttpResponse(
                    "Rate limit exceeded. Try again later.",
                    status=429,
                    content_type="text/plain",
                )

            # Atomically increment per-minute and per-hour counters
            now = int(time.time())
            minute_key = f"{RATE_LIMIT_CACHE_PREFIX}:min:{ip}:{now // 60}"
            hour_key = f"{RATE_LIMIT_CACHE_PREFIX}:hr:{ip}:{now // 3600}"

            minute_count = self._incr(minute_key, 60)
            hour_count = self._incr(hour_key, 3600)
        except Exception:
            # If cache is unavailable, allow the request through
            return self.get_response(request)

        # Check thresholds
        if minute_count > RATE_LIMIT_PER_MINUTE or hour_count > RATE_LIMIT_PER_HOUR:
            try:
                cache.set(block_key, True, timeout=RATE_LIMIT_BLOCK_DURATION)
            except Exception:
                pass
            exceeded = (
                f"{minute_count}/min"
                if minute_count > RATE_LIMIT_PER_MINUTE
                else f"{hour_count}/hr"
            )
            logger.warning(
                "Rate limit exceeded for %s (%s) - blocked for %ds. Path: %s",
                ip,
                exceeded,
                RATE_LIMIT_BLOCK_DURATION,
                path,
            )
            return HttpResponse(
                "Rate limit exceeded. Try again later.",
                status=429,
                content_type="text/plain",
            )

        return self.get_response(request)

    @staticmethod
    def _incr(key, timeout):
        """Atomically increment a cache counter, creating it if needed."""
        try:
            return cache.incr(key)
        except ValueError:
            # Key doesn't exist yet — create it
            cache.set(key, 1, timeout=timeout)
            return 1

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from X-Forwarded-For (Heroku) or REMOTE_ADDR."""
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class HTMXPushURLMiddleware:
    """
    Middleware that adds HX-Push-URL header to HTMX responses.

    When hx-push-url="true" is used in templates, HTMX expects the server
    to return an HX-Push-URL header. This middleware ensures that header
    is present, preventing historyCacheError.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Check if this is an HTMX request
        is_htmx_request = (
            request.META.get("HTTP_HX_REQUEST") == "true"
            or request.headers.get("HX-Request") == "true"
        )

        if is_htmx_request:
            # Check if HX-Push-URL is already set (case-insensitive check)
            # Django's HttpResponse headers are case-insensitive
            hx_push_url = response.get("HX-Push-URL")
            if not hx_push_url:
                # Build the full URL with query parameters
                full_url = request.get_full_path()
                response["HX-Push-URL"] = full_url

        return response

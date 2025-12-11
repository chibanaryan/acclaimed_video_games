"""
Content Security Policy (CSP) middleware.

Implements CSP with nonce-based script protection to prevent XSS attacks.
"""

import secrets


class CSPMiddleware:
    """
    Adds Content Security Policy headers with nonce support.

    Generates a unique nonce per request for inline scripts and adds it to
    both the response headers and request context for template use.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate unique nonce for this request
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

        response = self.get_response(request)

        # Add CORS headers for font files
        if request.path.startswith("/static/") and any(
            request.path.endswith(ext)
            for ext in [".woff", ".woff2", ".ttf", ".eot", ".otf"]
        ):
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type"

        # Skip CSP for admin URLs (admin has its own security via authentication)
        if request.path.startswith("/admin/"):
            return response

        # Build CSP policy with nonce
        # Note: 'unsafe-eval' and 'unsafe-inline' are required for Alpine.js
        # - 'unsafe-eval' for x-data expressions
        # - 'unsafe-inline' for @click and other event handlers
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' "
            f"'unsafe-eval' 'unsafe-inline' "
            f"https://unpkg.com https://cdn.jsdelivr.net "
            f"https://www.googletagmanager.com; "
            f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data: https:; "
            f"connect-src 'self' https:; "
            f"frame-src 'self'; "
            f"object-src 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self'; "
            f"upgrade-insecure-requests"
        )

        response["Content-Security-Policy"] = csp_policy

        return response

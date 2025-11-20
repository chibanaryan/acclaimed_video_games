"""
HTMX middleware to add HX-Push-URL header for history cache support.
This fixes the htmx:historyCacheError that occurs when hx-push-url="true" is used.
"""


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

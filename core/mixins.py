"""Reusable view mixins for the multi-media platform."""

from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse


class RobustPaginationMixin:
    """Pagination mixin with graceful handling of invalid page numbers.

    Instead of raising 404 errors for invalid page numbers, returns
    the last valid page (or first page if no results).
    """

    def paginate_queryset(self, queryset, page_size):
        """Paginate the queryset with graceful fallback for invalid pages."""
        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - handle gracefully
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())


class AnonymousResponseCacheMixin:
    """Cache rendered full-page responses for anonymous users to reduce TTFB.

    Subclasses must implement `get_page_cache_key()` returning the cache key
    for the current request, or None to skip caching, and set
    `page_cache_timeout` (seconds). Only anonymous, non-HTMX GET requests
    are cached; only successful, non-streaming responses are stored.
    """

    page_cache_timeout = None
    CACHE_HEADER_SKIP = {
        "content-length",
        "content-type",
        "transfer-encoding",
        "connection",
    }

    def get_page_cache_key(self):
        raise NotImplementedError("Subclasses must implement get_page_cache_key()")

    @classmethod
    def _serialize_headers(cls, response):
        headers = {}
        for name, value in response.headers.items():
            if name.lower() in cls.CACHE_HEADER_SKIP:
                continue
            headers[name] = value
        return headers

    @staticmethod
    def _serialize_cookies(response):
        cookies = {}
        for name, morsel in response.cookies.items():
            max_age = morsel["max-age"] or None
            if max_age is not None:
                try:
                    max_age = int(max_age)
                except (TypeError, ValueError):
                    max_age = None
            cookies[name] = {
                "value": morsel.value,
                "expires": morsel["expires"] or None,
                "max_age": max_age,
                "path": morsel["path"] or "/",
                "domain": morsel["domain"] or None,
                "secure": bool(morsel["secure"]),
                "httponly": bool(morsel["httponly"]),
                "samesite": morsel["samesite"] or None,
            }
        return cookies

    @classmethod
    def _apply_cached_headers(cls, response, headers):
        for name, value in (headers or {}).items():
            if name.lower() in cls.CACHE_HEADER_SKIP:
                continue
            response[name] = value

    @staticmethod
    def _apply_cached_cookies(response, cookies):
        for name, data in (cookies or {}).items():
            response.set_cookie(
                name,
                data.get("value", ""),
                expires=data.get("expires") or None,
                max_age=data.get("max_age"),
                path=data.get("path") or "/",
                domain=data.get("domain") or None,
                secure=bool(data.get("secure")),
                httponly=bool(data.get("httponly")),
                samesite=data.get("samesite") or None,
            )

    def dispatch(self, request, *args, **kwargs):
        is_htmx = (
            request.headers.get("HX-Request")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.GET.get("partial") == "true"
            or request.GET.get("append") == "true"
        )

        if request.user.is_authenticated or is_htmx or request.method != "GET":
            return super().dispatch(request, *args, **kwargs)

        cache_key = self.get_page_cache_key()
        if cache_key is None:
            return super().dispatch(request, *args, **kwargs)

        # Check cache (store only rendered content to avoid retaining
        # request/context)
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            if isinstance(cached_payload, dict) and "content" in cached_payload:
                content = cached_payload.get("content", b"")
                status = cached_payload.get("status", 200)
                content_type = cached_payload.get("content_type")
                response = HttpResponse(
                    content,
                    status=status,
                    content_type=content_type or "text/html; charset=utf-8",
                )
                self._apply_cached_headers(response, cached_payload.get("headers"))
                self._apply_cached_cookies(response, cached_payload.get("cookies"))
                return response
            # Drop legacy cached payloads (response objects) and rebuild.
            cache.delete(cache_key)

        # Generate response and cache it
        response = super().dispatch(request, *args, **kwargs)

        # Only cache successful, non-streaming responses (render first)
        if response.status_code == 200 and not getattr(response, "streaming", False):
            if hasattr(response, "render"):
                response.render()
            cache.set(
                cache_key,
                {
                    "content": response.content,
                    "status": response.status_code,
                    "content_type": response.get("Content-Type"),
                    "headers": self._serialize_headers(response),
                    "cookies": self._serialize_cookies(response),
                },
                self.page_cache_timeout,
            )

        return response


class HTMXPartialMixin:
    """Mixin for views that serve both full pages and HTMX partial responses.

    Set `htmx_partial_template` on your view class to the template path
    that should be used for HTMX requests.
    """

    htmx_partial_template = None

    def get_template_names(self):
        """Return partial template for HTMX requests, full template otherwise."""
        if self.request.headers.get("HX-Request") and self.htmx_partial_template:
            return [self.htmx_partial_template]
        return super().get_template_names()

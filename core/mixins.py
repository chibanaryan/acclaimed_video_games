"""Reusable view mixins for the multi-media platform."""

from django.core.paginator import EmptyPage, Paginator


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

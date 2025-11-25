from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import datetime
import json

from games import constants

register = template.Library()


@register.filter
def get_list_type_label(type_code):
    """Convert list type code to human-readable label."""
    type_dict = dict(constants.LIST_TYPES)
    return type_dict.get(type_code, type_code)


@register.simple_tag
def pagination_pages(page_obj, show_all_pages=False):
    """
    Calculate pagination pages with ellipsis logic.

    Args:
        page_obj: Django Paginator page object
        show_all_pages: If True, show all pages (no ellipsis)

    Returns:
        List of page numbers and None values (for ellipsis)
    """
    if not page_obj or not hasattr(page_obj, "paginator") or not page_obj.paginator:
        return []

    num_pages = page_obj.paginator.num_pages
    if num_pages <= 1:
        return []

    current_page = page_obj.number
    pages = list(range(1, num_pages + 1))

    # Handle show_all_pages - it might come as string "True" from template
    if isinstance(show_all_pages, str):
        show_all_pages = show_all_pages.lower() in ("true", "1", "yes")

    # If show_all_pages is True, return all pages (no filtering)
    # Note: pages is always sequential from range(), so no gaps exist
    if show_all_pages:
        return pages

    # Filter pages based on distance from current page
    current_page_is_first_page = current_page == 1
    current_page_is_second_page = current_page == 2
    current_page_is_second_last_page = current_page == num_pages - 1
    current_page_is_last_page = current_page == num_pages

    filtered_pages = []
    for page in pages:
        first_page = page == 1
        last_page = page == num_pages
        is_current = page == current_page

        distance_from_current = abs(current_page - page)

        # Determine minimum distance based on current page position
        min_distance = 2
        if current_page_is_first_page or current_page_is_last_page:
            min_distance = 4
        elif current_page_is_second_page or current_page_is_second_last_page:
            min_distance = 3

        is_close_to_current = distance_from_current < min_distance

        if first_page or last_page or is_current or is_close_to_current:
            filtered_pages.append(page)

    # Add ellipsis where pages are skipped
    result = []
    last_page = 0
    for page in filtered_pages:
        if (page - last_page) > 1:
            result.append(None)  # Ellipsis
        result.append(page)
        last_page = page

    return result


@register.filter
def from_now(value):
    """
    Format a datetime as "X ago" similar to moment.js fromNow().
    Only shows the largest unit (e.g., "24 days ago" not "3 weeks, 3 days ago").
    """
    if not value:
        return ""

    try:
        # Get current time (will be naive if USE_TZ=False, aware if USE_TZ=True)
        now = timezone.now()

        # Handle different input types
        if isinstance(value, str):
            # If it's a string, try to parse it
            from django.utils.dateparse import parse_datetime

            parsed = parse_datetime(value)
            if parsed:
                value = parsed
            else:
                return ""

        # Check if value is a datetime-like object
        if not isinstance(value, datetime):
            return ""

        # When USE_TZ=False, both now and value are naive
        # When USE_TZ=True, both should be aware
        # Calculate delta directly - Python handles naive vs aware correctly
        delta = now - value

        # If in the future, return "in X"
        if delta.total_seconds() < 0:
            delta = -delta
            prefix = "in "
        else:
            prefix = ""
            suffix = " ago"

        total_seconds = delta.total_seconds()

        # Calculate different time units
        # Use rounding for days to match moment.js behavior (rounds to nearest day)
        # For other units, use floor division to match moment.js thresholds
        years = int(total_seconds // (365 * 24 * 60 * 60))
        months = int(total_seconds // (30 * 24 * 60 * 60))
        days = round(total_seconds / (24 * 60 * 60))  # Round to nearest day
        hours = int(total_seconds // (60 * 60))
        minutes = int(total_seconds // 60)

        # Return only the largest unit, matching moment.js fromNow() behavior
        # Skip weeks - use days for anything less than a month
        year_s = "s" if years != 1 else ""
        if years > 0:
            suf = suffix if prefix == "" else ""
            return f"{prefix}{years} year{year_s}{suf}"
        month_s = "s" if months != 1 else ""
        if months > 0:
            suf = suffix if prefix == "" else ""
            return f"{prefix}{months} month{month_s}{suf}"
        day_s = "s" if days != 1 else ""
        if days > 0:
            suf = suffix if prefix == "" else ""
            return f"{prefix}{days} day{day_s}{suf}"
        hour_s = "s" if hours != 1 else ""
        if hours > 0:
            suf = suffix if prefix == "" else ""
            return f"{prefix}{hours} hour{hour_s}{suf}"
        min_s = "s" if minutes != 1 else ""
        if minutes > 0:
            suf = suffix if prefix == "" else ""
            return f"{prefix}{minutes} minute{min_s}{suf}"
        else:
            return "just now"
    except Exception:
        # Return empty string on any error to prevent template errors
        # In development, you might want to log this
        return ""


@register.simple_tag
def game_rank_url(rank, game_id=None, start=None, end=None):
    """
    Generate URL for game rank route with page-based pagination.

    Args:
        rank: The rank number
        game_id: Optional game ID for highlighting
        start: Optional start year for filtering
        end: Optional end year for filtering

    Returns:
        URL string for games-list with appropriate query parameters
    """
    from django.urls import reverse
    from urllib.parse import urlencode

    # Calculate page number from rank
    # Page 1: ranks 1-100, Page 2: ranks 101-200, etc.
    page = (rank - 1) // 100 + 1

    # Build query parameters
    query_params = {
        "page": page,
    }

    if game_id:
        query_params["highlight"] = game_id

    # Convert start/end to decade or year parameter
    if start and end:
        if start == end:
            # Same year - use year parameter
            query_params["year"] = start
        elif end - start == 9:
            # Decade range - use decade parameter (format: "1990-99")
            decade_str = f"{start}-{str(end)[2:4]}"
            query_params["decade"] = decade_str
        else:
            # Custom range - use start/end
            query_params["start"] = start
            query_params["end"] = end
    elif start:
        query_params["start"] = start
    elif end:
        query_params["end"] = end

    # Build URL with query string
    base_url = reverse("games-list")
    query_string = urlencode(query_params)
    return f"{base_url}?{query_string}"


@register.filter
def tojson(value):
    """
    Convert a Python value to JSON string, safe for use in JavaScript.
    """
    return mark_safe(json.dumps(value))


@register.filter
def format_decade(value):
    """
    Format decade string for display.
    Converts "1990-99" to "1990's".
    """
    if not value:
        return ""
    # Extract the start year (e.g., "1990" from "1990-99")
    start_year = value.split("-")[0] if "-" in value else value
    return f"{start_year}'s"


@register.simple_tag(takes_context=True)
def pagination_url(context, page_num):
    """
    Generate pagination URL preserving all query parameters except 'page'.
    Returns full URL path for HTMX compatibility.

    Usage: {% pagination_url page_num=2 %}
    """
    request = context["request"]
    params = request.GET.copy()
    params["page"] = page_num
    # Return full URL path for HTMX (relative to current path)
    return f"{request.path}?{params.urlencode()}"

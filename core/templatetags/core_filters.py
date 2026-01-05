"""
Shared template filters and tags for the multi-media platform.

These are generic utilities that can be used across games, books,
and future media types.
"""

import json
from datetime import datetime

import markdown as md
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()


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
    return f"{request.path}?{params.urlencode()}"


@register.filter
def from_now(value):
    """
    Format a datetime as "X ago" similar to moment.js fromNow().
    Only shows the largest unit (e.g., "24 days ago" not "3 weeks, 3 days ago").
    """
    if not value:
        return ""

    try:
        now = timezone.now()

        # Handle string input
        if isinstance(value, str):
            from django.utils.dateparse import parse_datetime

            parsed = parse_datetime(value)
            if parsed:
                value = parsed
            else:
                return ""

        if not isinstance(value, datetime):
            return ""

        delta = now - value

        # If in the future, return "in X"
        if delta.total_seconds() < 0:
            delta = -delta
            prefix = "in "
            suffix = ""
        else:
            prefix = ""
            suffix = " ago"

        total_seconds = delta.total_seconds()

        years = int(total_seconds // (365 * 24 * 60 * 60))
        months = int(total_seconds // (30 * 24 * 60 * 60))
        days = round(total_seconds / (24 * 60 * 60))
        hours = int(total_seconds // (60 * 60))
        minutes = int(total_seconds // 60)

        if years > 0:
            s = "s" if years != 1 else ""
            return f"{prefix}{years} year{s}{suffix}"
        if months > 0:
            s = "s" if months != 1 else ""
            return f"{prefix}{months} month{s}{suffix}"
        if days > 0:
            s = "s" if days != 1 else ""
            return f"{prefix}{days} day{s}{suffix}"
        if hours > 0:
            s = "s" if hours != 1 else ""
            return f"{prefix}{hours} hour{s}{suffix}"
        if minutes > 0:
            s = "s" if minutes != 1 else ""
            return f"{prefix}{minutes} minute{s}{suffix}"
        return "just now"
    except Exception:
        return ""


@register.filter
def tojson(value):
    """Convert a Python value to JSON string, safe for use in JavaScript."""
    return mark_safe(json.dumps(value))


@register.filter
def format_duration(seconds):
    """
    Format duration in seconds to human-readable string.
    Examples: "30s", "2m 30s", "1h 15m"
    """
    if not seconds or seconds < 0:
        return "0s"

    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    elif minutes > 0:
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        return f"{secs}s"


@register.filter
def markdown(value):
    """Convert markdown text to HTML."""
    if not value:
        return ""
    return mark_safe(md.markdown(value))


@register.filter
def format_decade(value):
    """
    Format decade string for display.
    Converts "1990-99" to "1990s".
    """
    if not value:
        return ""
    # Extract the start year (e.g., "1990" from "1990-99")
    start_year = value.split("-")[0] if "-" in value else value
    return f"{start_year}s"

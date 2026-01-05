"""
Book-specific template filters and tags.

For shared filters (pagination_pages, from_now, tojson, etc.), use:
    {% load core_filters %}

This module provides book-specific utilities like genre icons, page count
formatting, author helpers, and other book-related template helpers.
"""

from django import template

from games import constants

# Re-export shared filters for backward compatibility
# Templates using {% load book_filters %} can continue to use these
from core.templatetags.core_filters import (
    format_decade,
    format_duration,
    from_now,
    markdown,
    pagination_pages,
    pagination_url,
    tojson,
)

register = template.Library()

# Re-register the shared filters/tags so they work with {% load book_filters %}
register.filter("from_now", from_now)
register.filter("tojson", tojson)
register.filter("format_duration", format_duration)
register.filter("markdown", markdown)
register.filter("format_decade", format_decade)
register.simple_tag(pagination_pages, name="pagination_pages")
register.simple_tag(takes_context=True, name="pagination_url")(pagination_url)


@register.filter
def get_list_type_label(type_code):
    """Convert list type code to human-readable label."""
    type_dict = dict(constants.LIST_TYPES)
    return type_dict.get(type_code, type_code)


@register.filter
def get_list_type_badge_class(type_code):
    """Return DaisyUI badge class for list type."""
    badge_classes = {
        constants.LIST_ALLTIME: "badge-info font-semibold",
        constants.LIST_DECADE: "badge-success font-semibold",
        constants.LIST_MISC: "badge-warning font-semibold",
        constants.LIST_EOY: "badge-error font-semibold",
    }
    return badge_classes.get(type_code, "badge-ghost")


# Book genre category icons
# Maps top-level genre categories to MDI icon classes
BOOK_GENRE_ICONS = {
    # Fiction categories
    "Fiction": "mdi-book-open-page-variant",
    "Non-Fiction": "mdi-file-document-outline",
    # Major fiction genres
    "Science Fiction": "mdi-rocket-launch",
    "Fantasy": "mdi-sword-cross",
    "Mystery": "mdi-magnify",
    "Thriller": "mdi-alert-circle",
    "Romance": "mdi-heart",
    "Horror": "mdi-ghost",
    "Historical Fiction": "mdi-castle",
    "Literary Fiction": "mdi-feather",
    "Adventure": "mdi-compass",
    "Humor": "mdi-emoticon-happy",
    "Young Adult": "mdi-account-group",
    "Children's": "mdi-baby-carriage",
    "Dystopian": "mdi-city-variant",
    "Crime": "mdi-police-badge",
    "Graphic Novel": "mdi-image-multiple",
    "Short Stories": "mdi-text-short",
    # Non-fiction genres
    "Biography": "mdi-account",
    "Memoir": "mdi-notebook",
    "History": "mdi-book-clock",
    "Science": "mdi-atom",
    "Philosophy": "mdi-head-lightbulb",
    "Psychology": "mdi-brain",
    "Self-Help": "mdi-arm-flex",
    "Business": "mdi-briefcase",
    "Travel": "mdi-airplane",
    "True Crime": "mdi-skull-crossbones",
    "Essays": "mdi-script-text",
    "Poetry": "mdi-text-recognition",
    "Art": "mdi-palette",
    "Music": "mdi-music",
    "Sports": "mdi-basketball",
    "Cooking": "mdi-chef-hat",
    "Health": "mdi-hospital-box",
    "Religion": "mdi-church",
    "Politics": "mdi-gavel",
    "Nature": "mdi-leaf",
    "Technology": "mdi-laptop",
    "Education": "mdi-school",
    "Reference": "mdi-book-alphabet",
}

# Default icon for genres not in the mapping
DEFAULT_BOOK_GENRE_ICON = "mdi-book"


@register.filter
def book_genre_icon(genre):
    """
    Get the MDI icon class for a book genre.

    Args:
        genre: BookGenre object or genre name string

    Returns:
        MDI icon class string (e.g., 'mdi-rocket-launch') or default icon
    """
    # If it's a string, look it up directly
    if isinstance(genre, str):
        return BOOK_GENRE_ICONS.get(genre, DEFAULT_BOOK_GENRE_ICON)

    # Check if the genre has an explicit icon_name set
    if hasattr(genre, "icon_name") and genre.icon_name:
        return genre.icon_name

    # Check if genre has a parent (category)
    if hasattr(genre, "parent") and genre.parent:
        # First try the specific genre name
        if hasattr(genre, "name"):
            icon = BOOK_GENRE_ICONS.get(genre.name)
            if icon:
                return icon
        # Then try the parent category name
        category_name = genre.parent.name
        return BOOK_GENRE_ICONS.get(category_name, DEFAULT_BOOK_GENRE_ICON)

    # Check if the genre itself is a category (level 0)
    if hasattr(genre, "level") and genre.level == 0:
        return BOOK_GENRE_ICONS.get(genre.name, DEFAULT_BOOK_GENRE_ICON)

    # If genre has a name, check if it matches a known genre
    if hasattr(genre, "name"):
        return BOOK_GENRE_ICONS.get(genre.name, DEFAULT_BOOK_GENRE_ICON)

    return DEFAULT_BOOK_GENRE_ICON


@register.filter
def book_genres_grouped(genres):
    """
    Group book genres by their parent category with metadata for display.

    Returns list of dicts with:
    - icon: MDI icon class
    - name: Category display name
    - count: Number of genres in this category
    - genre_ids_str: Comma-separated genre IDs for filtering
    - tooltip: Full genre names for tooltip display
    """
    categories = {}

    for genre in genres:
        # Determine the category
        if hasattr(genre, "parent") and genre.parent:
            category_name = genre.parent.name
        elif hasattr(genre, "level") and genre.level == 0:
            category_name = genre.name
        else:
            category_name = "Other"

        if category_name not in categories:
            icon = BOOK_GENRE_ICONS.get(category_name, DEFAULT_BOOK_GENRE_ICON)
            categories[category_name] = {
                "icon": icon,
                "name": category_name,
                "genre_ids": [],
                "genre_names": [],
            }

        genre_id = genre.id if hasattr(genre, "id") else None
        genre_name = genre.name if hasattr(genre, "name") else str(genre)

        if genre_id:
            categories[category_name]["genre_ids"].append(str(genre_id))
        categories[category_name]["genre_names"].append(genre_name)

    # Build final list with computed fields
    result = []
    for data in categories.values():
        data["count"] = len(data["genre_names"])
        data["genre_ids_str"] = ",".join(data["genre_ids"])
        data["tooltip"] = ", ".join(data["genre_names"])
        result.append(data)

    return result


@register.filter
def format_page_count(page_count):
    """
    Format page count for display.

    Args:
        page_count: Integer number of pages

    Returns:
        Formatted string (e.g., "342 pages", "1 page", or empty string if None)
    """
    if page_count is None:
        return ""
    try:
        page_count = int(page_count)
        if page_count == 1:
            return "1 page"
        return f"{page_count:,} pages"
    except (ValueError, TypeError):
        return ""


@register.filter
def format_page_count_short(page_count):
    """
    Format page count for compact display.

    Args:
        page_count: Integer number of pages

    Returns:
        Formatted string (e.g., "342pp", "1.2k pp" for large books)
    """
    if page_count is None:
        return ""
    try:
        page_count = int(page_count)
        if page_count >= 1000:
            return f"{page_count / 1000:.1f}k pp"
        return f"{page_count}pp"
    except (ValueError, TypeError):
        return ""


@register.filter
def estimated_reading_time(page_count, pages_per_hour=30):
    """
    Estimate reading time based on page count.

    Args:
        page_count: Integer number of pages
        pages_per_hour: Reading speed (default 30 pages/hour, ~250 words/min)

    Returns:
        Formatted string (e.g., "~8 hours", "~30 min")
    """
    if page_count is None:
        return ""
    try:
        page_count = int(page_count)
        hours = page_count / pages_per_hour

        if hours < 1:
            minutes = round(hours * 60)
            return f"~{minutes} min"
        elif hours < 24:
            return f"~{round(hours)} hours"
        else:
            days = hours / 8  # Assuming 8 hours of reading per day
            return f"~{round(days)} days"
    except (ValueError, TypeError):
        return ""


@register.simple_tag
def book_rank_url(rank, book_id=None, start=None, end=None):
    """
    Generate URL for book rank with highlight for smooth scrolling.

    Args:
        rank: The rank number (unused, kept for consistency with game_rank_url)
        book_id: Optional book ID for highlighting
        start: Optional start year for filtering
        end: Optional end year for filtering

    Returns:
        URL string for books home with appropriate query parameters
    """
    from urllib.parse import urlencode

    from django.urls import reverse

    # Build query parameters
    query_params = {}

    if book_id:
        query_params["highlight"] = book_id

    if start:
        query_params["start"] = start
    if end:
        query_params["end"] = end

    # Build URL with query string
    try:
        base_url = reverse("books:home")
    except Exception:
        base_url = "/books/"

    if query_params:
        query_string = urlencode(query_params)
        return f"{base_url}?{query_string}"
    return base_url


@register.filter
def get_author_ids(book_author_map, book_id):
    """
    Get the list of author IDs for a book from the book->author mapping.

    Args:
        book_author_map: Dict mapping book_id -> list of author_ids
        book_id: The book ID to look up

    Returns:
        List of author IDs, or empty list if not found
    """
    if not book_author_map or not isinstance(book_author_map, dict):
        return []
    return book_author_map.get(book_id, [])


@register.filter
def child_author_ids(sub_authors):
    """
    Extract author IDs from a list of sub_author dicts.

    Args:
        sub_authors: List of dicts with 'author' key containing Author objects

    Returns:
        List of author IDs
    """
    if not sub_authors:
        return []
    return [a["author"].id for a in sub_authors if "author" in a]


@register.filter
def format_series_position(position):
    """
    Format a series position for display.

    Args:
        position: Decimal or int position (e.g., 1, 2.5 for novellas)

    Returns:
        Formatted string (e.g., "#1", "#2.5")
    """
    if position is None:
        return ""
    try:
        position = float(position)
        # If it's a whole number, display without decimal
        if position == int(position):
            return f"#{int(position)}"
        return f"#{position}"
    except (ValueError, TypeError):
        return ""


@register.filter
def format_rating(rating):
    """
    Format a Goodreads rating for display.

    Args:
        rating: Decimal rating (0.00-5.00)

    Returns:
        Formatted string (e.g., "4.5/5", "3.8/5")
    """
    if rating is None:
        return ""
    try:
        rating = float(rating)
        return f"{rating:.1f}/5"
    except (ValueError, TypeError):
        return ""


@register.filter
def format_rating_count(count):
    """
    Format rating/review count for compact display.

    Args:
        count: Integer count of ratings

    Returns:
        Formatted string (e.g., "1.2M", "45K", "892")
    """
    if count is None:
        return ""
    try:
        count = int(count)
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)
    except (ValueError, TypeError):
        return ""


@register.filter
def rank_pct(rank, total):
    """
    Calculate rank position as percentage (higher rank = higher percentage).
    Rank 1 = 100%, Rank N = close to 0%.
    """
    if not rank or not total or total <= 1:
        return 0
    return round((1 - (rank - 1) / (total - 1)) * 100)

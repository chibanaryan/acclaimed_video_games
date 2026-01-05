"""
Book-specific template filters and tags.

For shared filters (pagination_pages, from_now, tojson, etc.), use:
    {% load core_filters %}

This module provides book-specific utilities like genre icons,
page count formatting, reading time estimates, and other book-related
template helpers.
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


# Book genre category icons - maps root genre categories to MDI icons
# These are different from game genres since books use Fiction/Non-Fiction taxonomy
BOOK_GENRE_CATEGORY_ICONS = {
    # Fiction categories
    "Fiction": "mdi-book-open-page-variant",
    "Literary Fiction": "mdi-feather",
    "Science Fiction": "mdi-rocket-launch",
    "Fantasy": "mdi-wizard-hat",
    "Mystery": "mdi-magnify",
    "Thriller": "mdi-knife-military",
    "Horror": "mdi-skull",
    "Romance": "mdi-heart",
    "Historical Fiction": "mdi-castle",
    "Adventure": "mdi-compass",
    "Crime": "mdi-police-badge",
    "Dystopian": "mdi-city-variant",
    "Young Adult": "mdi-account-school",
    "Children's": "mdi-teddy-bear",
    # Non-Fiction categories
    "Non-Fiction": "mdi-bookshelf",
    "Biography": "mdi-account-circle",
    "Memoir": "mdi-notebook",
    "Autobiography": "mdi-account-star",
    "History": "mdi-clock-outline",
    "Science": "mdi-flask",
    "Philosophy": "mdi-head-question",
    "Psychology": "mdi-head-cog",
    "Self-Help": "mdi-lightbulb-on",
    "Business": "mdi-briefcase",
    "Travel": "mdi-airplane",
    "True Crime": "mdi-handcuffs",
    "Politics": "mdi-vote",
    "Religion": "mdi-book-cross",
    "Art": "mdi-palette",
    "Cooking": "mdi-chef-hat",
    "Sports": "mdi-basketball",
    "Nature": "mdi-leaf",
    "Technology": "mdi-chip",
    # Poetry and Drama
    "Poetry": "mdi-text-box-multiple",
    "Drama": "mdi-drama-masks",
    "Graphic Novel": "mdi-image-multiple",
    "Comics": "mdi-comment-text-multiple",
}

# Default icon for genres without specific mapping
DEFAULT_BOOK_GENRE_ICON = "mdi-book"


@register.filter
def book_genre_icon(genre):
    """
    Get the MDI icon class for a book genre based on its category.

    Args:
        genre: BookGenre object with 'parent' attribute or category name string

    Returns:
        MDI icon class string (e.g., 'mdi-rocket-launch') or default 'mdi-book'
    """
    # If it's a string, check if it's a category name directly
    if isinstance(genre, str):
        return BOOK_GENRE_CATEGORY_ICONS.get(genre, DEFAULT_BOOK_GENRE_ICON)

    # Check if genre has a parent (category)
    if hasattr(genre, "parent") and genre.parent:
        category_name = genre.parent.name
        return BOOK_GENRE_CATEGORY_ICONS.get(category_name, DEFAULT_BOOK_GENRE_ICON)

    # Check if the genre itself is a category (level 0)
    if hasattr(genre, "level") and genre.level == 0:
        return BOOK_GENRE_CATEGORY_ICONS.get(genre.name, DEFAULT_BOOK_GENRE_ICON)

    # If genre has an icon_name field, use it
    if hasattr(genre, "icon_name") and genre.icon_name:
        return genre.icon_name

    # If genre has a name, check if it matches a category
    if hasattr(genre, "name"):
        return BOOK_GENRE_CATEGORY_ICONS.get(genre.name, DEFAULT_BOOK_GENRE_ICON)

    return DEFAULT_BOOK_GENRE_ICON


@register.filter
def book_genre_categories_grouped(genres):
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
            icon = BOOK_GENRE_CATEGORY_ICONS.get(category_name, DEFAULT_BOOK_GENRE_ICON)
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
        page_count: Number of pages (int or None)

    Returns:
        Formatted string like "324 pages" or "~320 pages" for estimates,
        or empty string if None
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
def reading_time_estimate(page_count, words_per_minute=250):
    """
    Estimate reading time based on page count.

    Assumes average of 250 words per page and default reading speed
    of 250 words per minute (adjustable).

    Args:
        page_count: Number of pages
        words_per_minute: Reading speed (default: 250 wpm)

    Returns:
        Human-readable duration like "2h 30m" or "~45m"
    """
    if page_count is None:
        return ""
    try:
        page_count = int(page_count)
        words_per_minute = int(words_per_minute)
        if page_count <= 0 or words_per_minute <= 0:
            return ""

        # Average 250 words per page
        total_words = page_count * 250
        minutes = total_words / words_per_minute

        hours = int(minutes // 60)
        remaining_minutes = int(minutes % 60)

        if hours > 0:
            if remaining_minutes > 0:
                return f"~{hours}h {remaining_minutes}m"
            return f"~{hours}h"
        return f"~{remaining_minutes}m"
    except (ValueError, TypeError):
        return ""


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


@register.simple_tag
def book_rank_url(rank, book_id=None, start=None, end=None):
    """
    Generate URL for book rank with highlight for smooth scrolling.

    The books list uses infinite scroll with dynamic page sizing. When a highlight
    parameter is provided, the view automatically loads enough books to include
    the highlighted one, then smooth scrolls to it.

    Args:
        rank: The rank number (unused, kept for API compatibility with games)
        book_id: Optional book ID for highlighting
        start: Optional start year for filtering
        end: Optional end year for filtering

    Returns:
        URL string for books home with appropriate query parameters
    """
    from urllib.parse import urlencode

    from django.urls import reverse

    # Build query parameters - no page needed, view handles dynamic loading
    query_params = {}

    if book_id:
        query_params["highlight"] = book_id

    # Always use start/end parameters for year filtering
    if start:
        query_params["start"] = start
    if end:
        query_params["end"] = end

    # Build URL with query string
    base_url = reverse("books:home")
    if query_params:
        query_string = urlencode(query_params)
        return f"{base_url}?{query_string}"
    return base_url


@register.filter
def author_display_name(author):
    """
    Get display name for an author, including parent if applicable.

    Args:
        author: Author object

    Returns:
        Display name string
    """
    if not author:
        return ""
    if hasattr(author, "parent") and author.parent:
        return f"{author.name} ({author.parent.name})"
    return author.name if hasattr(author, "name") else str(author)


@register.filter
def format_author_list(authors, max_display=3):
    """
    Format a list of authors for display.

    Args:
        authors: QuerySet or list of Author objects
        max_display: Maximum number of authors to show before truncating

    Returns:
        Formatted string like "Author One, Author Two & 3 more"
    """
    if not authors:
        return ""

    author_list = list(authors)
    if not author_list:
        return ""

    try:
        max_display = int(max_display)
    except (ValueError, TypeError):
        max_display = 3

    if len(author_list) <= max_display:
        names = [a.name for a in author_list if hasattr(a, "name")]
        return ", ".join(names)

    # Show first (max_display - 1) authors plus "& X more"
    visible_count = max_display - 1
    visible_names = [a.name for a in author_list[:visible_count] if hasattr(a, "name")]
    remaining = len(author_list) - visible_count
    return ", ".join(visible_names) + f" & {remaining} more"


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
def book_series_label(book):
    """
    Get formatted series label for a book.

    Args:
        book: Book object with series and series_position fields

    Returns:
        String like "Harry Potter #1" or "A Song of Ice and Fire #3.5"
        or empty string if not part of a series
    """
    if not book or not hasattr(book, "series") or not book.series:
        return ""

    series_name = book.series.name
    position = getattr(book, "series_position", None)

    if position is not None:
        # Format position - remove trailing .0 for whole numbers
        if position == int(position):
            position_str = str(int(position))
        else:
            position_str = str(position)
        return f"{series_name} #{position_str}"

    return series_name


@register.filter
def isbn_display(isbn):
    """
    Format ISBN for display with hyphens.

    Args:
        isbn: ISBN-10 or ISBN-13 string

    Returns:
        Formatted ISBN string or original if formatting fails
    """
    if not isbn:
        return ""

    # Remove any existing hyphens or spaces
    isbn = str(isbn).replace("-", "").replace(" ", "")

    # ISBN-13 format: 978-1-234-56789-0
    if len(isbn) == 13:
        return f"{isbn[:3]}-{isbn[3]}-{isbn[4:7]}-{isbn[7:12]}-{isbn[12]}"

    # ISBN-10 format: 1-234-56789-0
    if len(isbn) == 10:
        return f"{isbn[0]}-{isbn[1:4]}-{isbn[4:9]}-{isbn[9]}"

    return isbn


@register.filter
def rating_stars(rating, max_stars=5):
    """
    Generate star rating data for template rendering.

    Args:
        rating: Decimal or float rating (e.g., 4.25)
        max_stars: Maximum number of stars (default: 5)

    Returns:
        Dict with 'full', 'half', 'empty' counts and 'percentage' for display
    """
    if rating is None:
        return {"full": 0, "half": 0, "empty": max_stars, "percentage": 0}

    try:
        rating = float(rating)
        max_stars = int(max_stars)
        if rating < 0:
            rating = 0
        if rating > max_stars:
            rating = max_stars

        full_stars = int(rating)
        remainder = rating - full_stars
        half_star = 1 if remainder >= 0.25 and remainder < 0.75 else 0
        if remainder >= 0.75:
            full_stars += 1
            half_star = 0
        empty_stars = max_stars - full_stars - half_star

        return {
            "full": full_stars,
            "half": half_star,
            "empty": empty_stars,
            "percentage": round((rating / max_stars) * 100),
        }
    except (ValueError, TypeError):
        return {"full": 0, "half": 0, "empty": max_stars, "percentage": 0}

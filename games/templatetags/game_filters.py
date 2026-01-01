from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
from datetime import datetime
import json
import markdown as md

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
    Generate URL for game rank with highlight for smooth scrolling.

    The games list uses infinite scroll with dynamic page sizing. When a highlight
    parameter is provided, the view automatically loads enough games to include
    the highlighted one, then smooth scrolls to it.

    Args:
        rank: The rank number (unused, kept for backward compatibility)
        game_id: Optional game ID for highlighting
        start: Optional start year for filtering
        end: Optional end year for filtering

    Returns:
        URL string for home with appropriate query parameters
    """
    from django.urls import reverse
    from urllib.parse import urlencode

    # Build query parameters - no page needed, view handles dynamic loading
    query_params = {}

    if game_id:
        query_params["highlight"] = game_id

    # Always use start/end parameters for year filtering
    if start:
        query_params["start"] = start
    if end:
        query_params["end"] = end

    # Build URL with query string
    base_url = reverse("home")
    if query_params:
        query_string = urlencode(query_params)
        return f"{base_url}?{query_string}"
    return base_url


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
    Converts "1990-99" to "1990s".
    """
    if not value:
        return ""
    # Extract the start year (e.g., "1990" from "1990-99")
    start_year = value.split("-")[0] if "-" in value else value
    return f"{start_year}s"


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


# Platform family mappings - code to family key
PLATFORM_FAMILIES = {
    # Nintendo
    "SW": "nintendo",  # Nintendo Switch
    "WiiU": "nintendo",
    "Wii": "nintendo",
    "GC": "nintendo",
    "N64": "nintendo",
    "SNES": "nintendo",
    "NES": "nintendo",
    "GB": "nintendo",
    "GBC": "nintendo",
    "GBA": "nintendo",
    "DS": "nintendo",  # Nintendo DS
    "3DS": "nintendo",
    "FDS": "nintendo",  # Famicom Disk System
    # PlayStation
    "PS5": "playstation",
    "PS4": "playstation",
    "PS3": "playstation",
    "PS2": "playstation",
    "PS": "playstation",
    "PSP": "playstation",
    "PSV": "playstation",  # PlayStation Vita
    "PSVR": "playstation",  # PlayStation VR
    # Xbox
    "XBXS": "xbox",  # Xbox Series X/S
    "XB1": "xbox",  # Xbox One
    "X360": "xbox",
    "Xbox": "xbox",
    # Sega
    "GEN": "sega",
    "DC": "sega",
    "SAT": "sega",
    "SMS": "sega",
    "GG": "sega",
    "SCD": "sega",  # Sega CD
    # PC
    "WIN": "pc",
    "DOS": "pc",
    "LIN": "pc",
    "MAC": "pc",
    # Retro consoles
    "A26": "retro",
    "A52": "retro",
    "A78": "retro",
    "INTV": "retro",
    "CV": "retro",
    "TG16": "retro",
    "3DO": "retro",
    "NG": "retro",
    "JAG": "retro",
    "LYNX": "retro",
    # Microcomputers
    "C64": "computers",
    "AMI": "computers",
    "CD32": "computers",
    "MSX": "computers",
    "CPC": "computers",
    "ZXS": "computers",
    "AST": "computers",
    "BBCM": "computers",
    "PC88": "computers",
    "PC98": "computers",
    "FMT": "computers",
    "FM7": "computers",
    "SX1": "computers",
    "T80": "computers",
    "TCC": "computers",
    "VC20": "computers",
    "A8": "computers",
    "A2": "computers",
    "ARCH": "computers",  # Acorn Archimedes
    "E60": "computers",  # Electronika 60
    "HP21": "computers",  # HP 2100
    "PDP": "computers",  # DEC PDP
    # Arcade/Mobile/VR
    "ARC": "arcade",
    "AND": "arcade",
    "iOS": "arcade",
    "LMD": "arcade",
    "VR": "arcade",
    "BR": "arcade",
}

# Family display info - key to (icon_class, display_name, sort_order, svg_icon)
# svg_icon is optional - if provided, use SVG instead of MDI icon
FAMILY_INFO = {
    "nintendo": ("mdi-nintendo-switch", "Nintendo", 1, None),
    "playstation": ("mdi-sony-playstation", "PlayStation", 2, None),
    "xbox": ("mdi-microsoft-xbox", "Xbox", 3, None),
    "pc": ("mdi-microsoft-windows", "PC", 4, None),
    "sega": (None, "Sega", 5, "platform-sega"),
    "retro": ("mdi-television-classic", "Retro", 6, None),
    "computers": ("mdi-desktop-classic", "Microcomputers", 7, None),
    "arcade": ("mdi-space-invaders", "Arcade+", 8, None),
}


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
def platform_families(platforms):
    """
    Convert a list of platforms to unique families with icons.
    Returns list of dicts with 'icon', 'svg_icon', 'name', 'key', 'platform_id',
    'platform_name'. The platform_id and platform_name are from the first platform
    in each family. Order is preserved based on encounter order in the platforms list.
    """
    seen_families = set()
    families = []

    for platform in platforms:
        code = platform.code if hasattr(platform, "code") else str(platform)
        family_key = PLATFORM_FAMILIES.get(code, "other")

        if family_key not in seen_families and family_key in FAMILY_INFO:
            seen_families.add(family_key)
            icon, name, order, svg_icon = FAMILY_INFO[family_key]
            # Get platform ID and name for linking and tooltip
            platform_id = platform.id if hasattr(platform, "id") else None
            platform_name = platform.name if hasattr(platform, "name") else code
            families.append(
                {
                    "icon": icon,
                    "svg_icon": svg_icon,
                    "name": name,
                    "key": family_key,
                    "order": order,
                    "platform_id": platform_id,
                    "platform_name": platform_name,
                }
            )

    # Preserve encounter order (no sorting)
    return families


@register.filter
def platform_families_grouped(platforms):
    """
    Group platforms by family with full metadata for display.
    Returns list of dicts with:
    - icon: MDI icon class
    - svg_icon: SVG symbol ID (if applicable)
    - name: Family display name (e.g., "PlayStation")
    - key: Family key
    - count: Number of platforms in this family
    - platform_ids_str: Comma-separated platform IDs for filtering
    - tooltip: Full platform names for tooltip display
    - order: Sort order
    """
    families = {}

    for platform in platforms:
        code = platform.code if hasattr(platform, "code") else str(platform)
        family_key = PLATFORM_FAMILIES.get(code)

        if family_key is None or family_key not in FAMILY_INFO:
            continue

        if family_key not in families:
            icon, name, order, svg_icon = FAMILY_INFO[family_key]
            families[family_key] = {
                "icon": icon,
                "svg_icon": svg_icon,
                "name": name,
                "key": family_key,
                "order": order,
                "platform_ids": [],
                "platform_names": [],
            }

        platform_id = platform.id if hasattr(platform, "id") else None
        platform_name = platform.name if hasattr(platform, "name") else code

        if platform_id:
            families[family_key]["platform_ids"].append(str(platform_id))
        families[family_key]["platform_names"].append(platform_name)

    # Build final list with computed fields
    result = []
    for data in families.values():
        data["count"] = len(data["platform_names"])
        data["platform_ids_str"] = ",".join(data["platform_ids"])
        data["tooltip"] = ", ".join(data["platform_names"])
        result.append(data)

    return result


@register.filter
def markdown(value):
    """Convert markdown text to HTML."""
    if not value:
        return ""
    return mark_safe(md.markdown(value))


@register.filter
def rank_pct(rank, total):
    """
    Calculate rank position as percentage (higher rank = higher percentage).
    Rank 1 = 100%, Rank N = close to 0%.
    """
    if not rank or not total or total <= 1:
        return 0
    return round((1 - (rank - 1) / (total - 1)) * 100)


@register.filter
def platform_icon(platform):
    """
    Get the MDI icon class for a platform based on its family.

    Args:
        platform: Platform object with 'code' attribute

    Returns:
        MDI icon class string (e.g., 'mdi-nintendo-switch') or None for SVG icons
    """
    code = platform.code if hasattr(platform, "code") else str(platform)
    family_key = PLATFORM_FAMILIES.get(code, "other")
    if family_key in FAMILY_INFO:
        icon, _, _, _ = FAMILY_INFO[family_key]
        return icon
    return None


@register.filter
def platform_svg_icon(platform):
    """
    Get the SVG icon ID for a platform based on its family (for Sega, etc.).

    Args:
        platform: Platform object with 'code' attribute

    Returns:
        SVG icon ID string (e.g., 'platform-sega') or None if using MDI icon
    """
    code = platform.code if hasattr(platform, "code") else str(platform)
    family_key = PLATFORM_FAMILIES.get(code, "other")
    if family_key in FAMILY_INFO:
        _, _, _, svg_icon = FAMILY_INFO[family_key]
        return svg_icon
    return None


# Genre category icons - matches the filter components
GENRE_CATEGORY_ICONS = {
    "Action": "mdi-crosshairs",
    "Adventure": "mdi-image-filter-hdr",
    "Role-Playing": "mdi-wizard-hat",
    "Strategy": "mdi-chess-knight",
    "Simulation": "mdi-car-sports",
    "Sports": "mdi-basketball",
    "Puzzle": "mdi-puzzle",
    "Party & Casual": "mdi-party-popper",
    "Hybrid & Specialized": "mdi-layers",
}


@register.filter
def genre_categories_grouped(genres):
    """
    Group genres by their parent category with metadata for display.
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
            icon = GENRE_CATEGORY_ICONS.get(category_name, "mdi-gamepad-variant")
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
def genre_icon(genre):
    """
    Get the MDI icon class for a genre based on its category (parent).

    Args:
        genre: WikipediaGenre object with 'parent' attribute or category name string

    Returns:
        MDI icon class string (e.g., 'mdi-crosshairs') or default 'mdi-gamepad-variant'
    """
    # If it's a string, check if it's a category name directly
    if isinstance(genre, str):
        return GENRE_CATEGORY_ICONS.get(genre, "mdi-gamepad-variant")

    # Check if genre has a parent (category)
    if hasattr(genre, "parent") and genre.parent:
        category_name = genre.parent.name
        return GENRE_CATEGORY_ICONS.get(category_name, "mdi-gamepad-variant")

    # Check if the genre itself is a category (level 0)
    if hasattr(genre, "level") and genre.level == 0:
        return GENRE_CATEGORY_ICONS.get(genre.name, "mdi-gamepad-variant")

    # If genre has a name, check if it matches a category
    if hasattr(genre, "name"):
        return GENRE_CATEGORY_ICONS.get(genre.name, "mdi-gamepad-variant")

    return "mdi-gamepad-variant"

"""
Game-specific template filters and tags.

This module provides game-specific utilities like platform icons, genre icons,
list type badges, and other game-related template helpers.

NOTE: This taglib also includes common filters from core_filters for convenience.
Templates only need to load game_filters to access both game-specific filters
and common filters like from_now, tojson, pagination_pages, etc.
Alternatively, use {% load core_filters %} for just the common filters.
"""

from django import template

from games import constants

# Import shared filters to make them available via {% load game_filters %}
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

# Register shared filters/tags so they work with {% load game_filters %}
# This allows templates to use one load directive for all game-related functionality
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


def _platform_sort_key(platform):
    """
    Sort key for platforms: (year_start, year_end, name).
    None values sort to end (9999).
    """
    year_start = getattr(platform, "year_start", None) or 9999
    year_end = getattr(platform, "year_end", None) or 9999
    name = getattr(platform, "name", "") or ""
    return (year_start, year_end, name)


@register.filter
def platform_families_grouped(platforms):
    """
    Group platforms by family with full metadata for display.
    Platforms within each family are sorted by (year_start, year_end, name).
    Families are ordered by their first platform's sort position.

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
                "platform_codes": [],
                "platforms": [],  # Individual platform data for text display
                "_platform_objects": [],  # Keep originals for sorting
            }

        families[family_key]["_platform_objects"].append(platform)

    # Sort platforms within each family and build display data
    result = []
    for data in families.values():
        # Sort platforms by (year_start, year_end, name)
        sorted_platforms = sorted(data["_platform_objects"], key=_platform_sort_key)

        # Build display data from sorted platforms
        for platform in sorted_platforms:
            code = platform.code if hasattr(platform, "code") else str(platform)
            platform_id = platform.id if hasattr(platform, "id") else None
            platform_name = platform.name if hasattr(platform, "name") else code

            if platform_id:
                data["platform_ids"].append(str(platform_id))
            data["platform_names"].append(platform_name)
            data["platform_codes"].append(code)
            data["platforms"].append(
                {
                    "code": code,
                    "id": str(platform_id) if platform_id else "",
                    "name": platform_name,
                }
            )

        data["count"] = len(data["platform_names"])
        data["platform_ids_str"] = ",".join(data["platform_ids"])
        data["tooltip"] = ", ".join(data["platform_names"])

        # Store first platform's sort key for family ordering
        if sorted_platforms:
            data["_first_sort_key"] = _platform_sort_key(sorted_platforms[0])
        else:
            data["_first_sort_key"] = (9999, 9999, "")

        # Clean up internal fields
        del data["_platform_objects"]
        result.append(data)

    # Sort families by their first platform's sort position
    result.sort(key=lambda f: f["_first_sort_key"])

    # Clean up sort key from output
    for data in result:
        del data["_first_sort_key"]

    return result


@register.filter
def format_playtime(hours):
    """
    Format playtime hours for display.
    If less than 1 hour, shows minutes (e.g., "~30m").
    If 1 hour or more, shows hours (e.g., "~10h").
    """
    if hours is None:
        return ""
    try:
        hours = float(hours)
        if hours < 1:
            minutes = round(hours * 60)
            return f"~{minutes}m"
        else:
            return f"~{round(hours)}h"
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


@register.filter
def get_developer_ids(game_developer_map, game_id):
    """
    Get the list of developer IDs for a game from the game->developer mapping.

    Args:
        game_developer_map: Dict mapping game_id -> list of developer_ids
        game_id: The game ID to look up

    Returns:
        List of developer IDs, or empty list if not found
    """
    if not game_developer_map or not isinstance(game_developer_map, dict):
        return []
    return game_developer_map.get(game_id, [])


@register.filter
def child_developer_ids(sub_developers):
    """
    Extract developer IDs from a list of sub_developer dicts.

    Args:
        sub_developers: List of dicts with 'developer' key containing Developer objects

    Returns:
        List of developer IDs
    """
    if not sub_developers:
        return []
    return [d["developer"].id for d in sub_developers if "developer" in d]


@register.simple_tag
def has_published_articles():
    """Check if there are any published articles."""
    from games.models import Article

    return Article.objects.filter(status=Article.Status.PUBLISHED).exists()

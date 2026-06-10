"""
Landing page definitions for SEO "best of" pages.

Single source of truth for which landing pages exist (/games/...), shared
by the views, sitemap, and index page. Pages are generated for root
genres, platforms with enough games, and years/decades with enough games.
"""

from typing import Any, Dict, List, Optional, Tuple

from django.core.cache import cache
from django.db.models import Count

from games import config, models, utils

# Number of games shown on each landing page
TOP_N = 25

# Minimum game counts for a page to exist (avoids thin content)
MIN_PLATFORM_GAMES = 25
MIN_YEAR_GAMES = 10

# Decades with substantial coverage (the 1970s have too few games)
DECADES = [1980, 1990, 2000, 2010, 2020]

# Manufacturer-family pages. The platform codes must match the groups in
# views._build_platform_segment / the JS PLATFORM_GROUPS so that selecting
# exactly these platforms produces the family label ("PC", "Nintendo") in
# the generated title, and the UI's family-group selection maps to the page.
FAMILY_PAGES = {
    "pc": ("PC", ["WIN", "DOS", "LIN", "MAC"]),
    "nintendo": (
        "Nintendo",
        [
            "NES",
            "SNES",
            "N64",
            "GC",
            "Wii",
            "WiiU",
            "DS",
            "3DS",
            "SW",
            "SW2",
            "GB",
            "GBA",
            "GBC",
            "FDS",
        ],
    ),
    "playstation": (
        "PlayStation",
        ["PS", "PS2", "PS3", "PS4", "PS5", "PSP", "PSV", "PSVR"],
    ),
    "xbox": ("Xbox", ["Xbox", "X360", "XB1", "XBXS"]),
    "sega": ("Sega", ["GEN", "SMS", "DC", "SAT", "GG", "SCD"]),
}


def get_landing_families() -> List[Dict[str, Any]]:
    """Manufacturer-family pages with their member platform IDs."""
    cache_key = _cache_key("families")
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = []
    for slug, (name, codes) in FAMILY_PAGES.items():
        ids = sorted(
            models.Platform.objects.filter(code__in=codes).values_list("id", flat=True)
        )
        if not ids:
            continue
        game_count = utils.apply_platform_filter(models.Game.objects.all(), ids).count()
        if game_count >= MIN_PLATFORM_GAMES:
            result.append(
                {"slug": slug, "name": name, "ids": ids, "game_count": game_count}
            )

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


def _cache_key(suffix: str) -> str:
    return f"{config.CACHE_VERSION}:landing_pages:{suffix}"


def get_landing_genres() -> List[Dict[str, Any]]:
    """Root genres that have games (directly or via descendants)."""
    cache_key = _cache_key("genres")
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = []
    roots = models.WikipediaGenre.objects.filter(level=0).order_by(
        "display_order", "name"
    )
    for genre in roots:
        game_count = utils.apply_genre_filter(
            models.Game.objects.all(), [genre.id], match_all=False
        ).count()
        if game_count > 0:
            result.append(
                {
                    "id": genre.id,
                    "name": genre.name,
                    "slug": genre.slug,
                    "game_count": game_count,
                }
            )

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


# Platforms whose names equal a family label ("PlayStation", "Xbox") would
# generate pages with titles identical to the family page's - the family
# page covers their search intent instead
EXCLUDED_PLATFORM_CODES = ["PS", "Xbox"]


def get_landing_platforms() -> List[Dict[str, Any]]:
    """Platforms with enough games to warrant a landing page."""
    cache_key = _cache_key("platforms")
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = list(
        models.Platform.objects.exclude(slug__isnull=True)
        .exclude(code__in=EXCLUDED_PLATFORM_CODES)
        .annotate(game_count=Count("games", distinct=True))
        .filter(game_count__gte=MIN_PLATFORM_GAMES)
        .order_by("name")
        .values("id", "name", "slug", "code", "game_count")
    )

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


def get_landing_years() -> List[int]:
    """Years with enough games to warrant a landing page."""
    cache_key = _cache_key("years")
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = sorted(
        models.Game.objects.exclude(year_of_release__isnull=True)
        .values("year_of_release")
        .annotate(game_count=Count("id"))
        .filter(game_count__gte=MIN_YEAR_GAMES)
        .values_list("year_of_release", flat=True)
    )

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


def get_landing_decades() -> List[int]:
    """Decades that have at least one game."""
    cache_key = _cache_key("decades")
    result = cache.get(cache_key)
    if result is not None:
        return result

    result = [
        decade
        for decade in DECADES
        if models.Game.objects.filter(
            year_of_release__gte=decade, year_of_release__lte=decade + 9
        ).exists()
    ]

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


def resolve_slug(slug: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Resolve a /games/<slug>/ slug to ("genre"|"platform"|"family", entry).

    Only root genres, qualifying platforms, and manufacturer families
    resolve; everything else (sub-genres, small platforms, unknown slugs)
    returns None so those URLs 404 instead of creating thin duplicate pages.
    """
    for entry in get_landing_families():
        if entry["slug"] == slug:
            return ("family", entry)
    for entry in get_landing_genres():
        if entry["slug"] == slug:
            return ("genre", entry)
    for entry in get_landing_platforms():
        if entry["slug"] == slug:
            return ("platform", entry)
    return None

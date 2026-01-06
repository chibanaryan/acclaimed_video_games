"""
Query filter utilities for Acclaimed Games.

Provides reusable filtering functions for Django querysets,
including genre, platform, and year filtering with caching support.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from django.db.models import Q, QuerySet

from games import config


def apply_genre_filter(
    queryset: QuerySet,
    genre_ids: List[int],
    match_all: bool = True,
    use_wikipedia: bool = True,  # Now defaults to Wikipedia genres
    expand_hierarchy: bool = True,
) -> QuerySet:
    """
    Filter queryset by Wikipedia genres with any/all matching.

    When using Wikipedia genres with hierarchy expansion, selecting a parent
    genre will automatically include all games tagged with child genres.

    Args:
        queryset: The queryset to filter
        genre_ids: List of genre IDs to filter by
        match_all: If True, games must match ALL selected genres (each can be
                   satisfied by itself or any descendant). If False, ANY match.
        use_wikipedia: Deprecated, always uses wikipedia_genres.
        expand_hierarchy: If True, expand parent genres to include all
                          descendants. If False, filter by exact genre IDs only.

    Returns:
        Filtered queryset
    """
    if not genre_ids:
        return queryset

    genre_field = "wikipedia_genres"

    # For Wikipedia genres with hierarchy expansion
    # Each selected genre expands to include its descendants
    # match_all: game must have at least one from EACH expanded group
    # match_any: game must have at least one from ANY expanded group
    if expand_hierarchy:
        expanded_groups = []
        for genre_id in genre_ids:
            # Get this genre plus all its descendants
            group = _expand_single_genre_with_descendants(genre_id)
            expanded_groups.append(group)

        if match_all:
            # Game must have at least one genre from EACH group
            for group in expanded_groups:
                q = Q()
                for gid in group:
                    q |= Q(**{genre_field: gid})
                queryset = queryset.filter(q)
        else:
            # Game must have at least one genre from ANY group
            q = Q()
            for group in expanded_groups:
                for gid in group:
                    q |= Q(**{genre_field: gid})
            queryset = queryset.filter(q)
    else:
        # No hierarchy expansion - exact matching
        if match_all:
            for genre_id in genre_ids:
                queryset = queryset.filter(**{genre_field: genre_id})
        else:
            q = Q()
            for genre_id in genre_ids:
                q |= Q(**{genre_field: genre_id})
            queryset = queryset.filter(q)

    # Use distinct() to avoid duplicate rows from M2M joins
    return queryset.distinct()


def _expand_single_genre_with_descendants(genre_id: int) -> List[int]:
    """
    Expand a single genre ID to include itself and all descendant IDs.

    Results are cached for 24 hours to avoid repeated recursive queries.

    Args:
        genre_id: A single genre ID to expand

    Returns:
        List containing the genre ID and all its descendant IDs
    """
    from django.core.cache import cache

    from games.models import WikipediaGenre

    cache_key = f"{config.CACHE_VERSION}:genre_descendants:{genre_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        genre = WikipediaGenre.objects.get(id=genre_id)
        # Get this genre plus all descendants
        result = genre.get_descendant_ids(include_self=True)
    except WikipediaGenre.DoesNotExist:
        result = [genre_id]

    cache.set(cache_key, result, config.CACHE_TIMEOUT_24_HOURS)
    return result


def _expand_genre_ids_with_descendants(genre_ids: List[int]) -> List[int]:
    """
    Expand a list of genre IDs to include all descendant IDs.

    This enables hierarchical filtering: selecting a parent genre
    automatically includes games tagged with any child genre.

    Args:
        genre_ids: List of genre IDs to expand

    Returns:
        List of genre IDs including all descendants
    """
    from games.models import WikipediaGenre

    expanded_ids = set(genre_ids)

    for genre_id in genre_ids:
        try:
            genre = WikipediaGenre.objects.get(id=genre_id)
            # Add all descendant IDs
            descendant_ids = genre.get_descendant_ids(include_self=False)
            expanded_ids.update(descendant_ids)
        except WikipediaGenre.DoesNotExist:
            continue

    return list(expanded_ids)


def apply_wikipedia_genre_filter(
    queryset: QuerySet,
    genre_ids: List[int],
    match_all: bool = True,
    expand_hierarchy: bool = True,
) -> QuerySet:
    """
    Filter queryset by Wikipedia genres with hierarchical support.

    This is a convenience wrapper around apply_genre_filter for Wikipedia genres.

    Args:
        queryset: The queryset to filter
        genre_ids: List of Wikipedia genre IDs to filter by
        match_all: If True, games must have ALL genres. If False, ANY genre matches.
        expand_hierarchy: If True, expand parent genres to include all descendants.

    Returns:
        Filtered queryset
    """
    return apply_genre_filter(
        queryset,
        genre_ids,
        match_all=match_all,
        use_wikipedia=True,
        expand_hierarchy=expand_hierarchy,
    )


def apply_platform_filter(queryset: QuerySet, platform_ids: List[int]) -> QuerySet:
    """
    Filter queryset by platforms (any match).

    Args:
        queryset: The queryset to filter
        platform_ids: List of platform IDs to filter by

    Returns:
        Filtered queryset
    """
    if not platform_ids:
        return queryset

    return queryset.filter(platforms__in=platform_ids).distinct()


def apply_series_filter(queryset: QuerySet, series_ids: List[int]) -> QuerySet:
    """
    Filter queryset by series (any match).

    Args:
        queryset: The queryset to filter
        series_ids: List of series IDs to filter by

    Returns:
        Filtered queryset with distinct() to avoid duplicates from M2M join
    """
    if not series_ids:
        return queryset

    return queryset.filter(series__in=series_ids).distinct()


def get_or_set_cache(
    cache_key: str,
    queryset: QuerySet,
    fields: List[str],
    timeout: int = config.CACHE_TIMEOUT_DEFAULT,
    order_by: Optional[str] = None,
    transform_id: bool = False,
) -> List[Dict[str, Any]]:
    """
    Get cached list or build and cache from queryset.

    Args:
        cache_key: Key to use for caching
        queryset: Queryset to build list from if not cached
        fields: List of field names to include in each dict
        timeout: Cache timeout in seconds (default from config)
        order_by: Optional field to order by
        transform_id: If True, convert 'id' field to string

    Returns:
        List of dictionaries with requested fields
    """
    from django.core.cache import cache

    result = cache.get(cache_key)
    if result is None:
        qs = queryset
        if order_by:
            qs = qs.order_by(order_by)
        result = list(qs.values(*fields))
        if transform_id and "id" in fields:
            result = [{**item, "id": str(item["id"])} for item in result]
        cache.set(cache_key, result, timeout)
    return result


def apply_year_filters(
    queryset: QuerySet,
    decade: Optional[str] = None,
    year: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> QuerySet:
    """
    Apply year/decade filtering to a Game queryset.

    Args:
        queryset: The queryset to filter
        decade: Decade string like "1990-99" or "2000-09"
        year: Single year as string (ignored if decade is set)
        start: Start year range as string
        end: End year range as string

    Returns:
        Filtered queryset
    """
    import re

    # Parse decade filter (format: "1990-99" -> start=1990, end=1999)
    if decade:
        decade_pattern = re.compile(r"(\d{2})(\d{2})-(\d{2})")
        match = decade_pattern.match(decade)
        if match:
            start_str = match.group(1) + match.group(2)
            end_str = match.group(1) + match.group(3)
            start_year = int(start_str)
            end_year = int(end_str)
            queryset = queryset.filter(
                year_of_release__gte=start_year, year_of_release__lte=end_year
            )

    # Year filter (single year) - only if decade not set
    if year and not decade:
        try:
            queryset = queryset.filter(year_of_release=int(year))
        except (ValueError, TypeError):
            pass

    # Start/end year range filters
    if start:
        try:
            queryset = queryset.filter(year_of_release__gte=int(start))
        except (ValueError, TypeError):
            pass
    if end:
        try:
            queryset = queryset.filter(year_of_release__lte=int(end))
        except (ValueError, TypeError):
            pass

    return queryset


def safe_int_filter(
    queryset: QuerySet, value: Optional[str], field_name: str
) -> QuerySet:
    """
    Apply integer filter, ignoring invalid values.

    Args:
        queryset: The queryset to filter
        value: String value to convert to int
        field_name: Field name to filter on

    Returns:
        Filtered queryset (unchanged if value is invalid)
    """
    if not value:
        return queryset
    try:
        queryset = queryset.filter(**{field_name: int(value)})
    except (ValueError, TypeError):
        pass
    return queryset


@dataclass
class Filter:
    """Generic filter class for API views."""

    param: str
    fields: List[str]
    coerce: type = str
    label: Callable[[str], str] = lambda x: x

    def filter_queryset(self, qs: QuerySet, param_val: Optional[str]) -> QuerySet:
        """
        Filter a queryset based on parameter value.

        Args:
            qs: The Django queryset to filter
            param_val: The parameter value to filter by

        Returns:
            The filtered queryset
        """
        if not param_val:
            return qs

        param_val = self.coerce(param_val.strip())
        if self.fields:
            query = Q()
            for field in self.fields:
                query |= Q(**{field: param_val})

        qs = qs.filter(query)

        return qs

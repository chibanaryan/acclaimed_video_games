"""
Game filtering service for Acclaimed Games.

Provides a unified interface for filtering games across views and API endpoints.
Consolidates duplicate filter logic from views.py and api/views.py.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from django.db.models import QuerySet
from django.http import HttpRequest

from games.services.query_filters import (
    apply_genre_filter,
    apply_platform_filter,
    apply_year_filters,
)


@dataclass
class GameFilters:
    """
    Container for all game filter parameters.

    Attributes:
        q: Search query for game name
        genres: List of genre IDs to filter by (single-select)
        platforms: List of platform IDs to filter by
        start: Minimum year of release
        end: Maximum year of release
        decade: Decade string (e.g., "1990-99")
        year: Single year filter
        company_igdb_id: Filter by company's IGDB ID
    """

    q: Optional[str] = None
    genres: List[int] = field(default_factory=list)
    platforms: List[int] = field(default_factory=list)
    start: Optional[int] = None
    end: Optional[int] = None
    decade: Optional[str] = None
    year: Optional[str] = None
    company_igdb_id: Optional[int] = None

    @classmethod
    def from_request(cls, request: HttpRequest) -> "GameFilters":
        """
        Parse filter parameters from an HTTP request.

        Args:
            request: Django HttpRequest object with GET parameters

        Returns:
            GameFilters instance populated from request parameters
        """
        filters = cls()

        # Search query
        q = request.GET.get("q")
        if q:
            filters.q = q.strip()

        # Genre filtering
        genres_param = request.GET.get("genres")
        if genres_param:
            try:
                filters.genres = [int(x) for x in genres_param.split(",") if x]
            except (ValueError, TypeError):
                filters.genres = []

        # Platform filtering
        platforms_param = request.GET.get("platforms")
        if platforms_param:
            try:
                filters.platforms = [int(x) for x in platforms_param.split(",") if x]
            except (ValueError, TypeError):
                filters.platforms = []

        # Year/decade filtering
        filters.decade = request.GET.get("decade")
        filters.year = request.GET.get("year")

        start = request.GET.get("start")
        if start:
            try:
                filters.start = int(start)
            except (ValueError, TypeError):
                pass

        end = request.GET.get("end")
        if end:
            try:
                filters.end = int(end)
            except (ValueError, TypeError):
                pass

        # Company filtering (API uses igdb_id)
        # Support both "company" and legacy "developer" parameter
        company = request.GET.get("company") or request.GET.get("developer")
        if company:
            try:
                filters.company_igdb_id = int(company)
            except (ValueError, TypeError):
                pass

        return filters

    @property
    def is_filtered(self) -> bool:
        """Returns True if any filter is active."""
        return bool(
            self.q
            or self.genres
            or self.platforms
            or self.decade
            or self.year
            or self.start
            or self.end
            or self.company_igdb_id
        )


def apply_game_filters(qs: QuerySet, filters: GameFilters) -> QuerySet:
    """
    Apply all game filters to a queryset.

    Args:
        qs: Base Game queryset
        filters: GameFilters instance with filter parameters

    Returns:
        Filtered queryset
    """
    # Search by name
    if filters.q:
        qs = qs.filter(name__icontains=filters.q)

    # Year/decade filtering
    qs = apply_year_filters(
        qs,
        decade=filters.decade,
        year=filters.year,
        start=str(filters.start) if filters.start else None,
        end=str(filters.end) if filters.end else None,
    )

    # Genre filtering (single-select, so match_all doesn't matter)
    if filters.genres:
        qs = apply_genre_filter(qs, filters.genres, match_all=False)

    # Platform filtering
    if filters.platforms:
        qs = apply_platform_filter(qs, filters.platforms)

    # Company filtering
    if filters.company_igdb_id:
        qs = qs.filter(studios__company__igdb_id=filters.company_igdb_id)

    return qs.distinct()


def get_filter_context_from_request(
    request: HttpRequest,
    min_year: int = 1970,
    max_year: Optional[int] = None,
) -> dict:
    """
    Build a filter context dictionary from request parameters.

    Useful for passing filter state to templates.

    Args:
        request: Django HttpRequest object
        min_year: Minimum year to default to
        max_year: Maximum year to default to (current year if None)

    Returns:
        Dictionary with filter values suitable for template context
    """
    from datetime import datetime

    if max_year is None:
        max_year = datetime.today().year

    filters = GameFilters.from_request(request)

    return {
        "q": filters.q or "",
        "start": filters.start if filters.start else min_year,
        "end": filters.end if filters.end else max_year,
        "genres": [str(g) for g in filters.genres],  # String IDs for HTML select
        "platforms": [str(p) for p in filters.platforms],  # String IDs for HTML select
        "decade": filters.decade,
        "year": filters.year,
    }

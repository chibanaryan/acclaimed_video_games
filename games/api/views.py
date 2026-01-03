from datetime import datetime

from django.contrib.flatpages.models import FlatPage
from django.db import connection
from django.db.models import Count, F, Min, Prefetch
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView, Response

from .. import config, models, utils
from . import serializers


@method_decorator(cache_page(60 * 15), name="dispatch")  # 15 min cache
class GameListView(ListAPIView):

    serializer_class = serializers.GameSummarySerializer
    # Build search fields based on database vendor
    # PostgreSQL supports full-text search, SQLite does not
    search_fields = ["name_normalized__icontains", "name__icontains"]
    if connection.vendor == "postgresql":
        search_fields = [
            "name_normalized__search",
            "name__search",
        ] + search_fields
    filters = [
        utils.Filter(
            param="q",
            fields=search_fields,
        ),
        utils.Filter(param="developer", fields=["developers__igdb_id"], coerce=int),
        utils.Filter(param="start", fields=["year_of_release__gte"], coerce=int),
        utils.Filter(param="end", fields=["year_of_release__lte"], coerce=int),
    ]

    def get_queryset(self):
        qs = models.Game.objects.with_relations()

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        # Genre filtering (single-select, so match_all doesn't matter)
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            qs = utils.apply_genre_filter(qs, genre_ids, match_all=False)

        # Platform filtering
        platforms = self.request.GET.get("platforms")
        if platforms:
            platform_ids = [int(x) for x in platforms.split(",")]
            qs = utils.apply_platform_filter(qs, platform_ids)

        order_by = self.request.GET.get("order_by")
        if order_by:
            qs = qs.order_by(order_by)

        return qs.distinct()


@method_decorator(cache_page(60 * 30), name="dispatch")  # 30 min cache
class GameDetailView(RetrieveAPIView):
    lookup_field = "slug"
    serializer_class = serializers.GameDetailSerializer
    queryset = models.Game.objects.select_related(
        "primary_igdb_game_data",
        "primary_wikipedia_game_data",
    ).prefetch_related(
        Prefetch(
            "lists",
            queryset=models.ListMembership.objects.select_related(
                "list__publisher",
            ),
        )
    )


@method_decorator(cache_page(60 * 30), name="dispatch")  # 30 min cache
class DeveloperDetailAPIView(RetrieveAPIView):
    """API endpoint for developer details."""

    lookup_field = "slug"
    serializer_class = serializers.DeveloperSerializer
    queryset = models.Developer.objects.select_related("parent").prefetch_related(
        "subsidiaries"
    )


# Legacy alias for backward compatibility
CompanyDetailView = DeveloperDetailAPIView


class DeveloperListAPIView(ListAPIView):
    """API endpoint for listing developers."""

    serializer_class = serializers.DeveloperSerializer
    search_fields = ["name__icontains"]
    if connection.vendor == "postgresql":
        search_fields = ["name__search"] + search_fields
    filters = [
        utils.Filter(
            param="q",
            fields=search_fields,
        )
    ]

    def get_queryset(self):
        qs = (
            models.Developer.objects.annotate(
                games_count=Count("developed_games"),
            )
            .filter(games_count__gt=0)  # Only show developers with games
            .select_related("parent")
            .prefetch_related("subsidiaries")
            .order_by(Lower("name"))
            .distinct()
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


# Legacy alias for backward compatibility
StudioListView = DeveloperListAPIView


class DeveloperDetailByIdView(RetrieveAPIView):
    """API endpoint for developer details by IGDB ID."""

    lookup_field = "igdb_id"
    serializer_class = serializers.DeveloperSerializer
    queryset = (
        models.Developer.objects.annotate(
            games_count=Count("developed_games"),
        )
        .select_related("parent")
        .prefetch_related("subsidiaries")
    )


# Legacy alias for backward compatibility
StudioDetailView = DeveloperDetailByIdView


class ListListView(ListAPIView):

    serializer_class = serializers.ListSerializer

    filters = [
        utils.Filter(param="publisher", fields=["publisher_id"], coerce=int),
        utils.Filter(param="year", fields=["year"], coerce=int),
        utils.Filter(param="type", fields=["type"], coerce=str),
    ]

    def get_queryset(self):
        qs = models.List.objects.select_related(
            "publisher",
        ).order_by(
            "publisher",
            "year",
            "name",
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


class PublicationListView(ListAPIView):
    serializer_class = serializers.PublicationSerializer
    queryset = models.Publication.objects.all()


class PublicationDetailView(RetrieveAPIView):
    serializer_class = serializers.PublicationSerializer
    queryset = models.Publication.objects.all()


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class MetaView(APIView):

    def get(self, *args, **kwargs):
        data = {}

        # Lists
        list_year_counts = (
            models.List.objects.order_by(
                "year",
            )
            .values(
                "year",
            )
            .annotate(count=Count("id"))
            .values(
                "year",
                "count",
            )
        )

        data["lists"] = {
            "years": list_year_counts,
            "total_count": models.List.objects.count(),
        }

        # Games
        game_stats = models.Game.objects.aggregate(
            min_year=Min("year_of_release"),
        )
        min_year = game_stats["min_year"] or 1970
        max_year = datetime.today().year
        all_years = range(min_year, max_year)
        year_count_map = {
            entry["year_of_release"]: entry["count"]
            for entry in models.Game.objects.values("year_of_release")
            .annotate(count=Count("id"))
            .order_by("year_of_release")
        }

        all_years_with_counts = [
            {"year": x, "count": year_count_map.get(x, 0)} for x in all_years
        ]

        # Calculate counts for each decade using database aggregation
        from django.db.models.functions import Floor

        decades_data = (
            models.Game.objects.annotate(
                decade_start=Floor(F("year_of_release") / 10) * 10
            )
            .values("decade_start")
            .annotate(count=Count("id"))
            .order_by("decade_start")
        )

        decades_with_counts = [
            {
                "decade": (
                    f"{item['decade_start']}-{str(item['decade_start'] + 9)[2:4]}"
                ),
                "count": item["count"],
            }
            for item in decades_data
        ]

        # Get last_full_update from SiteMetadata
        metadata = models.SiteMetadata.get_instance()
        last_update = metadata.last_full_update

        data["games"] = {
            "years": all_years_with_counts,
            "decades": decades_with_counts,
            "last_update": last_update,
        }

        # Publications
        data["publications"] = {
            "total_count": models.Publication.objects.count(),
        }

        return Response(data)


class SnippetDetailView(APIView):
    def get(self, *args, **kwargs):
        snippet = get_object_or_404(models.Snippet, **kwargs)
        return Response({"snippet": snippet.text})


class PageDetailView(RetrieveAPIView):

    serializer_class = serializers.PageSerializer

    def get_object(self):
        url = self.kwargs.get("url")
        page = get_object_or_404(FlatPage, url=f"/{url}/")
        return page


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class GenreListView(ListAPIView):
    """List IGDB genres (backward compatible endpoint)"""

    serializer_class = serializers.GenreSerializer
    queryset = models.IGDBGenre.objects.all()


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class WikipediaGenreListView(ListAPIView):
    """
    List all Wikipedia genres (flat list with hierarchy metadata).

    Returns genres ordered by level and display_order for consistent rendering.
    Includes parent_id for client-side tree building if needed.
    """

    serializer_class = serializers.WikipediaGenreSerializer
    queryset = models.WikipediaGenre.objects.all().order_by(
        "level", "display_order", "name"
    )


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class WikipediaGenreTreeView(ListAPIView):
    """
    List Wikipedia genres as hierarchical tree structure.

    Returns only root categories (level=0), with children nested recursively.
    Includes game counts for each genre.

    Response format:
    [
        {
            "id": 1,
            "name": "Action",
            "slug": "action",
            "level": 0,
            "game_count": 1234,
            "children": [
                {"id": 2, "name": "Shooter", "level": 1,
                 "game_count": 456, "children": []},
                ...
            ]
        },
        ...
    ]
    """

    serializer_class = serializers.WikipediaGenreTreeSerializer

    def get_queryset(self):
        """Return only root categories (parent=None) for tree building."""
        return models.WikipediaGenre.objects.filter(parent=None).order_by(
            "display_order", "name"
        )


@method_decorator(cache_page(config.CACHE_TIMEOUT_24_HOURS), name="dispatch")
class PlatformListView(ListAPIView):
    serializer_class = serializers.PlatformSerializer
    queryset = models.Platform.objects.all()


class GameSearchAPIView(APIView):
    """
    API endpoint for navbar search - returns JSON list of games matching query.
    Used by GameSearchComponent in navbar.
    """

    def get(self, request):
        from django.http import JsonResponse

        q = request.GET.get("q", "").strip()
        limit = int(request.GET.get("limit", 5))

        if len(q) < 2:
            return JsonResponse({"results": [], "count": 0})

        # Search games by name (only fetch required fields for performance)
        games = (
            models.Game.objects.filter(name__icontains=q)
            .select_related("primary_igdb_game_data")
            .only(
                "id",
                "name",
                "slug",
                "year_of_release",
                "rank",
                "primary_igdb_game_data__artwork_id",
            )
            .order_by("rank")[:limit]
        )

        results = []
        for game in games:
            results.append(
                {
                    "id": game.id,
                    "name": game.name,
                    "slug": game.slug,
                    "year_of_release": game.year_of_release,
                    "rank": game.rank,
                    "thumbnail": game.thumbnail,
                }
            )

        return JsonResponse({"results": results, "count": len(results)})


class UnifiedSearchView(APIView):
    """
    Unified search endpoint for navbar - returns both developers and games.
    Used by unified search component in navbar for grouped dropdown results.
    """

    def get(self, request):
        from django.http import JsonResponse

        q = request.GET.get("q", "").strip()
        game_limit = int(request.GET.get("game_limit", 5))
        developer_limit = int(request.GET.get("developer_limit", 3))
        series_limit = int(request.GET.get("series_limit", 3))

        if len(q) < 2:
            return JsonResponse({"developers": [], "games": [], "series": []})

        # Search developers - find developers with games
        developers = (
            models.Developer.objects.filter(
                name__icontains=q,
            )
            .select_related("parent")
            .annotate(games_count=Count("developed_games"))
            .filter(games_count__gt=0)
            .order_by("-games_count")[:developer_limit]
        )

        developer_results = []
        for dev in developers:
            # Use root developer's slug and id for URL routing
            root = dev.root_developer
            root_slug = root.slug if root else dev.slug
            root_id = root.id if root else dev.id
            developer_results.append(
                {
                    "id": dev.id,
                    "name": dev.name,
                    "root_slug": root_slug,
                    "root_id": root_id,
                    "games_count": dev.games_count,
                }
            )

        # Search games by name (only fetch required fields for performance)
        games = (
            models.Game.objects.filter(name__icontains=q)
            .select_related("primary_igdb_game_data")
            .only(
                "id",
                "name",
                "slug",
                "year_of_release",
                "rank",
                "primary_igdb_game_data__artwork_id",
            )
            .order_by("rank")[:game_limit]
        )

        game_results = []
        for game in games:
            game_results.append(
                {
                    "id": game.id,
                    "name": game.name,
                    "slug": game.slug,
                    "year_of_release": game.year_of_release,
                    "rank": game.rank,
                    "thumbnail": game.thumbnail,
                }
            )

        # Search series by name (only show series with 2+ games, like the filter)
        series = (
            models.Series.objects.filter(name__icontains=q)
            .annotate(games_count=Count("games"))
            .filter(games_count__gte=2)
            .order_by("-games_count")[:series_limit]
        )

        series_results = [
            {"id": s.id, "name": s.name, "slug": s.slug, "games_count": s.games_count}
            for s in series
        ]

        return JsonResponse(
            {
                "developers": developer_results,
                "games": game_results,
                "series": series_results,
            }
        )


def _compute_game_data_version():
    """
    Compute a version hash for cache invalidation.

    Uses schema version, max modified timestamp of games, genre count, and series count.
    Returns a short hash string that changes when data is updated.
    """
    import hashlib

    # Schema version - increment when API response format changes
    # v2: Changed st->dv, studios/companies->developers (commit ac84d07c)
    # v3: Added 'i' (IGDB ID) field for played game filtering
    # v4: Added 'lc' (list_count) field for displaying list appearances
    # v5: Added 'ys' (year_start) and 'ye' (year_end) to platforms for sorting
    # v6: Force cache refresh after list_count data update
    SCHEMA_VERSION = "6"

    # Get latest game modification time
    latest_game = models.Game.objects.order_by("-modified").first()
    game_modified = latest_game.modified.isoformat() if latest_game else ""

    # Get genre count (changes if genres are added/modified)
    genre_count = models.WikipediaGenre.objects.count()

    # Get series count (changes if series are added/removed)
    series_count = models.Series.objects.count()

    # Count games with series assignments
    games_with_series = models.Game.objects.filter(series__isnull=False).count()

    # Combine into version string and hash it
    version_string = (
        f"{SCHEMA_VERSION}:{game_modified}:{genre_count}"
        f":{series_count}:{games_with_series}"
    )
    return hashlib.md5(version_string.encode()).hexdigest()[:12]


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class GameDataVersionView(APIView):
    """
    Lightweight endpoint returning only the data version hash.

    Used by client-side cache to validate if cached data is still current.
    Response: {"version": "abc123def456"}
    """

    def get(self, request):
        return Response({"version": _compute_game_data_version()})


@method_decorator(cache_page(config.CACHE_TIMEOUT_1_HOUR), name="dispatch")
class GameAllDataView(APIView):
    """
    Complete game data endpoint for client-side filtering.

    Returns all games with minimal payload for efficient client-side filtering:
    - Compressed field names to minimize payload size
    - Reference data (developers, platforms, genres) keyed by ID
    - Genre hierarchy with descendant IDs for hierarchical filtering

    Response format:
    {
        "version": "abc123def456",
        "data": {
            "games": [{id, n, s, r, y, a, dv, p, g, sr, lc}, ...],
            "developers": {id: {n, pa, s}, ...},
            "platforms": {id: {n, c, ys, ye}, ...},
            "genres": [{id, n, s, p, l, d}, ...]
        }
    }
    """

    def get(self, request):
        version = _compute_game_data_version()

        # Fetch all games with required relations
        games = (
            models.Game.objects.select_related("primary_igdb_game_data")
            .prefetch_related(
                "developers__parent",
                "platforms",
                "wikipedia_genres",
                "series",
            )
            .with_list_count()
            .order_by("rank")
        )

        # Build games list with minimal field names
        games_data = []
        developers_dict = {}
        platforms_dict = {}
        series_dict = {}

        for game in games:
            # Collect developer IDs and build developer reference data
            dev_ids = []
            for dev in game.developers.all():
                dev_ids.append(dev.id)
                if dev.id not in developers_dict:
                    # Get root developer slug for URL routing
                    root = dev.root_developer
                    developers_dict[dev.id] = {
                        "n": dev.name,
                        "pa": dev.parent_id,
                        "s": root.slug if root else dev.slug,
                    }
                    # Also add parent chain to dict
                    if dev.parent and dev.parent.id not in developers_dict:
                        parent = dev.parent
                        parent_root = parent.root_developer
                        developers_dict[parent.id] = {
                            "n": parent.name,
                            "pa": parent.parent_id,
                            "s": parent_root.slug if parent_root else parent.slug,
                        }

            # Collect platform IDs
            platform_ids = []
            for platform in game.platforms.all():
                platform_ids.append(platform.id)
                if platform.id not in platforms_dict:
                    platforms_dict[platform.id] = {
                        "n": platform.name,
                        "c": platform.code,
                        "ys": platform.year_start,
                        "ye": platform.year_end,
                    }

            # Collect genre IDs
            genre_ids = [g.id for g in game.wikipedia_genres.all()]

            # Collect series IDs and build series reference data
            series_ids = []
            for s in game.series.all():
                series_ids.append(s.id)
                if s.id not in series_dict:
                    series_dict[s.id] = {
                        "n": s.name,
                        "s": s.slug,
                    }

            # Get artwork ID from primary IGDB data
            artwork_id = None
            if game.primary_igdb_game_data:
                artwork_id = game.primary_igdb_game_data.artwork_id

            games_data.append(
                {
                    "id": game.id,
                    "i": game.igdb_id,  # IGDB ID for played game tracking
                    "n": game.name,
                    "s": game.slug,
                    "r": game.rank,
                    "y": game.year_of_release,
                    "a": artwork_id,
                    "dv": dev_ids,  # Changed from "st" to "dv" for developers
                    "p": platform_ids,
                    "g": genre_ids,
                    "sr": series_ids,
                    "lc": game.list_count,  # List count for display
                }
            )

        # Build genre hierarchy with descendant IDs for client-side expansion
        genres_data = []
        all_genres = models.WikipediaGenre.objects.prefetch_related("children").all()

        # Pre-compute descendant IDs for each genre
        for genre in all_genres:
            descendant_ids = genre.get_descendant_ids(include_self=False)
            genres_data.append(
                {
                    "id": genre.id,
                    "n": genre.name,
                    "s": genre.slug,
                    "p": genre.parent_id,
                    "l": genre.level,
                    "d": descendant_ids,
                }
            )

        return Response(
            {
                "version": version,
                "data": {
                    "games": games_data,
                    "developers": developers_dict,
                    "platforms": platforms_dict,
                    "genres": genres_data,
                    "series": series_dict,
                },
            }
        )

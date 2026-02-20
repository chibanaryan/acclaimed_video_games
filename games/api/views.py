from collections import defaultdict
from datetime import datetime

from django.contrib.flatpages.models import FlatPage
from django.db import connection
from django.db.models import Count, F, Min, Prefetch, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView, Response

from unidecode import unidecode

from .. import config, models, utils
from . import serializers


def _normalize_search_text(value):
    """Normalize text for accent-insensitive comparisons."""
    return unidecode((value or "")).lower().strip()


def _matches_normalized(name, raw_query_lower, normalized_query):
    """Check if a name matches either raw or normalized query."""
    name_value = name or ""
    return (
        raw_query_lower in name_value.lower()
        or normalized_query in _normalize_search_text(name_value)
    )


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
        q_normalized = _normalize_search_text(q)
        limit = int(request.GET.get("limit", 5))

        if len(q) < 2:
            return JsonResponse({"results": [], "count": 0})

        # Search games by name (only fetch required fields for performance)
        # Search both original name and normalized (accent-stripped) version.
        # Use normalized query so accented and ASCII input both match.
        games = (
            models.Game.objects.filter(
                Q(name__icontains=q) | Q(name_normalized__icontains=q_normalized)
            )
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
        q_lower = q.lower()
        q_normalized = _normalize_search_text(q)

        if len(q) < 2:
            return JsonResponse({"developers": [], "games": [], "series": []})

        # Search developers - find developers with games.
        # Developer model does not have name_normalized, so normalize in Python.
        developers = (
            models.Developer.objects.select_related("parent")
            .annotate(games_count=Count("developed_games"))
            .filter(games_count__gt=0)
            .order_by("-games_count")
        )

        developer_results = []
        for dev in developers:
            if not _matches_normalized(dev.name, q_lower, q_normalized):
                continue
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
            if len(developer_results) >= developer_limit:
                break

        # Search games by original and normalized names for accent-insensitive matching.
        # Use normalized query so accented and ASCII input both match.
        games = (
            models.Game.objects.filter(
                Q(name__icontains=q) | Q(name_normalized__icontains=q_normalized)
            )
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

        # Search series by name (only show series with 2+ games, like the filter).
        # Series model does not have name_normalized, so normalize in Python.
        series = (
            models.Series.objects.annotate(games_count=Count("games"))
            .filter(games_count__gte=2)
            .order_by("-games_count")
        )

        series_results = []
        for s in series:
            if not _matches_normalized(s.name, q_lower, q_normalized):
                continue
            series_results.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "slug": s.slug,
                    "games_count": s.games_count,
                }
            )
            if len(series_results) >= series_limit:
                break

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
    # v7: Added 'pt' (playtime) field for HLTB filtering
    # v8: Added 'ptc' (playtime_completionist) field for HLTB 100% filtering
    # v9: Updated HLTB bucket boundaries (short: 0-10h, medium: 10-30h, long: 30+h)
    # v10: Removed game_modes - no longer supported
    # v11: Populated platform year_start/year_end data for all 74 platforms
    SCHEMA_VERSION = "11"

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
            "genres": [{id, n, s, p, l, d}, ...],
            "series": {id: {n, s}, ...}
        }
    }
    """

    def get(self, request):
        version = _compute_game_data_version()

        # Fetch base game rows with scalar fields only (no model instantiation)
        game_rows = list(
            models.Game.objects.values(
                "id",
                "igdb_id",
                "name",
                "slug",
                "rank",
                "year_of_release",
                "primary_igdb_game_data__artwork_id",
                "primary_hltb_game_data__main_story_hours",
                "primary_hltb_game_data__completionist_hours",
            )
            .annotate(list_count=Count("lists", distinct=True))
            .order_by("rank")
        )
        game_ids = [row["id"] for row in game_rows]

        # Group related IDs via through tables (ordered for deterministic output)
        game_developer_ids = defaultdict(list)
        used_developer_ids = set()
        if game_ids:
            for game_id, developer_id in (
                models.Game.developers.through.objects.filter(game_id__in=game_ids)
                .order_by("game_id", "developer__name", "developer_id")
                .values_list("game_id", "developer_id")
            ):
                game_developer_ids[game_id].append(developer_id)
                used_developer_ids.add(developer_id)

        game_platform_ids = defaultdict(list)
        used_platform_ids = set()
        if game_ids:
            for game_id, platform_id in (
                models.Game.platforms.through.objects.filter(game_id__in=game_ids)
                .order_by("game_id", "platform__name", "platform_id")
                .values_list("game_id", "platform_id")
            ):
                game_platform_ids[game_id].append(platform_id)
                used_platform_ids.add(platform_id)

        game_genre_ids = defaultdict(list)
        if game_ids:
            genre_links = models.Game.wikipedia_genres.through.objects.filter(
                game_id__in=game_ids
            ).order_by(
                "game_id",
                "wikipediagenre__level",
                "wikipediagenre__display_order",
                "wikipediagenre__name",
                "wikipediagenre_id",
            )
            for game_id, genre_id in genre_links.values_list(
                "game_id", "wikipediagenre_id"
            ):
                game_genre_ids[game_id].append(genre_id)

        game_series_ids = defaultdict(list)
        used_series_ids = set()
        if game_ids:
            for game_id, series_id in (
                models.Game.series.through.objects.filter(game_id__in=game_ids)
                .order_by("game_id", "series__name", "series_id")
                .values_list("game_id", "series_id")
            ):
                game_series_ids[game_id].append(series_id)
                used_series_ids.add(series_id)

        # Developers: fetch only game-linked developers + their immediate parents.
        developer_rows = {}
        pending_ids = set(used_developer_ids)
        while pending_ids:
            fetched_rows = list(
                models.Developer.objects.filter(id__in=pending_ids).values(
                    "id", "name", "parent_id", "slug"
                )
            )
            for row in fetched_rows:
                developer_rows[row["id"]] = row
            pending_ids = {
                row["parent_id"]
                for row in fetched_rows
                if row["parent_id"] and row["parent_id"] not in developer_rows
            }

        direct_parent_ids = {
            developer_rows[dev_id]["parent_id"]
            for dev_id in used_developer_ids
            if dev_id in developer_rows and developer_rows[dev_id]["parent_id"]
        }
        response_developer_ids = used_developer_ids | direct_parent_ids

        def _resolve_root_slug(dev_id):
            current_id = dev_id
            visited = set()
            while current_id and current_id not in visited:
                visited.add(current_id)
                current = developer_rows.get(current_id)
                if not current:
                    break
                if not current["parent_id"]:
                    return current["slug"]
                current_id = current["parent_id"]
            current = developer_rows.get(dev_id)
            return current["slug"] if current else None

        developers_dict = {}
        for dev_id in sorted(
            response_developer_ids,
            key=lambda pk: developer_rows.get(pk, {}).get("name", ""),
        ):
            row = developer_rows.get(dev_id)
            if not row:
                continue
            developers_dict[dev_id] = {
                "n": row["name"],
                "pa": row["parent_id"],
                "s": _resolve_root_slug(dev_id),
            }

        platform_rows = models.Platform.objects.filter(id__in=used_platform_ids).values(
            "id", "name", "code", "year_start", "year_end"
        )
        platforms_dict = {
            row["id"]: {
                "n": row["name"],
                "c": row["code"],
                "ys": row["year_start"],
                "ye": row["year_end"],
            }
            for row in platform_rows
        }

        series_rows = models.Series.objects.filter(id__in=used_series_ids).values(
            "id", "name", "slug"
        )
        series_dict = {
            row["id"]: {
                "n": row["name"],
                "s": row["slug"],
            }
            for row in series_rows
        }

        # Build all genres and descendants from one in-memory hierarchy map.
        genre_rows = list(
            models.WikipediaGenre.objects.values(
                "id", "name", "slug", "parent_id", "level", "display_order"
            ).order_by("level", "display_order", "name")
        )
        children_by_parent_id = defaultdict(list)
        for row in genre_rows:
            if row["parent_id"] is not None:
                children_by_parent_id[row["parent_id"]].append(row["id"])

        descendant_ids_by_genre_id = {}

        def _get_descendant_ids(genre_id):
            if genre_id in descendant_ids_by_genre_id:
                return descendant_ids_by_genre_id[genre_id]

            stack = [(genre_id, False)]
            while stack:
                current_id, expanded = stack.pop()
                if current_id in descendant_ids_by_genre_id:
                    continue
                if expanded:
                    descendants = []
                    for child_id in children_by_parent_id.get(current_id, []):
                        descendants.append(child_id)
                        descendants.extend(descendant_ids_by_genre_id.get(child_id, []))
                    descendant_ids_by_genre_id[current_id] = descendants
                    continue

                stack.append((current_id, True))
                children = children_by_parent_id.get(current_id, [])
                for child_id in reversed(children):
                    if child_id not in descendant_ids_by_genre_id:
                        stack.append((child_id, False))

            return descendant_ids_by_genre_id.get(genre_id, [])

        genres_data = [
            {
                "id": row["id"],
                "n": row["name"],
                "s": row["slug"],
                "p": row["parent_id"],
                "l": row["level"],
                "d": _get_descendant_ids(row["id"]),
            }
            for row in genre_rows
        ]

        # Assemble games preserving existing compressed keys/semantics.
        games_data = []
        for row in game_rows:
            playtime = row["primary_hltb_game_data__main_story_hours"]
            completionist = row["primary_hltb_game_data__completionist_hours"]
            games_data.append(
                {
                    "id": row["id"],
                    "i": row["igdb_id"],  # IGDB ID for played game tracking
                    "n": row["name"],
                    "s": row["slug"],
                    "r": row["rank"],
                    "y": row["year_of_release"],
                    "a": row["primary_igdb_game_data__artwork_id"],
                    "dv": game_developer_ids.get(row["id"], []),
                    "p": game_platform_ids.get(row["id"], []),
                    "g": game_genre_ids.get(row["id"], []),
                    "sr": game_series_ids.get(row["id"], []),
                    "lc": row["list_count"],  # List count for display
                    "pt": float(playtime) if playtime is not None else None,
                    "ptc": (
                        float(completionist) if completionist is not None else None
                    ),
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


class SavedFilterSetListCreateView(APIView):
    """
    List saved filter sets for current user (GET).
    Create new saved filter set (POST).

    Enforces maximum of 10 saved filters per user.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all saved filter sets for current user."""
        filter_sets = models.SavedFilterSet.objects.filter(user=request.user).order_by(
            "-modified"
        )[:10]

        data = [
            {
                "id": fs.id,
                "name": fs.name,
                "filters": fs.filters,
                "modified": fs.modified.isoformat(),
            }
            for fs in filter_sets
        ]
        return Response({"filter_sets": data, "count": len(data)})

    def post(self, request):
        """Create a new saved filter set."""
        current_count = models.SavedFilterSet.objects.filter(user=request.user).count()

        if current_count >= 10:
            return Response(
                {
                    "error": "Maximum of 10 saved filters allowed. "
                    "Delete one to save a new filter."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = request.data.get("name", "").strip()
        filters = request.data.get("filters", {})

        if not name:
            return Response(
                {"error": "Filter name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(name) > 255:
            return Response(
                {"error": "Filter name must be 255 characters or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate name
        if models.SavedFilterSet.objects.filter(user=request.user, name=name).exists():
            return Response(
                {"error": "A filter with this name already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filter_set = models.SavedFilterSet.objects.create(
            user=request.user,
            name=name,
            filters=filters,
        )

        return Response(
            {
                "id": filter_set.id,
                "name": filter_set.name,
                "filters": filter_set.filters,
                "modified": filter_set.modified.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class SavedFilterSetDetailView(APIView):
    """
    Update (PATCH) or delete (DELETE) a saved filter set.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        return get_object_or_404(models.SavedFilterSet, pk=pk, user=user)

    def patch(self, request, pk):
        """Rename saved filter set."""
        filter_set = self.get_object(pk, request.user)

        name = request.data.get("name", "").strip()
        if not name:
            return Response(
                {"error": "Name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(name) > 255:
            return Response(
                {"error": "Filter name must be 255 characters or less."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check for duplicate name (excluding current filter)
        if (
            models.SavedFilterSet.objects.filter(user=request.user, name=name)
            .exclude(pk=pk)
            .exists()
        ):
            return Response(
                {"error": "A filter with this name already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filter_set.name = name
        filter_set.save(update_fields=["name", "modified"])

        return Response(
            {
                "id": filter_set.id,
                "name": filter_set.name,
            }
        )

    def delete(self, request, pk):
        """Delete saved filter set."""
        filter_set = self.get_object(pk, request.user)
        filter_set.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

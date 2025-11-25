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

from .. import models, utils
from . import serializers


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
        utils.Filter(
            param="developer", fields=["developers__developer__igdb_id"], coerce=int
        ),
        utils.Filter(param="start", fields=["year_of_release__gte"], coerce=int),
        utils.Filter(param="end", fields=["year_of_release__lte"], coerce=int),
    ]

    def get_queryset(self):
        qs = models.Game.objects.with_relations()

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        # Genre filtering
        genre_option = self.request.GET.get("genre_option")
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            match_all = genre_option != "A"  # "A" = Any, otherwise All
            qs = utils.apply_genre_filter(qs, genre_ids, match_all=match_all)

        # Platform filtering
        platforms = self.request.GET.get("platforms")
        if platforms:
            platform_ids = [int(x) for x in platforms.split(",")]
            qs = utils.apply_platform_filter(qs, platform_ids)

        order_by = self.request.GET.get("order_by")
        if order_by:
            qs = qs.order_by(order_by)

        return qs.distinct()


class GameDetailView(RetrieveAPIView):
    lookup_field = "slug"
    serializer_class = serializers.GameDetailSerializer
    queryset = models.Game.objects.prefetch_related(
        Prefetch(
            "lists",
            queryset=models.ListMembership.objects.select_related(
                "list__publisher",
            ),
        )
    )


class DeveloperDetailView(RetrieveAPIView):
    lookup_field = "slug"
    serializer_class = serializers.DeveloperSerializer
    queryset = models.Developer.objects.prefetch_related("aliases")


class DeveloperAliasListView(ListAPIView):

    serializer_class = serializers.DeveloperAliasSerializer
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
            models.DeveloperAlias.objects.annotate(
                games_count=Count("games"),
            )
            .filter(games_count__gt=0)  # Only show aliases with games
            .order_by(Lower("name"))
            .distinct()  # Ensure correct count for pagination
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


class DeveloperAliasDetailView(RetrieveAPIView):
    lookup_field = "igdb_id"
    serializer_class = serializers.DeveloperAliasSerializer
    queryset = models.DeveloperAlias.objects.annotate(
        games_count=Count("games"),
    ).order_by(Lower("name"))


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


class PostListView(ListAPIView):
    serializer_class = serializers.PostSerializer
    queryset = models.Post.objects.all()


@method_decorator(cache_page(60 * 60), name="dispatch")
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
    serializer_class = serializers.PublicationSerializer

    def get(self, *args, **kwargs):
        snippet = get_object_or_404(models.Snippet, **kwargs)
        return Response({"snippet": snippet.text})


class PageDetailView(RetrieveAPIView):

    serializer_class = serializers.PageSerializer

    def get_object(self):
        url = self.kwargs.get("url")
        page = get_object_or_404(FlatPage, url=f"/{url}/")
        return page


@method_decorator(cache_page(60 * 60 * 24), name="dispatch")
class GenreListView(ListAPIView):
    serializer_class = serializers.GenreSerializer
    queryset = models.Genre.objects.all()


@method_decorator(cache_page(60 * 60 * 24), name="dispatch")
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
            .only("id", "name", "slug", "year_of_release", "rank", "igdb_artwork_id")
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

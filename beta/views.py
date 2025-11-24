from django.db.models import Count, Min, Max, Prefetch
from django.db.models.functions import Lower
from django.views.generic import ListView, DetailView, TemplateView
from django.views import View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from games import models
from games import views as games_views


class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch latest posts (limit 5, matching Vue version)
        context["posts"] = models.Post.objects.filter(active=True).order_by("-date")[:5]

        # Fetch top 10 games (matching Vue version)
        context["games"] = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        ).order_by("rank")[:10]

        # Fetch counts for dynamic tagline
        context["list_count"] = models.List.objects.count()
        context["publication_count"] = models.Publication.objects.count()

        # Fetch meta data for last update
        # Get last_full_update from SiteMetadata
        metadata = models.SiteMetadata.get_instance()
        context["last_update"] = metadata.last_full_update

        return context


class GameListView(ListView):
    model = models.Game
    template_name = "games/game_list.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        Instead of raising 404, return the last valid page.
        """
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                # This shouldn't happen often, but handle it gracefully
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_queryset(self):
        # Prefetch relationships for GameRowProperties component
        qs = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",  # Access the Developer through DeveloperAlias
            "platforms",
            "genres",
        )

        # Parse decade filter (format: "1990-99" -> start=1990, end=1999)
        decade = self.request.GET.get("decade")
        if decade:
            # Parse decade format like "1990-99" or "2000-09"
            import re

            decade_pattern = re.compile(r"(\d{2})(\d{2})-(\d{2})")
            match = decade_pattern.match(decade)
            if match:
                start_str = match.group(1) + match.group(2)
                end_str = match.group(1) + match.group(3)
                start_year = int(start_str)
                end_year = int(end_str)
                qs = qs.filter(
                    year_of_release__gte=start_year, year_of_release__lte=end_year
                )

        # Year filter (single year)
        year = self.request.GET.get("year")
        if year and not decade:  # Year takes precedence if both are set
            year_int = int(year)
            qs = qs.filter(year_of_release=year_int)

        # Support start/end parameters (used by game_rank_url)
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        if start:
            qs = qs.filter(year_of_release__gte=int(start))
        if end:
            qs = qs.filter(year_of_release__lte=int(end))

        return qs.order_by("rank")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add meta data for SimpleFilters component
        from datetime import datetime as dt

        # Get meta data (same logic as MetaView)
        data = {}

        # Games meta
        game_stats = models.Game.objects.aggregate(
            min_year=Min("year_of_release"),
            last_update=Max("modified"),
        )
        min_year = game_stats["min_year"] or 1970
        max_year = dt.today().year
        all_years = range(min_year, max_year + 1)
        year_count_map = {
            entry["year_of_release"]: entry["count"]
            for entry in models.Game.objects.values("year_of_release")
            .annotate(count=Count("id"))
            .order_by("year_of_release")
        }

        all_years_with_counts = [
            {"year": x, "count": year_count_map.get(x, 0)} for x in all_years
        ]
        decade_starts = sorted(list(set(int(x / 10) * 10 for x in all_years)))

        # Calculate counts for each decade
        decades_with_counts = []
        for decade_start in decade_starts:
            decade_end = decade_start + 9
            count = models.Game.objects.filter(
                year_of_release__gte=decade_start, year_of_release__lte=decade_end
            ).count()
            decade_str = f"{decade_start}-{str(decade_end)[2:4]}"
            decades_with_counts.append({"decade": decade_str, "count": count})

        data["games"] = {
            "years": all_years_with_counts,
            "decades": decades_with_counts,
            "last_update": game_stats["last_update"],
        }

        context["meta"] = data

        # Add filters from query params
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        context["filters"] = {
            "decade": self.request.GET.get("decade"),
            "year": self.request.GET.get("year"),
        }

        # Add highlight parameter for scrolling to specific game
        highlight = self.request.GET.get("highlight")
        context["highlight"] = int(highlight) if highlight else None

        # Determine if filtered (for show_rank logic)
        is_filtered = bool(
            context["filters"]["decade"] or context["filters"]["year"] or start or end
        )
        context["is_filtered"] = is_filtered

        return context

    def get_template_names(self):
        # Support HTMX partial responses - return just the content block if HTMX request
        if self.request.headers.get("HX-Request"):
            return ["games/includes/_game_list_content.html"]
        return super().get_template_names()


class GameDetailView(DetailView):
    model = models.Game
    template_name = "games/game_detail.html"
    context_object_name = "game"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch lists with publisher for ListResultsComponent
        return models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
            Prefetch(
                "lists",
                queryset=models.ListMembership.objects.select_related(
                    "list__publisher",
                ).order_by("list__publisher__name", "list__year"),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        game = context["game"]

        # Group lists by type (matching Vue GameDetail logic)
        from collections import defaultdict

        LIST_TYPE_LABELS = {
            "A": "All time",
            "D": "Decade",
            "M": "Miscellaneous",
            "E": "End of year",
        }

        grouped = defaultdict(list)
        for membership in game.lists.all():
            list_type = membership.list.type
            label = LIST_TYPE_LABELS.get(list_type, list_type)
            grouped[label].append(
                {
                    "id": membership.list.id,
                    "name": membership.list.name,
                    "publication": (
                        membership.list.publisher.name
                        if membership.list.publisher
                        else ""
                    ),
                    "type": list_type,
                    "type_name": label,
                    "url": membership.list.url,
                    "year": membership.list.year,
                    "rank": membership.rank,
                }
            )

        # Sort by predefined order (matching Vue)
        sorting_arr = ["All time", "Decade", "Miscellaneous", "End of year"]
        grouped_lists = sorted(
            grouped.items(),
            key=lambda x: sorting_arr.index(x[0]) if x[0] in sorting_arr else 999,
        )

        context["grouped_lists"] = grouped_lists
        return context


@method_decorator(never_cache, name="dispatch")
class GameSearchView(ListView):
    model = models.Game
    template_name = "games/game_search.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        Instead of raising 404, return the last valid page.
        """
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_template_names(self):
        # Support HTMX partial responses
        # Check both HX-Request header (for real HTMX) and
        # X-Requested-With header (for fetch)
        is_htmx = (
            self.request.headers.get("HX-Request")
            or self.request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or self.request.GET.get("partial") == "true"
        )
        if is_htmx:
            # Targeted update for just the results container
            if self.request.headers.get("HX-Target") == "game-results-container":
                return ["games/includes/_game_search_results.html"]
            # Full content partial for pagination and initial loads
            return ["games/includes/_game_search_content.html"]
        return super().get_template_names()

    def get_queryset(self):
        from django.db.models import Q

        # Prefetch relationships for GameRowProperties component
        qs = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        )

        # Basic search by name
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Year range filtering
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        if start:
            qs = qs.filter(year_of_release__gte=int(start))
        if end:
            qs = qs.filter(year_of_release__lte=int(end))

        # Genre filtering
        genre_option = self.request.GET.get("genre_option", "L")
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            if genre_option == "A":  # Any
                q = Q()
                for genre_id in genre_ids:
                    q |= Q(genres=genre_id)
                qs = qs.filter(q)
            else:  # All
                for genre_id in genre_ids:
                    qs = qs.filter(genres=genre_id)

        # Platform filtering
        platforms = self.request.GET.get("platforms")
        if platforms:
            platform_ids = [int(x) for x in platforms.split(",")]
            qs = qs.filter(platforms__in=platform_ids)

        return qs.distinct().order_by("rank")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import datetime

        # Get genres and platforms for AdvancedFilters
        # Convert IDs to strings for proper Alpine.js binding
        genres = [
            {"id": str(g["id"]), "name": g["name"]}
            for g in models.Genre.objects.all().order_by("name").values("id", "name")
        ]
        platforms = [
            {"id": str(p["id"]), "name": p["name"], "code": p["code"]}
            for p in models.Platform.objects.all()
            .order_by("name")
            .values("id", "name", "code")
        ]

        # Get min/max years
        year_stats = models.Game.objects.aggregate(
            min_year=Min("year_of_release"),
            max_year=Max("year_of_release"),
        )
        min_year = year_stats["min_year"] or 1970
        max_year = year_stats["max_year"] or datetime.today().year

        # Build filters dict from query params
        filters = {
            "q": self.request.GET.get("q", ""),
            "start": int(self.request.GET.get("start", min_year)),
            "end": int(self.request.GET.get("end", max_year)),
            "genres": [],
            "platforms": [],
            "genre_option": self.request.GET.get("genre_option", "L"),
            "rank_display": self.request.GET.get("rank_display", "alltime"),
        }

        # Parse selected genres - send string IDs for HTML select compatibility
        genres_param = self.request.GET.get("genres")
        if genres_param:
            filters["genres"] = genres_param.split(",")

        # Parse selected platforms - send string IDs for HTML select compatibility
        platforms_param = self.request.GET.get("platforms")
        if platforms_param:
            filters["platforms"] = platforms_param.split(",")

        context["genres"] = genres
        context["platforms"] = platforms
        context["filters"] = filters
        context["min_year"] = min_year
        context["max_year"] = max_year
        context["highlight"] = self.request.GET.get("highlight")
        context["is_filtered"] = True  # GameSearch is always filtered

        return context


class DeveloperListView(ListView):
    model = models.DeveloperAlias
    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 100
    paginate_orphans = 0

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        Instead of raising 404, return the last valid page.
        """
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_queryset(self):
        from django.db.models import Count

        qs = (
            models.DeveloperAlias.objects.annotate(
                games_count=Count("games"),
            )
            .filter(games_count__gt=0)  # Only show aliases with games
            .select_related("developer")
            .order_by(Lower("name"))
            .distinct()
        )

        # Search filter
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        return qs

    def get_template_names(self):
        # Support HTMX partial responses - return just the content block if HTMX request
        if self.request.headers.get("HX-Request"):
            return ["developers/includes/_developer_list_content.html"]
        return super().get_template_names()


class DeveloperDetailView(DetailView):
    model = models.Developer
    template_name = "developers/developer_detail.html"
    context_object_name = "developer"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch aliases and games
        return models.Developer.objects.prefetch_related(
            "aliases",
            "aliases__games",
            "aliases__games__developers",
            "aliases__games__developers__developer",
            "aliases__games__platforms",
            "aliases__games__genres",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        developer = context["developer"]

        # Get all games from all aliases
        games = (
            models.Game.objects.filter(developers__developer=developer)
            .prefetch_related(
                "developers",
                "developers__developer",
                "platforms",
                "genres",
            )
            .distinct()
            .order_by("year_of_release")
        )

        # Create aliases data for Alpine.js (all selected by default)
        # Note: API uses igdb_id for alias IDs, matching Vue component
        aliases_data = []
        for alias in developer.aliases.all():
            # Use igdb_id to match API serializer
            alias_id = alias.igdb_id if alias.igdb_id else alias.id
            aliases_data.append(
                {
                    "id": alias_id,
                    "name": alias.name,
                    "selected": True,  # All aliases start selected
                }
            )

        # Serialize games for Alpine.js filtering (matching Vue structure)
        # Each game's developers array contains developer alias objects
        games_data = []
        for game in games:
            game_developers = []
            for da in game.developers.all():
                # Use igdb_id to match API serializer
                dev_id = da.igdb_id if da.igdb_id else da.id
                game_developers.append(
                    {
                        "id": dev_id,
                        "name": da.name,
                    }
                )
            games_data.append(
                {
                    "id": game.igdb_id if game.igdb_id else game.id,
                    "name": game.name,
                    "slug": game.slug,
                    "year_of_release": game.year_of_release,
                    "rank": game.rank,
                    "thumbnail": game.thumbnail,
                    "developers": game_developers,
                }
            )

        context["games"] = games
        context["games_data"] = games_data
        context["aliases_data"] = aliases_data
        return context


class DeveloperAliasRedirectView(View):
    """
    Redirects legacy /developer-alias/:id/ URLs to the developer detail page.
    Matches the Vue.js DeveloperAliasRedirect.vue component behavior.
    """

    def get(self, request, id):
        alias = get_object_or_404(models.DeveloperAlias, id=id)
        return redirect(
            "beta:developer-detail", slug=alias.developer.slug, permanent=True
        )


class ListListView(ListView):
    model = models.List
    template_name = "lists/list_list.html"
    context_object_name = "lists"
    paginate_by = 100
    paginate_orphans = 0

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        Instead of raising 404, return the last valid page.
        """
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

    def get_queryset(self):
        qs = models.List.objects.select_related("publisher").order_by(
            "publisher__name",
            "year",
            "name",
        )

        # Apply filters
        publisher = self.request.GET.get("publisher")
        if publisher:
            try:
                qs = qs.filter(publisher_id=int(publisher))
            except (ValueError, TypeError):
                pass  # Invalid publisher ID, skip filter

        year = self.request.GET.get("year")
        if year:
            try:
                qs = qs.filter(year=int(year))
            except (ValueError, TypeError):
                pass  # Invalid year, skip filter

        list_type = self.request.GET.get("type")
        if list_type:
            qs = qs.filter(type=list_type)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add meta data for filters
        from django.db.models import Count

        # Get list years with counts
        list_year_counts = (
            models.List.objects.order_by("year")
            .values("year")
            .annotate(count=Count("id"))
            .order_by("year")
        )

        # Get publishers
        from games.models import Publication

        publishers = Publication.objects.all().order_by("name")

        # Get list types
        LIST_TYPE_LABELS = {
            "A": "All time",
            "D": "Decade",
            "M": "Miscellaneous",
            "E": "End of year",
        }
        list_types = [(k, v) for k, v in LIST_TYPE_LABELS.items()]

        context["meta"] = {
            "lists": {
                "years": list(list_year_counts),
            }
        }
        context["publishers"] = publishers
        context["list_types"] = list_types
        context["filters"] = {
            "publisher": self.request.GET.get("publisher"),
            "year": self.request.GET.get("year"),
            "type": self.request.GET.get("type"),
        }

        return context

    def get_template_names(self):
        # Support HTMX partial responses - return just the content block if HTMX request
        if self.request.headers.get("HX-Request"):
            return ["lists/includes/_list_list_content.html"]
        return super().get_template_names()


class PostListView(ListView):
    model = models.Post
    template_name = "posts/post_list.html"
    context_object_name = "posts"
    paginate_by = 5
    paginate_orphans = 0

    def get_queryset(self):
        qs = models.Post.objects.filter(active=True).order_by("-date")

        # Check for offset parameter (from "older posts" link on home page)
        offset = self.request.GET.get("offset")
        if offset:
            try:
                offset = int(offset)
                # Apply offset and limit to 100
                qs = qs[offset : offset + 100]
                # Return as list to bypass pagination
                return list(qs)
            except (TypeError, ValueError):
                pass

        return qs

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        If queryset is already a list (from offset), skip pagination.
        """
        # If queryset is a list (from offset parameter),
        # return it directly without pagination
        if isinstance(queryset, list):
            from django.core.paginator import Paginator

            # Create a dummy paginator for compatibility, but return the list as-is
            paginator = Paginator(queryset, len(queryset))
            return (paginator, None, queryset, False)

        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())


class PageDetailView(TemplateView):
    template_name = "pages/page_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.contrib.flatpages.models import FlatPage
        from django.shortcuts import get_object_or_404
        import markdown

        slug = kwargs.get("slug")
        # Try /page/{slug}/ first (for consistency with URL pattern), then /{slug}/
        try:
            flatpage = FlatPage.objects.get(url=f"/page/{slug}/")
        except FlatPage.DoesNotExist:
            # Fall back to /{slug}/ format (matches existing database entries)
            flatpage = get_object_or_404(FlatPage, url=f"/{slug}/")

        # Convert markdown to HTML (matching API serializer behavior)
        if flatpage.content:
            flatpage.rendered_content = markdown.markdown(flatpage.content)
        else:
            flatpage.rendered_content = ""

        context["flatpage"] = flatpage
        return context


class NotFoundView(TemplateView):
    """
    Custom 404 page for beta site.
    Matches the Vue.js NotFound.vue component behavior with auto-redirect.
    """

    template_name = "404.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.status_code = 404
        return response


class ImportView(games_views.ImportView):
    """
    Beta site import view - inherits all functionality from games.views.ImportView
    but uses the beta template.
    """

    template_name = "import.html"
    success_url = reverse_lazy("beta:import")


class IGDBProgressView(games_views.IGDBProgressView):
    """
    Beta site IGDB progress view - inherits SSE functionality from
    games.views.IGDBProgressView.
    No template override needed as this returns streaming HTTP response.
    """

    pass

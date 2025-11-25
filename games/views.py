import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.flatpages.models import FlatPage
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Min, Max, Prefetch, Q
from django.db.models.functions import Lower
from django.forms import Form
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.vary import vary_on_headers
from django.views.generic import ListView, DetailView, TemplateView, FormView

from games import constants, models, utils
from games.forms import ImportForm, ContactForm
from games.mixins import HTMXPartialMixin, RobustPaginationMixin


class HomePageView(FormView):
    """Home page with top games, latest news, and contact form."""

    template_name = "home.html"
    form_class = ContactForm
    success_url = reverse_lazy("contact_thank_you")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch latest posts (limit 5)
        context["posts"] = models.Post.objects.filter(active=True).order_by("-date")[:5]

        # Fetch top 10 games
        context["games"] = models.Game.objects.with_relations().order_by("rank")[:10]

        # Fetch counts for dynamic tagline
        context["list_count"] = models.List.objects.count()
        context["publication_count"] = models.Publication.objects.count()

        # Fetch meta data for last update
        # Get last_full_update from SiteMetadata
        metadata = models.SiteMetadata.get_instance()
        context["last_update"] = metadata.last_full_update

        return context

    def form_valid(self, form):
        """Process valid contact form submission and send email."""
        name = form.cleaned_data["name"]
        email = form.cleaned_data["email"]
        category = form.cleaned_data["category"]
        message = form.cleaned_data["message"]

        # Send the email
        email_sent = utils.send_contact_email(name, email, category, message)

        if not email_sent:
            # If email fails, add an error message and re-render the form
            form.add_error(
                None,
                "We're sorry, but there was an error sending your message. "
                "Please try again later or email us directly at "
                "contact@acclaimedvideogames.com",
            )
            return self.form_invalid(form)

        return super().form_valid(form)


class ContactThankYouView(TemplateView):
    """Display thank you page after successful contact form submission."""

    template_name = "contact_thank_you.html"


class GameListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    model = models.Game
    template_name = "games/game_list.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0
    htmx_partial_template = "games/includes/_game_list_content.html"

    def get_queryset(self):
        qs = models.Game.objects.with_relations()

        # Apply year/decade filters using utility function
        qs = utils.apply_year_filters(
            qs,
            decade=self.request.GET.get("decade"),
            year=self.request.GET.get("year"),
            start=self.request.GET.get("start"),
            end=self.request.GET.get("end"),
        )

        return qs.order_by("rank")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add meta data for SimpleFilters component

        # Get meta data (cached for 1 hour to improve performance)
        data = cache.get("game_list_meta")
        if data is None:
            data = {}

            # Games meta
            game_stats = models.Game.objects.aggregate(
                min_year=Min("year_of_release"),
            )
            min_year = game_stats["min_year"] or 1970
            max_year = datetime.today().year
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

            # Calculate counts for each decade from year_count_map (no DB queries)
            decades_with_counts = []
            for decade_start in decade_starts:
                decade_end = decade_start + 9
                # Sum counts from year_count_map instead of querying database
                count = sum(
                    year_count_map.get(year, 0)
                    for year in range(decade_start, decade_end + 1)
                )
                decade_str = f"{decade_start}-{str(decade_end)[2:4]}"
                decades_with_counts.append({"decade": decade_str, "count": count})

            # Get last_full_update from SiteMetadata
            metadata = models.SiteMetadata.get_instance()

            data["games"] = {
                "years": all_years_with_counts,
                "decades": decades_with_counts,
                "last_update": metadata.last_full_update,
            }

            cache.set("game_list_meta", data, 60 * 60)  # Cache for 1 hour

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


def download_games_csv(request):
    """Download games list as CSV, respecting current filters."""
    # Get filtered queryset using same logic as GameListView
    qs = models.Game.objects.with_relations()

    decade = request.GET.get("decade")
    year = request.GET.get("year")
    start = request.GET.get("start")
    end = request.GET.get("end")

    qs = utils.apply_year_filters(qs, decade=decade, year=year, start=start, end=end)
    qs = qs.order_by("rank")

    # Determine if filtered (use filtered rank instead of alltime rank)
    is_filtered = bool(decade or year or start or end)

    # Build filename based on filters
    filename = "acclaimed_games"
    if decade:
        filename += f"_{decade}"
    elif year:
        filename += f"_{year}"
    filename += ".csv"

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Rank", "Name", "Year", "Developers", "Platforms", "Genres"])

    for index, game in enumerate(qs, start=1):
        developers = ", ".join(d.name for d in game.developers.all())
        platforms = ", ".join(p.name for p in game.platforms.all())
        genres = ", ".join(g.name for g in game.genres.all())
        rank = index if is_filtered else game.rank
        writer.writerow(
            [rank, game.name, game.year_of_release, developers, platforms, genres]
        )

    return response


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

        # Get lists grouped by type using model property
        context["grouped_lists"] = list(game.lists_grouped_by_type.items())
        return context


@method_decorator(vary_on_headers("X-Requested-With", "HX-Request"), name="dispatch")
class GameSearchView(RobustPaginationMixin, ListView):
    model = models.Game
    template_name = "games/game_search.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0

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
        qs = models.Game.objects.with_relations()

        # Basic search by name
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Year range filtering using utility function
        qs = utils.apply_year_filters(
            qs,
            start=self.request.GET.get("start"),
            end=self.request.GET.get("end"),
        )

        # Genre filtering
        genre_option = self.request.GET.get("genre_option", "L")
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

        return qs.distinct().order_by("rank")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get genres and platforms for AdvancedFilters (cached for 24 hours)
        # Convert IDs to strings for proper Alpine.js binding
        genres = utils.get_or_set_cache(
            "search_genres_list",
            models.Genre.objects.all(),
            ["id", "name"],
            order_by="name",
            transform_id=True,
        )

        platforms = utils.get_or_set_cache(
            "search_platforms_list",
            models.Platform.objects.all(),
            ["id", "name", "code"],
            order_by="name",
            transform_id=True,
        )

        # Get min/max years (cached for 24 hours)
        year_stats = cache.get("game_year_stats")
        if year_stats is None:
            year_stats = models.Game.objects.aggregate(
                min_year=Min("year_of_release"),
                max_year=Max("year_of_release"),
            )
            cache.set("game_year_stats", year_stats, 60 * 60 * 24)  # 24 hours
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


class DeveloperListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    model = models.DeveloperAlias
    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 100
    paginate_orphans = 0
    htmx_partial_template = "developers/includes/_developer_list_content.html"

    def get_queryset(self):
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


class DeveloperDetailView(DetailView):
    model = models.Developer
    template_name = "developers/developer_detail.html"
    context_object_name = "developer"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch aliases and games with optimized queryset
        games_queryset = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        ).order_by("year_of_release")

        return models.Developer.objects.prefetch_related(
            "aliases",
            Prefetch("aliases__games", queryset=games_queryset),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        developer = context["developer"]

        # Use prefetched games from aliases instead of making a new query
        # Collect unique games from all aliases (already prefetched in get_queryset)
        seen_ids = set()
        games = []
        for alias in developer.aliases.all():
            for game in alias.games.all():
                if game.id not in seen_ids:
                    seen_ids.add(game.id)
                    games.append(game)
        # Sort by year_of_release to match original behavior
        games.sort(key=lambda g: (g.year_of_release or 0))

        # Create aliases data for Alpine.js (all selected by default)
        # Note: API uses igdb_id for alias IDs
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

        # Serialize games for Alpine.js filtering
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
    """

    def get(self, request, id):
        alias = get_object_or_404(models.DeveloperAlias, id=id)
        return redirect("developer-detail", slug=alias.developer.slug, permanent=True)


class ListListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    model = models.List
    template_name = "lists/list_list.html"
    context_object_name = "lists"
    paginate_by = 100
    paginate_orphans = 0
    htmx_partial_template = "lists/includes/_list_list_content.html"

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

        # Get list years with counts
        list_year_counts = (
            models.List.objects.order_by("year")
            .values("year")
            .annotate(count=Count("id"))
            .order_by("year")
        )

        # Get publishers with list counts
        publishers = models.Publication.objects.annotate(
            list_count=Count("lists")
        ).order_by("name")

        # Get list types from constants
        list_types = constants.LIST_TYPES

        # Get type counts
        type_counts = (
            models.List.objects.values("type")
            .annotate(count=Count("id"))
            .order_by("type")
        )

        context["meta"] = {
            "lists": {
                "years": list(list_year_counts),
            }
        }
        context["publishers"] = publishers
        context["list_types"] = list_types
        context["type_counts"] = list(type_counts)
        context["filters"] = {
            "publisher": self.request.GET.get("publisher"),
            "year": self.request.GET.get("year"),
            "type": self.request.GET.get("type"),
        }

        return context


class PostListView(RobustPaginationMixin, ListView):
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
        """Handle offset list case, delegate standard pagination to mixin."""
        # If queryset is a list (from offset parameter), skip pagination
        if isinstance(queryset, list):
            paginator = Paginator(queryset, len(queryset) or 1)
            return (paginator, None, queryset, False)

        return super().paginate_queryset(queryset, page_size)


class PageDetailView(TemplateView):
    template_name = "pages/page_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
    Custom 404 page with auto-redirect.
    """

    template_name = "404.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.status_code = 404
        return response


def custom_404_view(request, exception):
    """
    Function-based wrapper for NotFoundView (required for handler404).
    """
    return NotFoundView.as_view()(request, exception=exception)


class ImportView(LoginRequiredMixin, FormView):
    """
    Handles batch importing of game data files with validation and transaction safety.

    Supports:
    - Batch upload of multiple TSV files (platforms, lists, games, memberships)
    - Single-file uploads (legacy support)
    - Delete existing data
    - IGDB data fetching

    Files are imported in dependency order:
    1. Platforms (no dependencies)
    2. Source Lists (Publications auto-created)
    3. Games (requires Platforms)
    4. Game Positions (requires Lists and Games)
    """

    template_name = "import.html"
    form_class = ImportForm
    success_url = reverse_lazy("import")

    def get_context_data(self, **kwargs) -> dict:
        """Add database object counts and persistent errors to context."""
        context = super().get_context_data(**kwargs)

        # Get all counts in a single aggregation query (optimized)
        game_counts = models.Game.objects.aggregate(
            total=Count("id"),
            with_igdb=Count("id", filter=Q(igdb_artwork_id__isnull=False)),
            without_igdb=Count("id", filter=Q(igdb_artwork_id__isnull=True)),
        )
        total_games = game_counts["total"]
        games_with_igdb = game_counts["with_igdb"]
        games_without_igdb = game_counts["without_igdb"]

        context["counts"] = {
            "platforms": models.Platform.objects.count(),
            "publications": models.Publication.objects.count(),
            "lists": models.List.objects.count(),
            "games": total_games,
            "memberships": models.ListMembership.objects.count(),
            "developers": models.Developer.objects.count(),
            "genres": models.Genre.objects.count(),
        }
        context["igdb_counts"] = {
            "total": total_games,
            "with_igdb": games_with_igdb,
            "without_igdb": games_without_igdb,
            "percentage": int(
                (games_with_igdb / total_games * 100) if total_games > 0 else 0
            ),
        }

        # Get persistent errors from session
        import_errors = self.request.session.pop("import_errors", None)
        import_success_message = self.request.session.pop("import_success", None)
        trigger_igdb = self.request.session.pop("trigger_igdb", False)
        context["import_errors"] = import_errors
        context["import_success_message"] = import_success_message
        context["trigger_igdb"] = trigger_igdb

        return context

    def form_valid(self, form: Form) -> HttpResponse:
        """Process the import form and handle file uploads."""
        import_data = form.cleaned_data

        # Quick action: load bundled test data files from the repo
        if import_data.get("seed_test_data"):
            seed_dir = Path(settings.BASE_DIR) / "acclaimedgames" / "test_input_files"
            file_map = {
                "platforms_file": "PlatformDB.txt",
                "lists_file": "SourceLists.txt",
                "games_file": "Top1000.txt",
                "memberships_file": "GamePositions.txt",
            }

            opened_files = {}
            try:
                for field, filename in file_map.items():
                    path = seed_dir / filename
                    opened_files[field] = open(path, "rb")

                seed_payload = {**import_data, **opened_files}
                res, message, trigger_igdb = utils.import_batch(seed_payload)
            except FileNotFoundError:
                res, message, trigger_igdb = (
                    False,
                    (
                        "Bundled test data files not found in "
                        "acclaimedgames/test_input_files."
                    ),
                    False,
                )
            finally:
                for fh in opened_files.values():
                    fh.close()

            if res:
                self.request.session["import_success"] = (
                    "Loaded bundled test data.\n" + message
                )
                if trigger_igdb:
                    self.request.session["trigger_igdb"] = True
            else:
                self.request.session["import_errors"] = [message]

            self.request.session.modified = True
            return super().form_valid(form)

        # Check if this is a batch file import (not delete/igdb operations)
        has_batch_files = any(
            [
                import_data.get("platforms_file"),
                import_data.get("lists_file"),
                import_data.get("games_file"),
                import_data.get("memberships_file"),
            ]
        )

        # If batch files are provided, process them directly
        if has_batch_files and not import_data.get("delete"):
            # Process batch import immediately (handles IGDB flag internally)
            res, message, trigger_igdb = utils.import_batch(import_data)
            if res:
                # Store success message in session (persist across redirect)
                self.request.session["import_success"] = message
                # Store IGDB trigger flag if import succeeded and checkbox was checked
                if trigger_igdb:
                    self.request.session["trigger_igdb"] = True
            else:
                # Store error message in session as a list for persistent display
                self.request.session["import_errors"] = [message]
            # Explicitly save session before redirect
            self.request.session.modified = True
            return super().form_valid(form)

        # For delete/igdb operations, use the standard import flow
        res, message = utils.import_data(import_data)
        if res:
            # Store success message in session (persist across redirect)
            self.request.session["import_success"] = message
        else:
            # Store error message in session as a list for persistent display
            self.request.session["import_errors"] = [message]

        # Explicitly save session before redirect
        self.request.session.modified = True
        return super().form_valid(form)


class IGDBProgressView(LoginRequiredMixin, View):
    """
    Streams IGDB data fetching progress via Server-Sent Events (SSE).
    Allows real-time progress bar updates in the browser.
    """

    def get(self, request, *args, **kwargs):
        """Stream IGDB fetch progress as SSE events."""
        return StreamingHttpResponse(
            utils.import_igdb_with_progress(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

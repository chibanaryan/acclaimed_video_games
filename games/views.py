import csv
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.flatpages.models import FlatPage
from django.core.cache import cache
from django.db.models import Count, Min, Max, Prefetch, Q
from django.db.models.functions import Lower
from django.forms import Form
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views import View
from django.views.decorators.vary import vary_on_headers
from django.views.generic import ListView, DetailView, TemplateView, FormView

from games import config, constants, models, utils
from games.forms import ImportForm, ContactForm
from games.mixins import HTMXPartialMixin, RobustPaginationMixin


def _get_year_bounds():
    """Return cached global min/max release years."""
    year_stats = cache.get("game_year_stats")
    if year_stats is None:
        year_stats = models.Game.objects.aggregate(
            min_year=Min("year_of_release"),
            max_year=Max("year_of_release"),
        )
        cache.set("game_year_stats", year_stats, config.CACHE_TIMEOUT_24_HOURS)
    min_year = year_stats["min_year"] or 1970
    max_year = year_stats["max_year"] or datetime.today().year
    return min_year, max_year


def _join_names(names):
    """Join a list of names with commas and an 'and' before the last item."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _build_time_window(start_year, end_year, min_year, max_year):
    """Return a human-readable time window label for headings and filenames."""
    if start_year is None or end_year is None:
        return ""
    if start_year <= min_year and end_year >= max_year:
        return "All Time"
    if start_year == end_year:
        return str(start_year)
    if start_year % 10 == 0 and end_year == start_year + 9:
        return f"the {start_year}'s"
    return f"{start_year}-{end_year}"


def _build_platform_segment(selected_platform_ids, platforms, include_games=True):
    """Return platform segment text like 'Nintendo Switch Games'."""
    all_groups = {
        # Accordion categories (check these first)
        "Retro Consoles": [
            "A26",
            "A52",
            "A78",
            "INTV",
            "CV",
            "TG16",
            "3DO",
            "NG",
            "JAG",
            "LYNX",
            "NGP",
            "WS",
        ],
        "Microcomputers": [
            "C64",
            "AMI",
            "CD32",
            "MSX",
            "CPC",
            "ZXS",
            "AST",
            "BBCM",
            "PC88",
            "PC98",
            "FMT",
            "FM7",
            "SX1",
            "T80",
            "TCC",
            "VC20",
            "A8",
            "A2",
        ],
        # Big Five groups
        "Nintendo": [
            "NES",
            "SNES",
            "N64",
            "GC",
            "Wii",
            "WiiU",
            "DS",
            "3DS",
            "SW",
            "GB",
            "GBA",
            "GBC",
            "FDS",
        ],
        "PlayStation": ["PS", "PS2", "PS3", "PS4", "PS5", "PSP", "PSV", "PSVR"],
        "Xbox": ["Xbox", "X360", "XB1", "XBXS"],
        "Sega": ["GEN", "SMS", "DC", "SAT", "GG", "SCD"],
        "PC": ["WIN", "DOS", "LIN", "MAC"],
        "Arcade, Mobile & VR": ["ARC", "AND", "iOS", "LMD", "VR", "BR"],
    }

    name_lookup = {str(p["id"]): p["name"] for p in platforms}
    code_lookup = {str(p["id"]): p.get("code") for p in platforms}

    selected_ids = {str(pid) for pid in selected_platform_ids}
    labels = []
    consumed_ids = set()

    # Add group labels when entire group is selected
    for group_name, codes in all_groups.items():
        group_ids = [pid for pid, code in code_lookup.items() if code in codes]
        if group_ids and all(gid in selected_ids for gid in group_ids):
            labels.append(group_name)
            consumed_ids.update(group_ids)

    # Add remaining platform names
    for pid in selected_ids - consumed_ids:
        labels.append(name_lookup.get(pid, pid))

    if not labels:
        return "Video" + (" Games" if include_games else "")
    return f"{_join_names(labels)}" + (" Games" if include_games else "")


def _build_genre_subtitle(selected_genre_ids, option, genres):
    """Return subtitle string with AND/OR connector for genres."""
    if not selected_genre_ids:
        return ""
    name_lookup = {str(g["id"]): g["name"] for g in genres}
    genre_names = [name_lookup.get(str(gid), str(gid)) for gid in selected_genre_ids]
    if not genre_names:
        return ""
    connector = " AND " if option == "L" else " OR "
    return f"Genre: {connector.join(genre_names)}"


def _build_filter_title(filters, genres, platforms, min_year, max_year):
    """Compose the heading text based on filters."""
    start_year = filters.get("start")
    end_year = filters.get("end")
    time_window = _build_time_window(start_year, end_year, min_year, max_year)
    platform_label = _build_platform_segment(
        filters.get("platforms", []), platforms, include_games=False
    )
    # If exactly one genre is selected, fold it into the title after platform
    genre_label = ""
    selected_genres = filters.get("genres") or []
    if len(selected_genres) == 1:
        name_lookup = {str(g["id"]): g["name"] for g in genres}
        genre_name = name_lookup.get(str(selected_genres[0]), "").strip()
        if genre_name:
            genre_label = f" {genre_name}"
            # Omit "Video" prefix when genre selected ("Action Games")
            if platform_label == "Video":
                platform_label = ""

    time_suffix = f" of {time_window}" if time_window else ""
    return f"Most Acclaimed {platform_label}{genre_label} Games{time_suffix}"


class HomePageView(FormView):
    """Home page with top games, latest news, and contact form."""

    template_name = "home.html"
    form_class = ContactForm
    success_url = reverse_lazy("contact_thank_you")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch latest posts (limit 5)
        context["posts"] = models.Post.objects.filter(active=True).order_by("-date")[:5]

        # Fetch top 30 games for staggered animation display
        context["games"] = models.Game.objects.with_relations().order_by("rank")[:30]

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


def download_games_csv(request):
    """Download games list as CSV, respecting current filters."""
    # Get filtered queryset using same logic as GameSearchView / GameListView
    qs = models.Game.objects.with_relations()

    q = request.GET.get("q")
    decade = request.GET.get("decade")
    year = request.GET.get("year")
    start = request.GET.get("start")
    end = request.GET.get("end")
    genres_param = request.GET.get("genres")
    genre_option = request.GET.get("genre_option", "all")
    platforms_param = request.GET.get("platforms")

    if q:
        qs = qs.filter(name__icontains=q)

    qs = utils.apply_year_filters(qs, decade=decade, year=year, start=start, end=end)

    if genres_param:
        genre_ids = [int(x) for x in genres_param.split(",") if x]
        match_all = genre_option != "any"  # "any" = Any, otherwise All
        qs = utils.apply_genre_filter(qs, genre_ids, match_all=match_all)
    else:
        genre_ids = []

    if platforms_param:
        platform_ids = [int(x) for x in platforms_param.split(",") if x]
        qs = utils.apply_platform_filter(qs, platform_ids)
    else:
        platform_ids = []

    qs = qs.distinct().order_by("rank")

    use_filtered_rank = True

    # Build filename based on filters
    min_year, max_year = _get_year_bounds()
    genres_lookup = utils.get_or_set_cache(
        "search_genres_list_with_counts",
        models.Genre.objects.annotate(game_count=Count("game")),
        ["id", "name", "game_count"],
        order_by="name",
        transform_id=True,
    )
    platforms_lookup = utils.get_or_set_cache(
        "search_platforms_list",
        models.Platform.objects.all(),
        ["id", "name", "code"],
        order_by="name",
        transform_id=True,
    )

    def _safe_int(val, default):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def _decade_bounds(decade_str):
        import re

        pattern = re.compile(r"(\d{2})(\d{2})-(\d{2})")
        match = pattern.match(decade_str) if decade_str else None
        if not match:
            return None, None
        start_str = match.group(1) + match.group(2)
        end_str = match.group(1) + match.group(3)
        return _safe_int(start_str, None), _safe_int(end_str, None)

    start_for_title = _safe_int(start, None)
    end_for_title = _safe_int(end, None)
    if decade:
        d_start, d_end = _decade_bounds(decade)
        start_for_title = d_start
        end_for_title = d_end
    elif year:
        y_val = _safe_int(year, None)
        start_for_title = y_val
        end_for_title = y_val
    if start_for_title is None:
        start_for_title = min_year
    if end_for_title is None:
        end_for_title = max_year

    filters_for_title = {
        "q": q or "",
        "start": start_for_title,
        "end": end_for_title,
        "genres": [str(gid) for gid in genre_ids],
        "platforms": [str(pid) for pid in platform_ids],
        "genre_option": genre_option,
        "rank_display": "filtered",
    }
    filter_title = _build_filter_title(
        filters_for_title, genres_lookup, platforms_lookup, min_year, max_year
    )
    filename_base = filter_title
    if decade:
        filename_base = f"{filename_base} {decade}"
    elif year:
        filename_base = f"{filename_base} {year}"
    filename_base = slugify(filename_base) or "acclaimed-games"
    filename = f"{filename_base}.csv"

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "Filtered Rank",
            "Global Rank",
            "Name",
            "Year",
            "Developers",
            "Platforms",
            "Genres",
        ]
    )

    for index, game in enumerate(qs, start=1):
        developers = ", ".join(d.name for d in game.developers.all())
        platforms = ", ".join(p.name for p in game.platforms.all())
        genres = ", ".join(g.name for g in game.genres.all())
        filtered_rank = index if use_filtered_rank else game.rank
        writer.writerow(
            [
                filtered_rank,
                game.rank,
                game.name,
                game.year_of_release,
                developers,
                platforms,
                genres,
            ]
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
    template_name = "games/game_list.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0

    def get_paginate_by(self, queryset):
        """Dynamically adjust page size to include highlighted game."""
        highlight_str = self.request.GET.get("highlight")
        if highlight_str and highlight_str.isdigit():
            highlight_id = int(highlight_str)
            # Find position of highlighted game in queryset
            # We need to count how many games come before it
            try:
                # Get list of game IDs in order to find position
                game_ids = list(queryset.values_list("id", flat=True))
                if highlight_id in game_ids:
                    position = game_ids.index(highlight_id) + 1  # 1-based position
                    # Round up to nearest 100 to include the game
                    if position > self.paginate_by:
                        return ((position - 1) // 100 + 1) * 100
            except (ValueError, models.Game.DoesNotExist):
                pass
        return self.paginate_by

    def get_template_names(self):
        # Support HTMX partial responses
        # Check both HX-Request header (for real HTMX) and
        # X-Requested-With header (for fetch)
        is_htmx = (
            self.request.headers.get("HX-Request")
            or self.request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or self.request.GET.get("partial") == "true"
        )

        # Append mode for Load More - returns just game rows
        if self.request.GET.get("append") == "true":
            return ["games/includes/_game_list_append.html"]

        if is_htmx:
            # Targeted update for just the results container
            if self.request.headers.get("HX-Target") == "game-results-container":
                return ["games/includes/_game_list_results.html"]
            # Full content partial for pagination and initial loads
            return ["games/includes/_game_list_content.html"]
        return super().get_template_names()

    def get_queryset(self):
        qs = models.Game.objects.with_relations()

        # Basic search by name
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Year range filtering using utility function
        # Support legacy decade/year params from old GameListView
        qs = utils.apply_year_filters(
            qs,
            decade=self.request.GET.get("decade"),
            year=self.request.GET.get("year"),
            start=self.request.GET.get("start"),
            end=self.request.GET.get("end"),
        )

        # Genre filtering
        genre_option = self.request.GET.get("genre_option", "all")
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            match_all = genre_option != "any"  # "any" = Any, otherwise All
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
        # Includes game_count for heatmap visualization
        genres = utils.get_or_set_cache(
            "search_genres_list_with_counts",
            models.Genre.objects.annotate(game_count=Count("game")),
            ["id", "name", "game_count"],
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

        min_year, max_year = _get_year_bounds()

        # Parse year/decade params and convert to start/end
        # Priority: start/end > year > decade
        start_param = self.request.GET.get("start")
        end_param = self.request.GET.get("end")
        year_param = self.request.GET.get("year")
        decade_param = self.request.GET.get("decade")

        if start_param or end_param:
            start_val = int(start_param) if start_param else min_year
            end_val = int(end_param) if end_param else max_year
        elif year_param:
            start_val = int(year_param)
            end_val = int(year_param)
        elif decade_param:
            # Parse decade format like "1990-99"
            decade_start = int(decade_param.split("-")[0])
            start_val = decade_start
            end_val = decade_start + 9
        else:
            start_val = min_year
            end_val = max_year

        # Build filters dict from query params
        filters = {
            "q": self.request.GET.get("q", ""),
            "start": start_val,
            "end": end_val,
            "genres": [],
            "platforms": [],
            "genre_option": self.request.GET.get("genre_option", "all"),
            "rank_display": "filtered",
            # Keep legacy params for context
            "year": year_param,
            "decade": decade_param,
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
        # Check if year filtering is active (via start/end, year, or decade)
        has_year_filter = start_param or end_param or year_param or decade_param
        context["download_query"] = urlencode(
            {
                **({"q": filters["q"]} if filters["q"] else {}),
                **({"start": filters["start"]} if has_year_filter else {}),
                **({"end": filters["end"]} if has_year_filter else {}),
                **(
                    {"genres": ",".join(filters["genres"])} if filters["genres"] else {}
                ),
                **(
                    {"platforms": ",".join(filters["platforms"])}
                    if filters["platforms"]
                    else {}
                ),
                **(
                    {"genre_option": filters["genre_option"]}
                    if self.request.GET.get("genre_option")
                    else {}
                ),
            }
        )
        context["min_year"] = min_year
        context["max_year"] = max_year
        # Convert highlight to int for comparison with game.id in template
        highlight_str = self.request.GET.get("highlight")
        context["highlight"] = (
            int(highlight_str) if highlight_str and highlight_str.isdigit() else None
        )
        context["is_filtered"] = True  # GameSearch is always filtered
        context["filter_title"] = _build_filter_title(
            filters, genres, platforms, min_year, max_year
        )
        # Only show subtitle when multiple genres are selected
        if len(filters["genres"]) > 1:
            context["genre_subtitle"] = _build_genre_subtitle(
                filters["genres"], filters["genre_option"], genres
            )
        else:
            context["genre_subtitle"] = ""

        # Get year counts for heatmap grid based on current filters (excluding year)
        # This allows users to see which years have games given their other filters
        base_qs = models.Game.objects.all()

        # Apply search filter (same as get_queryset)
        q = self.request.GET.get("q")
        if q:
            base_qs = base_qs.filter(name__icontains=q)

        # Apply genre filter (same as get_queryset)
        genre_option = self.request.GET.get("genre_option", "all")
        genres_param = self.request.GET.get("genres")
        if genres_param:
            genre_ids = [int(x) for x in genres_param.split(",")]
            match_all = genre_option != "any"
            base_qs = utils.apply_genre_filter(base_qs, genre_ids, match_all=match_all)

        # Apply platform filter (same as get_queryset)
        platforms_param = self.request.GET.get("platforms")
        if platforms_param:
            platform_ids = [int(x) for x in platforms_param.split(",")]
            base_qs = utils.apply_platform_filter(base_qs, platform_ids)

        # Calculate year counts from filtered base queryset
        # Use distinct=True to avoid counting games multiple times when M2M JOINs
        # cause duplicate rows (e.g., a game with WIN+MAC platforms matched twice)
        all_years = range(min_year, max_year + 1)
        year_count_map = {
            entry["year_of_release"]: entry["count"]
            for entry in base_qs.values("year_of_release")
            .annotate(count=Count("id", distinct=True))
            .order_by("year_of_release")
        }
        all_years_with_counts = [
            {"year": x, "count": year_count_map.get(x, 0)} for x in all_years
        ]

        context["year_counts"] = all_years_with_counts

        # FACETED COUNTS FOR GENRES
        # For "Match Any": apply all filters EXCEPT genres (standard faceted filtering)
        # For "Match All": INCLUDE genre filter (shows intersection - how many games
        #                 have ALL selected genres AND this additional genre)
        genre_facet_qs = models.Game.objects.all()
        if q:
            genre_facet_qs = genre_facet_qs.filter(name__icontains=q)
        genre_facet_qs = utils.apply_year_filters(
            genre_facet_qs,
            decade=decade_param,
            year=year_param,
            start=start_param,
            end=end_param,
        )
        if platforms_param:
            platform_ids = [int(x) for x in platforms_param.split(",")]
            genre_facet_qs = utils.apply_platform_filter(genre_facet_qs, platform_ids)

        # For Match All mode, use subquery approach to get all genres on matching games
        # This shows "how many games have all selected genres AND this genre"
        # Note: We must use a subquery because Django ORM reuses JOINs, which would
        # otherwise limit results to only the filtered genre IDs
        if genres_param and genre_option == "all":
            genre_ids = [int(x) for x in genres_param.split(",")]
            # First, get IDs of games that have ALL selected genres
            filtered_game_ids = utils.apply_genre_filter(
                genre_facet_qs, genre_ids, match_all=True
            ).values_list("id", flat=True)
            # Then count genres on those games (fresh queryset avoids JOIN reuse)
            genre_counts = dict(
                models.Game.objects.filter(id__in=list(filtered_game_ids))
                .values("genres__id")
                .exclude(genres__id__isnull=True)
                .annotate(count=Count("id", distinct=True))
                .values_list("genres__id", "count")
            )
        else:
            # For Match Any mode or no genre filter, standard faceted counting
            genre_counts = dict(
                genre_facet_qs.values("genres__id")
                .exclude(genres__id__isnull=True)
                .annotate(count=Count("id", distinct=True))
                .values_list("genres__id", "count")
            )

        # FACETED COUNTS FOR PLATFORMS
        # Base: apply all filters EXCEPT platforms (q, year, genres)
        platform_facet_qs = models.Game.objects.all()
        if q:
            platform_facet_qs = platform_facet_qs.filter(name__icontains=q)
        platform_facet_qs = utils.apply_year_filters(
            platform_facet_qs,
            decade=decade_param,
            year=year_param,
            start=start_param,
            end=end_param,
        )
        if genres_param:
            genre_ids = [int(x) for x in genres_param.split(",")]
            match_all = genre_option != "any"
            platform_facet_qs = utils.apply_genre_filter(
                platform_facet_qs, genre_ids, match_all=match_all
            )

        # Count games per platform
        platform_counts = dict(
            platform_facet_qs.values("platforms__id")
            .exclude(platforms__id__isnull=True)
            .annotate(count=Count("id", distinct=True))
            .values_list("platforms__id", "count")
        )

        # Merge filtered counts into genres/platforms lists
        genres_with_filtered = [
            {**g, "filtered_count": genre_counts.get(int(g["id"]), 0)} for g in genres
        ]
        platforms_with_filtered = [
            {**p, "filtered_count": platform_counts.get(int(p["id"]), 0)}
            for p in platforms
        ]

        # Replace context with filtered versions
        context["genres"] = genres_with_filtered
        context["platforms"] = platforms_with_filtered

        # JSON for HTMX partial updates (keyed by string ID)
        context["genre_counts_json"] = {str(k): v for k, v in genre_counts.items()}
        context["platform_counts_json"] = {
            str(k): v for k, v in platform_counts.items()
        }

        # Load More context
        page_obj = context.get("page_obj")
        if page_obj:
            context["has_more"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()
            context["remaining_count"] = max(
                0, page_obj.paginator.count - page_obj.end_index()
            )
            context["max_loaded"] = page_obj.end_index() >= 1000

        return context


class DeveloperListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    model = models.DeveloperAlias
    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 150
    paginate_orphans = 0
    htmx_partial_template = "developers/includes/_developer_list_content.html"

    def get_template_names(self):
        # Append mode for Load More - returns just rows
        if self.request.GET.get("append") == "true":
            return ["developers/includes/_developer_list_append.html"]
        return super().get_template_names()

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Load More context
        page_obj = context.get("page_obj")
        if page_obj:
            context["has_more"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()
            context["remaining_count"] = max(
                0, page_obj.paginator.count - page_obj.end_index()
            )

        return context


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
    paginate_by = 150
    paginate_orphans = 0
    htmx_partial_template = "lists/includes/_list_list_content.html"

    def get_template_names(self):
        # Append mode for Load More - returns just rows
        if self.request.GET.get("append") == "true":
            return ["lists/includes/_list_list_append.html"]
        return super().get_template_names()

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

        # Convert URL slug to type code for filtering
        type_slug = self.request.GET.get("type")
        if type_slug:
            type_code = constants.LIST_TYPE_CODES.get(type_slug)
            if type_code:
                qs = qs.filter(type=type_code)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Extract and validate filter values
        publisher_id = self.request.GET.get("publisher")
        year_value = self.request.GET.get("year")
        type_slug = self.request.GET.get("type")

        try:
            publisher_id = int(publisher_id) if publisher_id else None
        except (ValueError, TypeError):
            publisher_id = None

        try:
            year_value = int(year_value) if year_value else None
        except (ValueError, TypeError):
            year_value = None

        # Convert URL slug to type code for database queries
        type_code = constants.LIST_TYPE_CODES.get(type_slug) if type_slug else None

        # --- FACETED COUNTS ---
        # Each dropdown shows counts based on OTHER filters applied

        # 1. Year counts: filtered by publisher + type (NOT year)
        year_base_qs = models.List.objects.all()
        if publisher_id:
            year_base_qs = year_base_qs.filter(publisher_id=publisher_id)
        if type_code:
            year_base_qs = year_base_qs.filter(type=type_code)

        list_year_counts = list(
            year_base_qs.values("year").annotate(count=Count("id")).order_by("year")
        )

        # Filter years: include count > 0 OR currently selected
        year_str = str(year_value) if year_value else None
        filtered_years = [
            y for y in list_year_counts if y["count"] > 0 or str(y["year"]) == year_str
        ]

        # 2. Publisher counts: filtered by year + type (NOT publisher)
        publisher_base_qs = models.List.objects.all()
        if year_value:
            publisher_base_qs = publisher_base_qs.filter(year=year_value)
        if type_code:
            publisher_base_qs = publisher_base_qs.filter(type=type_code)

        publisher_ids_with_counts = dict(
            publisher_base_qs.values("publisher_id")
            .annotate(count=Count("id"))
            .values_list("publisher_id", "count")
        )

        # Include publishers with count > 0 OR currently selected
        publishers = []
        for pub in models.Publication.objects.order_by("name"):
            count = publisher_ids_with_counts.get(pub.id, 0)
            if count > 0 or pub.id == publisher_id:
                pub.list_count = count
                publishers.append(pub)

        # 3. Type counts: filtered by publisher + year (NOT type)
        type_base_qs = models.List.objects.all()
        if publisher_id:
            type_base_qs = type_base_qs.filter(publisher_id=publisher_id)
        if year_value:
            type_base_qs = type_base_qs.filter(year=year_value)

        type_counts_raw = list(
            type_base_qs.values("type").annotate(count=Count("id")).order_by("type")
        )

        # Add slug to each type and filter: include count > 0 OR currently selected
        filtered_types = []
        for t in type_counts_raw:
            t["slug"] = constants.LIST_TYPE_SLUGS.get(t["type"], t["type"])
            if t["count"] > 0 or t["type"] == type_code:
                filtered_types.append(t)

        # Build context
        context["meta"] = {"lists": {"years": filtered_years}}
        context["publishers"] = publishers
        context["list_types"] = constants.LIST_TYPES
        context["type_counts"] = filtered_types
        context["filters"] = {
            "publisher": str(publisher_id) if publisher_id else None,
            "year": str(year_value) if year_value else None,
            "type": type_slug,  # Keep as slug for template comparison
        }

        # Load More context
        page_obj = context.get("page_obj")
        if page_obj:
            context["has_more"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()
            context["remaining_count"] = max(
                0, page_obj.paginator.count - page_obj.end_index()
            )

        return context


class PostListView(RobustPaginationMixin, ListView):
    model = models.Post
    template_name = "posts/post_list.html"
    context_object_name = "posts"
    paginate_by = 5
    paginate_orphans = 0

    def get_template_names(self):
        # Append mode for Load More - returns just posts
        if self.request.GET.get("append") == "true":
            return ["posts/includes/_post_list_append.html"]
        return super().get_template_names()

    def get_queryset(self):
        return models.Post.objects.filter(active=True).order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Load More context
        page_obj = context.get("page_obj")
        if page_obj:
            context["has_more"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()
            context["remaining_count"] = max(
                0, page_obj.paginator.count - page_obj.end_index()
            )

        return context


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


def robots_txt(request):
    """
    Serve robots.txt for search engine crawlers.
    """
    content = """User-agent: *
Allow: /

Sitemap: https://www.acclaimedvideogames.com/sitemap.xml
"""
    return HttpResponse(content, content_type="text/plain")


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

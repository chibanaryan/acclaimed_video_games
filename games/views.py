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
from games.forms import ImportForm, ContactForm, SubscribeForm
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
    # Groups are checked in order - broader manufacturer groups first, then form factors
    # This ensures "Nintendo" is used when all Nintendo platforms are selected,
    # but "Nintendo Handheld" when only handhelds are selected
    all_groups = [
        # Big manufacturer groups (checked first to collapse when all are selected)
        (
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
                "GB",
                "GBA",
                "GBC",
                "FDS",
            ],
        ),
        ("PlayStation", ["PS", "PS2", "PS3", "PS4", "PS5", "PSP", "PSV", "PSVR"]),
        ("Sega", ["GEN", "SMS", "DC", "SAT", "GG", "SCD"]),
        # Other manufacturer groups
        ("Xbox", ["Xbox", "X360", "XB1", "XBXS"]),
        ("PC", ["WIN", "DOS", "LIN", "MAC"]),
        ("Arcade, Mobile & VR", ["ARC", "AND", "iOS", "LMD", "VR", "BR"]),
        (
            "Retro Consoles",
            [
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
        ),
        (
            "Microcomputers",
            [
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
        ),
        # Form factor groups (checked after manufacturer groups)
        ("Nintendo Handheld", ["GB", "GBC", "GBA", "DS", "3DS"]),
        (
            "Nintendo Home Console",
            ["NES", "FDS", "SNES", "N64", "GC", "Wii", "WiiU", "SW"],
        ),
        ("PlayStation Handheld", ["PSP", "PSV"]),
        ("PlayStation Home Console", ["PS", "PS2", "PS3", "PS4", "PS5", "PSVR"]),
        ("Sega Handheld", ["GG"]),
        ("Sega Home Console", ["SMS", "GEN", "SCD", "SAT", "DC"]),
    ]

    name_lookup = {str(p["id"]): p["name"] for p in platforms}
    code_lookup = {str(p["id"]): p.get("code") for p in platforms}

    selected_ids = {str(pid) for pid in selected_platform_ids}
    labels = []
    consumed_ids = set()

    # Add group labels when entire group is selected (checking more specific first)
    for group_name, codes in all_groups:
        group_ids = [pid for pid, code in code_lookup.items() if code in codes]
        # Only match if ALL platforms in group are selected, none consumed
        unconsumed_group_ids = [gid for gid in group_ids if gid not in consumed_ids]
        if unconsumed_group_ids and all(
            gid in selected_ids for gid in unconsumed_group_ids
        ):
            # Check if this exact set matches (not a subset)
            if set(unconsumed_group_ids) == set(group_ids):
                labels.append(group_name)
                consumed_ids.update(group_ids)

    # Add remaining platform names
    for pid in selected_ids - consumed_ids:
        labels.append(name_lookup.get(pid, pid))

    if not labels:
        return "Video" + (" Games" if include_games else "")
    return f"{_join_names(labels)}" + (" Games" if include_games else "")


def _expand_platform_virtual_ids(platforms_param, platforms):
    """Expand virtual IDs (mfr-nintendo, ff-nintendo-home) to actual platform IDs.

    Returns a list of platform IDs (integers) that should be used for filtering.
    If the param contains regular IDs, returns those directly.
    Using - instead of : for URL-friendliness.
    """
    if not platforms_param:
        return []

    # Platform hierarchy - maps virtual IDs to platform codes
    virtual_id_to_codes = {
        # Manufacturer virtual IDs
        "mfr-nintendo": [
            "NES",
            "FDS",
            "SNES",
            "N64",
            "GC",
            "Wii",
            "WiiU",
            "SW",
            "GB",
            "GBC",
            "GBA",
            "DS",
            "3DS",
        ],
        "mfr-playstation": ["PS", "PS2", "PS3", "PS4", "PS5", "PSVR", "PSP", "PSV"],
        "mfr-xbox": ["Xbox", "X360", "XB1", "XBXS"],
        "mfr-sega": ["SMS", "GEN", "SCD", "SAT", "DC", "GG"],
        "mfr-pc": ["WIN", "DOS", "LIN", "MAC"],
        "mfr-arcadePlus": ["ARC", "AND", "iOS", "LMD", "VR", "BR"],
        "mfr-retro": [
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
        "mfr-computers": [
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
        # Form factor virtual IDs
        "ff-nintendo-home": ["NES", "FDS", "SNES", "N64", "GC", "Wii", "WiiU", "SW"],
        "ff-nintendo-handheld": ["GB", "GBC", "GBA", "DS", "3DS"],
        "ff-playstation-home": ["PS", "PS2", "PS3", "PS4", "PS5", "PSVR"],
        "ff-playstation-handheld": ["PSP", "PSV"],
        "ff-sega-home": ["SMS", "GEN", "SCD", "SAT", "DC"],
        "ff-sega-handheld": ["GG"],
    }

    # Build code -> ID lookup from platforms list (ensure int IDs)
    code_to_id = {p.get("code"): int(p["id"]) for p in platforms if p.get("code")}

    platform_ids = []
    for param in platforms_param.split(","):
        param = param.strip()
        if param in virtual_id_to_codes:
            # Virtual ID - expand to all platform codes
            codes = virtual_id_to_codes[param]
            for code in codes:
                if code in code_to_id:
                    platform_ids.append(code_to_id[code])
        else:
            # Regular ID - try to parse as int
            try:
                platform_ids.append(int(param))
            except ValueError:
                pass  # Skip invalid IDs

    return platform_ids


def _build_genre_subtitle(selected_genre_ids, option, genres):
    """Return subtitle string with AND/OR connector for genres."""
    if not selected_genre_ids:
        return ""
    name_lookup = {str(g["id"]): g["name"] for g in genres}
    genre_names = [name_lookup.get(str(gid), str(gid)) for gid in selected_genre_ids]
    if not genre_names:
        return ""
    connector = " AND " if option == "all" else " OR "
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

        # Fetch latest posts (limit 5 for home page)
        context["posts"] = models.Post.objects.filter(active=True).order_by("-date")[:5]

        # Fetch top 30 games for display
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
    platforms_param = request.GET.get("platforms")

    if q:
        qs = qs.filter(name__icontains=q)

    qs = utils.apply_year_filters(qs, decade=decade, year=year, start=start, end=end)

    if genres_param:
        genre_ids = [int(x) for x in genres_param.split(",") if x]
        qs = utils.apply_genre_filter(
            qs, genre_ids, match_all=False, use_wikipedia=True
        )
    else:
        genre_ids = []

    # Get platforms list for virtual ID expansion
    platforms_lookup = utils.get_or_set_cache(
        "search_platforms_list",
        models.Platform.objects.all(),
        ["id", "name", "code"],
        order_by="name",
        transform_id=True,
    )

    if platforms_param:
        platform_ids = _expand_platform_virtual_ids(platforms_param, platforms_lookup)
        qs = utils.apply_platform_filter(qs, platform_ids)
    else:
        platform_ids = []

    qs = qs.distinct().order_by("rank")

    use_filtered_rank = True

    # Build filename based on filters
    min_year, max_year = _get_year_bounds()
    genres_lookup = utils.get_or_set_cache(
        "search_genres_list_with_counts",
        models.IGDBGenre.objects.annotate(game_count=Count("game")),
        ["id", "name", "game_count"],
        order_by="name",
        transform_id=True,
    )
    # platforms_lookup already defined above for virtual ID expansion

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
        developers = ", ".join(d.name for d in game.studios.all())
        platforms = ", ".join(p.name for p in game.platforms.all())
        genres = ", ".join(g.name for g in game.wikipedia_genres.all())
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
            "studios",
            "studios__company",
            "platforms",
            "genres",
            "quotes",
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

        # Genre filtering (single-select, so match_all doesn't matter)
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            qs = utils.apply_genre_filter(
                qs, genre_ids, match_all=False, use_wikipedia=True
            )

        # Platform filtering (with virtual ID expansion)
        platforms_param = self.request.GET.get("platforms")
        if platforms_param:
            platforms_list = utils.get_or_set_cache(
                "search_platforms_list",
                models.Platform.objects.all(),
                ["id", "name", "code"],
                order_by="name",
                transform_id=True,
            )
            platform_ids = _expand_platform_virtual_ids(platforms_param, platforms_list)
            qs = utils.apply_platform_filter(qs, platform_ids)

        # Series filtering
        series_param = self.request.GET.get("series")
        if series_param:
            series_ids = [int(x) for x in series_param.split(",") if x.strip()]
            qs = utils.apply_series_filter(qs, series_ids)

        # Sort order
        sort = self.request.GET.get("sort", "rank")

        # Apply sorting
        if sort == "year":
            return qs.distinct().order_by("year_of_release", "rank")
        elif sort == "name":
            return qs.distinct().order_by("name")
        else:  # Default to rank
            return qs.distinct().order_by("rank")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get Wikipedia genres with hierarchy for AdvancedFilters (cached for 24 hours)
        # Convert IDs to strings for proper Alpine.js binding
        # Includes game_count for heatmap visualization and hierarchy fields
        # Filter out genres with 0 games (but keep parents if children have games)
        genres = cache.get("search_wikipedia_genres_list_with_counts")
        if genres is None:
            all_genres = list(
                models.WikipediaGenre.objects.annotate(
                    game_count=Count("games_with_wikipedia_genre")
                )
                .order_by("level", "display_order", "name")
                .values(
                    "id",
                    "name",
                    "game_count",
                    "parent_id",
                    "level",
                    "display_order",
                    "slug",
                )
            )
            # Find parent IDs that have children with games
            parents_with_games = {
                g["parent_id"]
                for g in all_genres
                if g["game_count"] > 0 and g["parent_id"]
            }
            # Keep genres that have games OR are parents with children that have games
            genres = [
                {
                    **g,
                    "id": str(g["id"]),
                    "parent_id": str(g["parent_id"]) if g["parent_id"] else None,
                }
                for g in all_genres
                if g["game_count"] > 0 or g["id"] in parents_with_games
            ]
            cache.set(
                "search_wikipedia_genres_list_with_counts",
                genres,
                config.CACHE_TIMEOUT_DEFAULT,
            )

        platforms = utils.get_or_set_cache(
            "search_platforms_list",
            models.Platform.objects.all(),
            ["id", "name", "code"],
            order_by="name",
            transform_id=True,
        )

        # Get series list with game counts (only show series with 2+ games)
        MIN_SERIES_GAMES = 2
        series_list = cache.get("search_series_list_with_counts")
        if series_list is None:
            series_list = list(
                models.Series.objects.annotate(game_count=Count("games"))
                .filter(game_count__gte=MIN_SERIES_GAMES)
                .values("id", "name", "slug", "game_count")
                .order_by("-game_count", "name")
            )
            # Convert IDs to strings for Alpine.js
            series_list = [{**s, "id": str(s["id"])} for s in series_list]
            cache.set(
                "search_series_list_with_counts",
                series_list,
                config.CACHE_TIMEOUT_DEFAULT,
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
        q_param = self.request.GET.get("q", "")
        sort_param = self.request.GET.get("sort", "rank")
        genres_param = self.request.GET.get("genres")
        platforms_param = self.request.GET.get("platforms")
        series_param = self.request.GET.get("series")

        # Determine if any filter actually narrows results (affects rank display)
        # Year filter only counts if it's narrower than the full range
        has_year_filter = (
            (year_param or decade_param)
            or (start_val > min_year)
            or (end_val < max_year)
        )
        has_any_filter = (
            q_param
            or has_year_filter
            or genres_param
            or platforms_param
            or series_param
            or sort_param != "rank"
        )

        filters = {
            "q": q_param,
            "start": start_val,
            "end": end_val,
            "genres": genres_param.split(",") if genres_param else [],
            "platforms": platforms_param.split(",") if platforms_param else [],
            "series": series_param.split(",") if series_param else [],
            "rank_display": "filtered" if has_any_filter else "alltime",
            "sort": sort_param,
            # Keep legacy params for context
            "year": year_param,
            "decade": decade_param,
        }

        context["genres"] = genres
        context["platforms"] = platforms
        context["series_list"] = series_list
        context["filters"] = filters
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
                    {"series": ",".join(filters["series"])} if filters["series"] else {}
                ),
                **(
                    {"sort": filters["sort"]}
                    if self.request.GET.get("sort")
                    and self.request.GET.get("sort") != "rank"
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
        # Genre subtitle not needed for single-select mode
        context["genre_subtitle"] = ""

        # Get year counts for heatmap grid based on current filters (excluding year)
        # This allows users to see which years have games given their other filters
        base_qs = models.Game.objects.all()

        # Apply search filter (same as get_queryset)
        q = self.request.GET.get("q")
        if q:
            base_qs = base_qs.filter(name__icontains=q)

        # Apply genre filter (single-select, so match_all doesn't matter)
        genres_param = self.request.GET.get("genres")
        if genres_param:
            genre_ids = [int(x) for x in genres_param.split(",")]
            base_qs = utils.apply_genre_filter(
                base_qs, genre_ids, match_all=False, use_wikipedia=True
            )

        # Apply platform filter (same as get_queryset, with virtual ID expansion)
        platforms_param = self.request.GET.get("platforms")
        if platforms_param:
            platform_ids = _expand_platform_virtual_ids(platforms_param, platforms)
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
        # Apply all filters EXCEPT genres (standard faceting for single-select)
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
            platform_ids = _expand_platform_virtual_ids(platforms_param, platforms)
            genre_facet_qs = utils.apply_platform_filter(genre_facet_qs, platform_ids)

        # Standard faceted counting (single-select mode)
        genre_counts = dict(
            genre_facet_qs.values("wikipedia_genres__id")
            .exclude(wikipedia_genres__id__isnull=True)
            .annotate(count=Count("id", distinct=True))
            .values_list("wikipedia_genres__id", "count")
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
            platform_facet_qs = utils.apply_genre_filter(
                platform_facet_qs, genre_ids, match_all=False, use_wikipedia=True
            )

        # Count games per platform
        platform_counts = dict(
            platform_facet_qs.values("platforms__id")
            .exclude(platforms__id__isnull=True)
            .annotate(count=Count("id", distinct=True))
            .values_list("platforms__id", "count")
        )

        # Merge filtered counts into IGDB genres/platforms lists
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

        # Enable client-side filtering for fast subsequent interactions
        context["enable_client_filtering"] = True

        return context


class DeveloperListItem:
    """
    Wrapper to normalize Company and Studio objects for unified display.

    Allows the developers list to include both parent Companies and Studios
    with consistent interface for templates.
    """

    def __init__(self, obj, game_count, is_company=False):
        self.obj = obj
        self.recursive_games_count = game_count
        self.is_company = is_company

    @property
    def id(self):
        return self.obj.id

    @property
    def name(self):
        return self.obj.name

    @property
    def slug(self):
        """Return slug for Companies, None for Studios."""
        return self.obj.slug if self.is_company else None

    @property
    def company(self):
        """Return parent company for Studios, None for Companies."""
        return None if self.is_company else self.obj.company

    @property
    def root_company(self):
        """Return root company for Studios, None for Companies."""
        if self.is_company:
            return None
        return getattr(self.obj, "root_company", self.obj.company)

    @property
    def games_count(self):
        """Fallback for template compatibility - same as recursive_games_count."""
        return self.recursive_games_count


class StudioListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    model = models.Studio
    template_name = "developers/company_list.html"
    context_object_name = "developers"
    paginate_by = 150
    paginate_orphans = 0
    htmx_partial_template = "developers/includes/_company_list_content.html"

    def _get_studio_hierarchy(self):
        """
        Build a map of studio_id -> list of child studio IDs.

        A studio can have children if a Company with the same name exists
        AND that company is different from the studio's own parent company.
        (If the matching company is the studio's parent, those are siblings.)
        """
        from django.core.cache import cache

        cache_key = "studio_list_hierarchy_map_v2"
        hierarchy = cache.get(cache_key)
        if hierarchy is not None:
            return hierarchy

        hierarchy = {}

        # Get all studios with their parent company IDs
        studios_with_company = list(
            models.Studio.objects.values_list("id", "name", "company_id")
        )

        # Find all companies that share a name with a studio
        studio_names = set(name for _, name, _ in studios_with_company)
        matching_companies = models.Company.objects.filter(
            name__in=studio_names
        ).prefetch_related("studios")

        # Build name -> company map
        company_by_name = {c.name: c for c in matching_companies}

        # For each studio, check if there's a DIFFERENT company with the same name
        for studio_id, studio_name, studio_company_id in studios_with_company:
            if studio_name in company_by_name:
                matching_company = company_by_name[studio_name]
                # Only add children if the matching company is NOT the studio's parent
                if matching_company.id != studio_company_id:
                    # Use .all() to leverage prefetch cache (values_list bypasses it)
                    child_ids = [s.id for s in matching_company.studios.all()]
                    if child_ids:
                        hierarchy[studio_id] = child_ids

        cache.set(cache_key, hierarchy, 3600)  # Cache for 1 hour
        return hierarchy

    def _get_all_descendant_ids(self, studio_id, hierarchy, visited=None):
        """Recursively get all descendant studio IDs."""
        if visited is None:
            visited = set()
        if studio_id in visited:
            return set()
        visited.add(studio_id)

        descendants = set()
        for child_id in hierarchy.get(studio_id, []):
            descendants.add(child_id)
            descendants.update(
                self._get_all_descendant_ids(child_id, hierarchy, visited)
            )
        return descendants

    def _collect_unique_game_ids(
        self, studio_id, hierarchy, game_ids_by_studio, visited=None
    ):
        """Recursively collect unique game IDs for a studio + all descendants."""
        if visited is None:
            visited = set()
        if studio_id in visited:
            return set()
        visited.add(studio_id)

        # Start with this studio's games
        unique_ids = set(game_ids_by_studio.get(studio_id, []))

        # Add games from all child studios
        for child_id in hierarchy.get(studio_id, []):
            unique_ids.update(
                self._collect_unique_game_ids(
                    child_id, hierarchy, game_ids_by_studio, visited
                )
            )
        return unique_ids

    def get_template_names(self):
        # Append mode for Load More - returns just rows
        if self.request.GET.get("append") == "true":
            return ["developers/includes/_company_list_append.html"]
        return super().get_template_names()

    def get_paginate_by(self, queryset):
        # Disable Django's pagination - we handle it manually in get_context_data
        # because we merge Companies and Studios into a unified list
        return None

    def get_queryset(self):
        from django.db.models import F

        qs = (
            models.Studio.objects.annotate(
                games_count=Count("games"),
            )
            .filter(games_count__gt=0)  # Only show studios with games
            .select_related("company")
            .distinct()
        )

        # Exclude primary studios (where studio name = company name)
        # These will be represented by the Company entry instead
        qs = qs.exclude(company__isnull=False, name=F("company__name"))

        # Search filter
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Sort parameter - "games" sort (default) is handled in get_context_data
        # because it requires recursive counting
        sort = self.request.GET.get("sort", "games")
        if sort != "games":
            qs = qs.order_by(Lower("name"))

        return qs

    def _get_company_game_counts(self, hierarchy, game_ids_by_studio):
        """
        Calculate aggregated game counts for all Companies.

        For each Company, recursively collects unique game IDs from all
        child studios and their descendants.
        """
        from collections import defaultdict

        company_game_counts = {}

        # Get all companies with their studios
        companies = (
            models.Company.objects.filter(slug__isnull=False)
            .exclude(slug="")
            .prefetch_related("studios")
        )

        for company in companies:
            all_game_ids = set()
            for studio in company.studios.all():
                # Get this studio's games + all descendant games
                all_game_ids.update(
                    self._collect_unique_game_ids(
                        studio.id, hierarchy, game_ids_by_studio
                    )
                )
            if all_game_ids:  # Only include companies with games
                company_game_counts[company] = len(all_game_ids)

        return company_game_counts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort = self.request.GET.get("sort", "games")
        search_query = self.request.GET.get("q", "").strip()
        context["sort"] = sort

        # Get the studios (full list when sorting by games, paginated otherwise)
        studios = list(context.get("developers", []))

        # Build hierarchy map and calculate recursive counts for all studios
        hierarchy = self._get_studio_hierarchy()

        # Collect all studio IDs we need game IDs for (including all descendants)
        all_studio_ids = set(s.id for s in studios)
        for studio in studios:
            all_studio_ids.update(self._get_all_descendant_ids(studio.id, hierarchy))

        # Also include all studios for Company game counting
        for company in models.Company.objects.prefetch_related("studios"):
            for studio in company.studios.all():
                all_studio_ids.add(studio.id)
                all_studio_ids.update(
                    self._get_all_descendant_ids(studio.id, hierarchy)
                )

        # Batch fetch game IDs for all relevant studios
        from collections import defaultdict

        game_ids_by_studio = defaultdict(list)
        for studio_id, game_id in models.Studio.objects.filter(
            id__in=all_studio_ids
        ).values_list("id", "games__id"):
            if game_id is not None:
                game_ids_by_studio[studio_id].append(game_id)

        # Calculate recursive counts for studios
        for studio in studios:
            unique_game_ids = self._collect_unique_game_ids(
                studio.id, hierarchy, game_ids_by_studio
            )
            studio.recursive_games_count = len(unique_game_ids)

        # Get Companies with aggregated game counts
        company_game_counts = self._get_company_game_counts(
            hierarchy, game_ids_by_studio
        )

        # Build unified developer list with DeveloperListItem wrappers
        developers = []

        # Add Companies (filter by search query if present)
        for company, game_count in company_game_counts.items():
            if search_query and search_query.lower() not in company.name.lower():
                continue
            developers.append(DeveloperListItem(company, game_count, is_company=True))

        # Add Studios (already filtered in get_queryset, but wrap them)
        for studio in studios:
            developers.append(
                DeveloperListItem(
                    studio, studio.recursive_games_count, is_company=False
                )
            )

        # Handle pagination and sorting
        if sort == "games":
            # Sort by game count (desc), then by name (asc) for ties
            developers.sort(key=lambda d: (-d.recursive_games_count, d.name.lower()))

            # Manual pagination
            try:
                page = int(self.request.GET.get("page", 1))
                if page < 1:
                    page = 1
            except (ValueError, TypeError):
                page = 1
            per_page = self.paginate_by
            total_count = len(developers)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page

            # Slice for current page
            context["developers"] = developers[start_idx:end_idx]

            # Build pagination context
            context["has_more"] = end_idx < total_count
            context["next_page"] = page + 1 if end_idx < total_count else None
            context["total_count"] = total_count
            context["loaded_count"] = min(end_idx, total_count)
            context["remaining_count"] = max(0, total_count - end_idx)
        else:
            # Sort alphabetically
            developers.sort(key=lambda d: d.name.lower())

            # Manual pagination for name sort too (since we're merging Companies)
            try:
                page = int(self.request.GET.get("page", 1))
                if page < 1:
                    page = 1
            except (ValueError, TypeError):
                page = 1
            per_page = self.paginate_by
            total_count = len(developers)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page

            context["developers"] = developers[start_idx:end_idx]
            context["has_more"] = end_idx < total_count
            context["next_page"] = page + 1 if end_idx < total_count else None
            context["total_count"] = total_count
            context["loaded_count"] = min(end_idx, total_count)
            context["remaining_count"] = max(0, total_count - end_idx)

        return context


class CompanyDetailView(DetailView):
    model = models.Company
    template_name = "developers/company_detail.html"
    context_object_name = "developer"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch studios and games with optimized queryset
        games_queryset = models.Game.objects.prefetch_related(
            "studios",
            "studios__company",
            "platforms",
            "genres",
        ).order_by("year_of_release")

        return models.Company.objects.prefetch_related(
            Prefetch(
                "studios",
                queryset=models.Studio.objects.order_by("name"),
            ),
            Prefetch("studios__games", queryset=games_queryset),
        )

    def flatten_studios(self, studios_data, parent_id=None, level=0):
        """Flatten recursive studio structure for checkbox tree."""
        flat = []
        for studio_data in studios_data:
            child_ids = [s["studio"].id for s in studio_data["sub_studios"]]
            flat.append(
                {
                    "id": studio_data["studio"].id,
                    "name": studio_data["studio"].name,
                    "game_ids": [g.id for g in studio_data["games"]],
                    "parent_id": parent_id,
                    "level": level,
                    "child_ids": child_ids,
                }
            )
            # Recursively flatten sub-studios
            flat.extend(
                self.flatten_studios(
                    studio_data["sub_studios"],
                    parent_id=studio_data["studio"].id,
                    level=level + 1,
                )
            )
        return flat

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = context["developer"]

        # Recursively gather studios with nested sub-studios
        def gather_studios(parent_company, visited=None):
            """Recursively gather studios and their games, including nested studios."""
            if visited is None:
                visited = set()

            if parent_company.id in visited:
                return []
            visited.add(parent_company.id)

            studios_data = []
            for studio in parent_company.studios.all():
                studio_games = list(studio.games.all())

                # Check if this studio also exists as a company (has sub-studios)
                sub_company = (
                    models.Company.objects.filter(name=studio.name)
                    .prefetch_related(
                        Prefetch(
                            "studios",
                            queryset=models.Studio.objects.order_by("name"),
                        )
                    )
                    .first()
                )
                sub_studios = []
                if sub_company and sub_company.id not in visited:
                    sub_studios = gather_studios(sub_company, visited)

                    # Filter out games that belong to sub-studios
                    # (show at most specific level)
                    if sub_studios:

                        def collect_sub_game_ids(studios):
                            """Recursively collect all game IDs from sub-studios."""
                            ids = set()
                            for s in studios:
                                ids.update(g.id for g in s["games"])
                                ids.update(collect_sub_game_ids(s["sub_studios"]))
                            return ids

                        sub_game_ids = collect_sub_game_ids(sub_studios)
                        studio_games = [
                            g for g in studio_games if g.id not in sub_game_ids
                        ]

                # Only include studios that have games OR sub-studios
                if studio_games or sub_studios:
                    studio_games.sort(key=lambda g: (g.year_of_release or 0))

                    # Calculate total unique games including all nested studios
                    def calc_total_games(games, sub_studios_list):
                        """
                        Count unique games to prevent double-counting
                        across siblings.
                        """
                        game_ids = {g.id for g in games}
                        for sub in sub_studios_list:
                            sub_ids = calc_unique_game_ids(
                                sub["games"], sub["sub_studios"]
                            )
                            game_ids.update(sub_ids)
                        return len(game_ids)

                    def calc_unique_game_ids(games, sub_studios_list):
                        """Recursively collect unique game IDs."""
                        game_ids = {g.id for g in games}
                        for sub in sub_studios_list:
                            game_ids.update(
                                calc_unique_game_ids(sub["games"], sub["sub_studios"])
                            )
                        return game_ids

                    # Calculate total nested studios
                    def calc_total_studios(sub_studios_list):
                        total = len(sub_studios_list)
                        for sub in sub_studios_list:
                            total += calc_total_studios(sub["sub_studios"])
                        return total

                    studios_data.append(
                        {
                            "studio": studio,
                            "games": studio_games,
                            "games_count": len(studio_games),
                            "sub_studios": sub_studios,
                            "total_games_count": calc_total_games(
                                studio_games, sub_studios
                            ),
                            "total_studios_count": calc_total_studios(sub_studios),
                        }
                    )

            return studios_data

        # Get all studios recursively
        studios_with_games = gather_studios(company)

        # Count unique games across all studios
        # (prevents double-counting across siblings)
        def collect_unique_game_ids(studios):
            """Recursively collect unique game IDs across all studios."""
            game_ids = set()
            for studio_data in studios:
                game_ids.update(g.id for g in studio_data["games"])
                game_ids.update(collect_unique_game_ids(studio_data["sub_studios"]))
            return game_ids

        total_games = len(collect_unique_game_ids(studios_with_games))

        # Count unique studios (flatten the hierarchy)
        def count_studios(studios):
            total = len(studios)
            for studio_data in studios:
                total += count_studios(studio_data["sub_studios"])
            return total

        studios_count = count_studios(studios_with_games)

        context["studios_with_games"] = studios_with_games
        context["total_games"] = total_games
        context["studios_count"] = studios_count

        # Add flattened studio data for filter UI
        studios_flat = self.flatten_studios(studios_with_games)

        # Prepend company as root node for the checkbox tree
        all_top_level_studio_ids = [s["id"] for s in studios_flat if s["level"] == 0]
        company_game_ids = collect_unique_game_ids(studios_with_games)
        company_entry = {
            "id": 0,  # Special ID for company (DB IDs start at 1)
            "name": company.name,
            "game_ids": list(company_game_ids),
            "level": 0,
            "child_ids": all_top_level_studio_ids,
        }

        # Increment all studio levels by 1 (company is now level 0)
        for studio in studios_flat:
            studio["level"] += 1

        # Insert company at the beginning
        studios_flat.insert(0, company_entry)

        context["studios_flat"] = studios_flat

        # Collect all unique games for filter view
        all_game_ids = collect_unique_game_ids(studios_with_games)
        all_games = list(
            models.Game.objects.filter(id__in=all_game_ids)
            .prefetch_related("studios", "platforms", "genres")
            .order_by("year_of_release")
        )
        context["all_games"] = all_games

        # Build studio -> game IDs mapping for Alpine.js
        # Each studio maps to ONLY its direct games (not descendants)
        # JavaScript handles hierarchical selection by checking/unchecking children
        studio_game_map = {}
        for studio in studios_flat:
            studio_game_map[studio["id"]] = studio["game_ids"]

        # Build studio -> child IDs mapping for Alpine.js
        studio_child_map = {s["id"]: s["child_ids"] for s in studios_flat}

        # Serialize to JSON for Alpine.js
        import json
        from django.core.serializers.json import DjangoJSONEncoder

        context["studio_game_map_json"] = json.dumps(
            studio_game_map, cls=DjangoJSONEncoder
        )
        context["studio_child_map_json"] = json.dumps(
            studio_child_map, cls=DjangoJSONEncoder
        )

        return context


class StudioRedirectView(View):
    """
    Redirects legacy /developer-alias/:id/ URLs to the company detail page.
    Also handles /studio/:id/ URLs (renamed but same functionality).
    """

    def get(self, request, id):
        studio = get_object_or_404(models.Studio, id=id)
        return redirect("developer-detail", slug=studio.company.slug, permanent=True)


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
        total_games = models.Game.objects.count()

        # Count metadata records (not games)
        # This persists when games are deleted (metadata is orphaned)
        total_igdb_metadata = models.IGDBGameData.objects.count()
        orphaned_igdb = models.IGDBGameData.objects.filter(game__isnull=True).count()
        connected_igdb = total_igdb_metadata - orphaned_igdb

        total_wikipedia_metadata = models.WikipediaGameData.objects.count()
        orphaned_wikipedia = models.WikipediaGameData.objects.filter(
            game__isnull=True
        ).count()
        connected_wikipedia = total_wikipedia_metadata - orphaned_wikipedia

        # Count games that need metadata (for fetch button)
        games_needing_igdb = models.Game.objects.filter(
            primary_igdb_game_data__isnull=True
        ).count()
        games_needing_wikipedia = models.Game.objects.filter(
            Q(primary_wikipedia_game_data__isnull=True)
            | Q(primary_wikipedia_game_data__page_title="")
        ).count()

        context["counts"] = {
            "platforms": models.Platform.objects.count(),
            "publications": models.Publication.objects.count(),
            "lists": models.List.objects.count(),
            "games": total_games,
            "memberships": models.ListMembership.objects.count(),
            "companies": models.Company.objects.count(),
            "studios": models.Studio.objects.count(),
            "igdb_genres": models.IGDBGenre.objects.count(),
            "wikipedia_genres": models.WikipediaGenre.objects.count(),
        }
        # Calculate time estimates for fetching metadata
        # IGDB: ~8-10 games/sec with default settings
        igdb_estimate_seconds = (
            int(games_needing_igdb / 9) if games_needing_igdb > 0 else 0
        )

        # Wikipedia: depends on authentication
        # Optimized to reuse page URLs from lookup (2 network requests per game)
        # Authenticated: ~1.0 games/sec, Unauthenticated: ~0.4 games/sec
        from django.conf import settings

        has_wikidata_auth = bool(getattr(settings, "WIKIDATA_ACCESS_TOKEN", None))
        wiki_games_per_sec = 1.0 if has_wikidata_auth else 0.4
        wiki_estimate_seconds = (
            int(games_needing_wikipedia / wiki_games_per_sec)
            if games_needing_wikipedia > 0
            else 0
        )

        context["igdb_counts"] = {
            "total": total_igdb_metadata,
            "connected": connected_igdb,
            "orphaned": orphaned_igdb,
            "games_needing": games_needing_igdb,
            "percentage": int(
                (connected_igdb / total_igdb_metadata * 100)
                if total_igdb_metadata > 0
                else 0
            ),
            "estimate_seconds": igdb_estimate_seconds,
        }
        context["wikipedia_counts"] = {
            "total": total_wikipedia_metadata,
            "connected": connected_wikipedia,
            "orphaned": orphaned_wikipedia,
            "games_needing": games_needing_wikipedia,
            "percentage": int(
                (connected_wikipedia / total_wikipedia_metadata * 100)
                if total_wikipedia_metadata > 0
                else 0
            ),
            "estimate_seconds": wiki_estimate_seconds,
            "has_auth": has_wikidata_auth,
        }

        # Get persistent errors from session
        import_errors = self.request.session.pop("import_errors", None)
        import_success_message = self.request.session.pop("import_success", None)
        context["import_errors"] = import_errors
        context["import_success_message"] = import_success_message

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
                res, message = utils.import_batch(seed_payload)
            except FileNotFoundError:
                res, message = (
                    False,
                    (
                        "Bundled test data files not found in "
                        "acclaimedgames/test_input_files."
                    ),
                )
            finally:
                for fh in opened_files.values():
                    fh.close()

            if res:
                self.request.session["import_success"] = (
                    "Loaded bundled test data.\n" + message
                )
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
            # Process batch import immediately
            res, message = utils.import_batch(import_data)
            if res:
                # Store success message in session (persist across redirect)
                self.request.session["import_success"] = message
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
        update_relationships = (
            request.GET.get("update_relationships", "false").lower() == "true"
        )
        return StreamingHttpResponse(
            utils.import_igdb_with_progress(update_relationships=update_relationships),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


class WikipediaPageProgressView(LoginRequiredMixin, View):
    """
    Streams Wikipedia page lookup progress via Server-Sent Events (SSE).
    Allows real-time progress bar updates in the browser.
    """

    def get(self, request, *args, **kwargs):
        """Stream Wikipedia page lookup progress as SSE events."""
        force_refresh = request.GET.get("force", "false").lower() == "true"
        return StreamingHttpResponse(
            utils.import_wikipedia_pages_with_progress(force_refresh=force_refresh),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


# =============================================================================
# Newsletter Subscription Views
# =============================================================================


class SubscribeView(FormView):
    """Handle newsletter subscription with double opt-in."""

    template_name = "subscribe.html"
    form_class = SubscribeForm
    success_url = reverse_lazy("subscribe_pending")

    def form_valid(self, form):  # pragma: no cover
        """Process valid subscription form and send confirmation email."""
        email = form.cleaned_data["email"]

        # Check if already subscribed
        subscriber, created = models.Subscriber.objects.get_or_create(email=email)

        if not created:
            # Already exists - check status
            if subscriber.is_confirmed and subscriber.is_active:
                # Already subscribed and active
                return redirect("subscribe_already")
            elif not subscriber.is_confirmed:
                # Pending confirmation - resend email
                utils.send_subscription_confirmation_email(subscriber)
                return redirect("subscribe_pending")
            else:
                # Was unsubscribed - reactivate and send confirmation
                subscriber.is_active = True
                subscriber.is_confirmed = False
                subscriber.save()
                utils.send_subscription_confirmation_email(subscriber)
                return redirect("subscribe_pending")
        else:
            # New subscriber - send confirmation email
            email_sent = utils.send_subscription_confirmation_email(subscriber)

            if not email_sent:
                # If email fails, delete the subscriber and show error
                subscriber.delete()
                form.add_error(
                    None,
                    (
                        "We're sorry, but there was an error sending "
                        "the confirmation email. Please try again later "
                        "or contact us at contact@acclaimedvideogames.com"
                    ),
                )
                return self.form_invalid(form)

        return super().form_valid(form)


class SubscribePendingView(TemplateView):
    """Display pending confirmation message."""

    template_name = "subscribe_pending.html"


class SubscribeAlreadyView(TemplateView):
    """Display already subscribed message."""

    template_name = "subscribe_already.html"


class ConfirmSubscriptionView(TemplateView):
    """Confirm subscription via token."""

    template_name = "subscribe_confirmed.html"

    def get(self, request, token):  # pragma: no cover
        """Process confirmation token."""
        try:
            subscriber = models.Subscriber.objects.get(confirmation_token=token)
            subscriber.is_confirmed = True
            subscriber.is_active = True
            subscriber.save()
            return self.render_to_response({"success": True})
        except models.Subscriber.DoesNotExist:
            return self.render_to_response({"success": False})


class UnsubscribeView(TemplateView):
    """Handle unsubscribe requests."""

    template_name = "unsubscribe.html"

    def get(self, request, token):  # pragma: no cover
        """Process unsubscribe token."""
        try:
            subscriber = models.Subscriber.objects.get(unsubscribe_token=token)
            subscriber.is_active = False
            subscriber.save()
            return self.render_to_response({"success": True, "email": subscriber.email})
        except models.Subscriber.DoesNotExist:
            return self.render_to_response({"success": False})

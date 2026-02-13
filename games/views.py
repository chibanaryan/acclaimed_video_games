import csv
import hashlib
import json
import logging
import math
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.flatpages.models import FlatPage
from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    Max,
    Prefetch,
    Q,
    When,
    Value,
    IntegerField,
)
from django.db.models.functions import Lower
from django.forms import Form
from django.http import HttpResponse, StreamingHttpResponse
from django.template.response import TemplateResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_headers
from django.views.generic import ListView, DetailView, TemplateView, FormView

from core.cache_helpers import get_year_bounds
from core.mixins import HTMXPartialMixin, RobustPaginationMixin
from core.models import User
from games import config, constants, models, utils
from games.cache import invalidate_played_games_cache, invalidate_want_to_play_cache
from games.forms import ImportForm, ContactForm
from games.services.percentile_service import calculate_percentile

logger = logging.getLogger(__name__)


def _get_year_bounds():
    """Return cached global min/max release years."""
    return get_year_bounds(
        model_class=models.Game,
        year_field="year_of_release",
        cache_key=config.CACHE_KEY_YEAR_STATS,
        cache_timeout=config.CACHE_TIMEOUT_24_HOURS,
        default_min=config.DEFAULT_MIN_YEAR,
    )


def _get_hero_stats():
    """Return cached hero section statistics (list, publication, game counts)."""
    cache_key = "homepage_hero_stats"
    stats = cache.get(cache_key)
    if stats is None:
        stats = {
            "list_count": models.List.objects.count(),
            "publication_count": models.Publication.objects.count(),
            "game_count": models.Game.objects.count(),
        }
        cache.set(cache_key, stats, config.CACHE_TIMEOUT_24_HOURS)
    return stats


def _normalize_cache_filters(filters, keys):
    normalized = {}
    for key in keys:
        value = filters.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value == "":
            continue
        if isinstance(value, (list, tuple, set)) and not value:
            continue
        if isinstance(value, (list, tuple, set)):
            normalized[key] = sorted(str(v) for v in value)
        else:
            normalized[key] = value
    return normalized


def _build_filter_cache_key(prefix, filters, keys, user_id=None):
    payload = _normalize_cache_filters(filters, keys)
    if user_id is not None:
        payload["user"] = user_id
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"{prefix}:{config.CACHE_VERSION}:{digest}"


def _get_played_game_ids(user):
    """Return cached list of played game IGDB IDs for a user."""
    cache_key = f"played_games_{user.id}"
    ids = cache.get(cache_key)
    if ids is None:
        ids = list(
            models.PlayedGame.objects.filter(user=user).values_list(
                "igdb_id", flat=True
            )
        )
        cache.set(cache_key, ids, 300)  # 5 minutes
    return ids


def _get_want_to_play_game_ids(user):
    """Return cached list of want-to-play game IGDB IDs for a user."""
    cache_key = f"want_to_play_games_{user.id}"
    ids = cache.get(cache_key)
    if ids is None:
        ids = list(
            models.WantToPlayGame.objects.filter(user=user).values_list(
                "igdb_id", flat=True
            )
        )
        cache.set(cache_key, ids, 300)  # 5 minutes
    return ids


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
        return f"the {start_year}s"
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
            "Microcomputer",
            [
                "VC20",
                "C64",
                "AMI",
                "CD32",
                "ZXS",
                "CPC",
                "BBCM",
                "ARCH",
                "PC88",
                "PC98",
                "FM7",
                "FMT",
                "SX1",
                "MSX",
                "A8",
                "AST",
                "A2",
                "T80",
                "TCC",
                "PDP",
                "HP21",
                "E60",
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
        # Microcomputer form factor groups
        ("Commodore", ["VC20", "C64", "AMI", "CD32"]),
        ("UK Microcomputer", ["ZXS", "CPC", "BBCM", "ARCH"]),
        ("Japanese Microcomputer", ["PC88", "PC98", "FM7", "FMT", "SX1", "MSX"]),
        ("Atari Microcomputer", ["A8", "AST"]),
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
            "VC20",
            "C64",
            "AMI",
            "CD32",
            "ZXS",
            "CPC",
            "BBCM",
            "ARCH",
            "PC88",
            "PC98",
            "FM7",
            "FMT",
            "SX1",
            "MSX",
            "A8",
            "AST",
            "A2",
            "T80",
            "TCC",
            "PDP",
            "HP21",
            "E60",
        ],
        # Form factor virtual IDs
        "ff-nintendo-home": ["NES", "FDS", "SNES", "N64", "GC", "Wii", "WiiU", "SW"],
        "ff-nintendo-handheld": ["GB", "GBC", "GBA", "DS", "3DS"],
        "ff-playstation-home": ["PS", "PS2", "PS3", "PS4", "PS5", "PSVR"],
        "ff-playstation-handheld": ["PSP", "PSV"],
        "ff-sega-home": ["SMS", "GEN", "SCD", "SAT", "DC"],
        "ff-sega-handheld": ["GG"],
        # Microcomputer form factor virtual IDs
        "ff-computers-commodore": ["VC20", "C64", "AMI", "CD32"],
        "ff-computers-uk": ["ZXS", "CPC", "BBCM", "ARCH"],
        "ff-computers-japan": ["PC88", "PC98", "FM7", "FMT", "SX1", "MSX"],
        "ff-computers-atari": ["A8", "AST"],
        "ff-computers-other": ["A2", "T80", "TCC", "PDP", "HP21", "E60"],
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
    genre_names = [name for name in genre_names if name]
    if not genre_names:
        return ""
    connector = " AND " if option == "all" else " OR "
    return f"Genre: {connector.join(genre_names)}"


def _apply_played_filter(qs, user, played_param):
    """Apply played status filter. Requires qs to have is_played_by_user annotation.

    Supports multi-select via comma-separated values (e.g., "no,want" shows both
    untracked and want-to-play games).
    """
    if not played_param or not user or not user.is_authenticated:
        return qs

    # Parse comma-separated values for multi-select support
    statuses = [s.strip() for s in played_param.split(",") if s.strip()]
    if not statuses:
        return qs

    # Build Q objects for each selected status
    q_filter = Q()
    for status in statuses:
        if status == "yes":
            q_filter |= Q(is_played_by_user=True)
        elif status == "want":
            q_filter |= Q(is_want_to_play_by_user=True)
        elif status == "no":
            q_filter |= Q(is_played_by_user=False, is_want_to_play_by_user=False)

    # Only apply filter if we have valid statuses
    if q_filter:
        return qs.filter(q_filter)
    return qs


def _build_filter_title(
    filters, genres, platforms, min_year, max_year, series_list=None
):
    """Compose the heading text based on filters."""
    start_year = filters.get("start")
    end_year = filters.get("end")
    time_window = _build_time_window(start_year, end_year, min_year, max_year)
    platform_label = _build_platform_segment(
        filters.get("platforms", []), platforms, include_games=False
    )
    # Fold selected genres into the title after platform
    genre_label = ""
    selected_genres = filters.get("genres") or []
    if selected_genres:
        name_lookup = {str(g["id"]): g["name"] for g in genres}
        genre_names = [
            name_lookup.get(str(gid), "").strip()
            for gid in selected_genres
            if name_lookup.get(str(gid), "").strip()
        ]
        if genre_names:
            genre_label = f" {_join_names(genre_names)}"

    # If exactly one series is selected, fold it into the title
    series_label = ""
    selected_series = filters.get("series") or []
    if len(selected_series) == 1 and series_list:
        name_lookup = {str(s["id"]): s["name"] for s in series_list}
        series_name = name_lookup.get(str(selected_series[0]), "").strip()
        if series_name:
            series_label = f" {series_name}"

    # Build HLTB playtime label
    hltb_label = ""
    hltb_mode = filters.get("hltb_mode", "main")
    hltb_min = filters.get("hltb_min")
    hltb_max = filters.get("hltb_max")

    if hltb_min is not None or hltb_max is not None:
        mode_suffix = " (100%)" if hltb_mode == "completionist" else ""
        time_desc = ""

        # Recognize preset patterns from min/max values
        # Short: 0-10, Medium: 10-30, Long: 30+
        if hltb_min == 0 and hltb_max == 10:
            time_desc = "Short (<10 Hour)"
        elif hltb_min == 10 and hltb_max == 30:
            time_desc = "Medium (10-30 Hour)"
        elif hltb_min == 30 and hltb_max is None:
            time_desc = "Long (30+ Hour)"
        # Custom ranges
        elif hltb_min == 0 and hltb_max is not None:
            time_desc = f"<{int(hltb_max)} Hour"
        elif hltb_min is not None and hltb_max is not None:
            if hltb_min == hltb_max:
                time_desc = f"~{int(hltb_min)} Hour"
            else:
                time_desc = f"{int(hltb_min)}-{int(hltb_max)} Hour"
        elif hltb_min is not None:
            time_desc = f"{int(hltb_min)}+ Hour"
        elif hltb_max is not None:
            time_desc = f"<{int(hltb_max)} Hour"

        if time_desc:
            hltb_label = f"{time_desc}{mode_suffix}"

    # Omit "Video" prefix when genre, series, or playtime is selected
    if platform_label == "Video" and (genre_label or series_label or hltb_label):
        platform_label = ""

    time_suffix = f" of {time_window}" if time_window else ""

    # Add played status suffix
    played_suffix = ""
    played = filters.get("played")
    if played == "yes":
        played_suffix = ": Played"
    elif played == "no":
        played_suffix = ": Untracked"

    # Build title with playtime before platform
    # Add space after hltb_label only if it exists
    if hltb_label:
        title = (
            f"Most Acclaimed {hltb_label} "
            f"{platform_label}{genre_label}{series_label} Games"
        )
    else:
        title = f"Most Acclaimed {platform_label}{genre_label}{series_label} Games"
    return f"{title}{time_suffix}{played_suffix}"


class ContactFormView(FormView):
    """Dedicated contact form handler (for form POST from modal)."""

    form_class = ContactForm
    success_url = reverse_lazy("contact_thank_you")
    template_name = "contact.html"  # Minimal template for form errors

    def form_valid(self, form):
        """Process valid contact form submission and send email."""
        name = form.cleaned_data["name"]
        email = form.cleaned_data["email"]
        category = form.cleaned_data["category"]
        message = form.cleaned_data["message"]

        # Send the email
        email_sent = utils.send_contact_email(name, email, category, message)

        if not email_sent:
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
    # Get filtered queryset using same logic as HomePageView
    # with_relations() already includes all needed prefetches:
    # developers, platforms, genres, and series.
    qs = models.Game.objects.with_relations()

    # Add played status annotation for authenticated users
    user = request.user
    is_authenticated = user.is_authenticated
    if is_authenticated:
        qs = qs.with_played_status(user)

    q = request.GET.get("q")
    decade = request.GET.get("decade")
    year = request.GET.get("year")
    start = request.GET.get("start")
    end = request.GET.get("end")
    genres_param = request.GET.get("genres")
    platforms_param = request.GET.get("platforms")
    series_param = request.GET.get("series")
    played_param = request.GET.get("played")

    # Parse HLTB parameters early (needed for filtering below)
    hltb_mode = request.GET.get("hltb_mode", "main")
    hltb_preset = request.GET.get("hltb_preset", "")
    hltb_min_param = request.GET.get("hltb_min")
    hltb_max_param = request.GET.get("hltb_max")

    # Convert to int or None
    hltb_min = None
    hltb_max = None
    if hltb_min_param:
        try:
            hltb_min = int(hltb_min_param)
            # Ensure non-negative
            if hltb_min < 0:
                hltb_min = 0
        except (ValueError, TypeError):
            pass
    if hltb_max_param and hltb_max_param != "unlimited":
        try:
            hltb_max = int(hltb_max_param)
            # Ensure non-negative
            if hltb_max < 0:
                hltb_max = 0
        except (ValueError, TypeError):
            pass

    # If max is set but min is not, default min to 0
    if hltb_max is not None and hltb_min is None:
        hltb_min = 0

    # Ensure max >= min (if both are set)
    if hltb_min is not None and hltb_max is not None:
        if hltb_max < hltb_min:
            hltb_max = hltb_min

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
        f"search_platforms_list:{config.CACHE_VERSION}",
        models.Platform.objects.all(),
        ["id", "name", "code", "year_start", "year_end"],
        order_by="name",
        transform_id=True,
    )

    if platforms_param:
        platform_ids = _expand_platform_virtual_ids(platforms_param, platforms_lookup)
        qs = utils.apply_platform_filter(qs, platform_ids)
    else:
        platform_ids = []

    # Apply series filter
    if series_param:
        series_ids = [int(x) for x in series_param.split(",") if x.strip()]
        qs = utils.apply_series_filter(qs, series_ids)

    # Apply played status filter (authenticated users only)
    qs = _apply_played_filter(qs, user, played_param)

    # Apply HLTB playtime filtering (reuse logic from GameSearchView)
    # Parse preset into min/max if provided
    pt_min = hltb_min
    pt_max = hltb_max
    if hltb_preset:
        preset_ranges = {
            "short": (0, 10),  # Under 10 hours
            "medium": (10, 30),  # 10-30 hours
            "long": (30, None),  # 30+ hours (no upper bound)
        }
        if hltb_preset in preset_ranges:
            pt_min, pt_max = preset_ranges[hltb_preset]

    # Determine field based on mode
    if hltb_mode == "completionist":
        field_prefix = "primary_hltb_game_data__completionist_hours"
    else:
        field_prefix = "primary_hltb_game_data__main_story_hours"

    # Apply filters and exclude games without HLTB data when filter is active
    # Filter on exact decimal values (no rounding in logic)
    if pt_min is not None or pt_max is not None:
        if pt_min is not None:
            try:
                qs = qs.filter(**{f"{field_prefix}__gte": int(pt_min)})
                qs = qs.exclude(**{field_prefix: None})
            except (ValueError, TypeError):  # pragma: no cover
                pass  # pragma: no cover
        if pt_max is not None:
            try:
                qs = qs.filter(**{f"{field_prefix}__lte": int(pt_max)})
                qs = qs.exclude(**{field_prefix: None})
            except (ValueError, TypeError):  # pragma: no cover
                pass  # pragma: no cover

    qs = qs.distinct().order_by("rank")

    use_filtered_rank = True

    # Build filename based on filters
    min_year, max_year = _get_year_bounds()
    genres_lookup = utils.get_or_set_cache(
        "search_genres_list_with_counts",
        models.WikipediaGenre.objects.annotate(
            game_count=Count("games_with_wikipedia_genre")
        ),
        ["id", "name", "game_count"],
        order_by="name",
        transform_id=True,
    )
    # platforms_lookup already defined above for virtual ID expansion

    # Get series list for title building (if series filter is used)
    series_list = None
    if series_param:
        series_ids_for_title = [int(x) for x in series_param.split(",") if x.strip()]
        series_list = list(
            models.Series.objects.filter(id__in=series_ids_for_title).values(
                "id", "name"
            )
        )
        # Convert IDs to strings for lookup
        for s in series_list:
            s["id"] = str(s["id"])

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

    # Get series IDs for title (if series filter is used)
    series_ids_for_filter = []
    if series_param:
        series_ids_for_filter = [str(x) for x in series_param.split(",") if x.strip()]

    # HLTB parameters already parsed at top of function

    filters_for_title = {
        "q": q or "",
        "start": start_for_title,
        "end": end_for_title,
        "genres": [str(gid) for gid in genre_ids],
        "platforms": [str(pid) for pid in platform_ids],
        "series": series_ids_for_filter,
        "played": (
            [s.strip() for s in played_param.split(",") if s.strip()]
            if played_param
            else []
        ),
        "rank_display": "filtered",
        "hltb_mode": hltb_mode,
        "hltb_preset": hltb_preset,
        "hltb_min": hltb_min,
        "hltb_max": hltb_max,
    }
    filter_title = _build_filter_title(
        filters_for_title,
        genres_lookup,
        platforms_lookup,
        min_year,
        max_year,
        series_list=series_list,
    )
    # Use the page title directly as the filename (slugified)
    filename_base = slugify(filter_title) or "acclaimed-games"
    filename = f"{filename_base}.csv"

    # Create CSV response
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Build header row - include Played column for authenticated users
    header = [
        "Filtered Rank",
        "Global Rank",
        "Name",
        "Year",
        "Developers",
        "Platforms",
        "Genres",
        "Series",
        "HLTB Main (hours)",
        "HLTB Main+Extra (hours)",
        "HLTB 100% (hours)",
    ]
    if is_authenticated:
        header.append("Played")
    writer.writerow(header)

    for index, game in enumerate(qs, start=1):
        developers = ", ".join(d.name for d in game.developers.all())
        platforms = ", ".join(p.name for p in game.platforms.all())
        genres = ", ".join(g.name for g in game.wikipedia_genres.all())
        series = ", ".join(s.name for s in game.series.all())
        filtered_rank = index if use_filtered_rank else game.rank

        # Get HLTB data
        hltb_main = ""
        hltb_main_extra = ""
        hltb_completionist = ""
        if game.primary_hltb_game_data:
            if game.primary_hltb_game_data.main_story_hours:
                hltb_main = f"{game.primary_hltb_game_data.main_story_hours:.1f}"
            if game.primary_hltb_game_data.main_extra_hours:
                hltb_main_extra = f"{game.primary_hltb_game_data.main_extra_hours:.1f}"
            if game.primary_hltb_game_data.completionist_hours:
                hltb_completionist = (
                    f"{game.primary_hltb_game_data.completionist_hours:.1f}"
                )

        row = [
            filtered_rank,
            game.rank,
            game.name,
            game.year_of_release,
            developers,
            platforms,
            genres,
            series,
            hltb_main,
            hltb_main_extra,
            hltb_completionist,
        ]
        if is_authenticated:
            # Use the annotated is_played_by_user field
            played = "Yes" if getattr(game, "is_played_by_user", False) else "No"
            row.append(played)
        writer.writerow(row)

    return response


class GameDetailView(DetailView):
    model = models.Game
    template_name = "games/game_detail.html"
    context_object_name = "game"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch lists with publisher, sorted by year (desc), publication, list name
        return models.Game.objects.select_related(
            "primary_igdb_game_data",
            "primary_wikipedia_game_data",
            "primary_hltb_game_data",
        ).prefetch_related(
            "developers",
            "developers__parent",
            "platforms",
            "wikipedia_genres",
            Prefetch(
                "lists",
                queryset=models.ListMembership.objects.select_related(
                    "list__publisher",
                ).order_by(
                    "-list__year",  # Year (descending)
                    "list__publisher__name",  # Publication name (alphabetical)
                    "list__name",  # List name (alphabetical)
                    "rank",  # Rank within list
                ),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        game = context["game"]

        # Build grouped lists from prefetched data (preserves prefetch ordering:
        # publication importance desc, year desc, name, rank)
        from collections import defaultdict

        grouped = defaultdict(list)
        for membership in game.lists.all():
            list_type = membership.list.type
            label = constants.get_list_type_label(list_type)
            grouped[label].append(
                {
                    "id": membership.list.id,
                    "name": membership.list.name,
                    "publication": (
                        membership.list.publisher.name
                        if membership.list.publisher
                        else ""
                    ),
                    "publisher": membership.list.publisher,
                    "type": list_type,
                    "type_name": label,
                    "url": membership.list.url,
                    "year": membership.list.year,
                    "rank": membership.rank,
                }
            )

        # Order groups by type importance (All-time, Decade, Misc, EOY)
        type_order = ["All time", "Decade", "Miscellaneous", "End of year"]
        sorted_grouped_lists = [(k, grouped[k]) for k in type_order if k in grouped]

        context["grouped_lists"] = sorted_grouped_lists

        # Check if current user has marked this game as played or want-to-play
        if self.request.user.is_authenticated and game.igdb_id:
            context["is_played"] = models.PlayedGame.objects.filter(
                user=self.request.user, igdb_id=game.igdb_id
            ).exists()
            context["is_want_to_play"] = models.WantToPlayGame.objects.filter(
                user=self.request.user, igdb_id=game.igdb_id
            ).exists()

        # Get series with 2+ games (single-game series aren't useful)
        # Must query Series separately for accurate game counts
        series_ids = list(game.series.values_list("id", flat=True))
        context["series_list"] = (
            models.Series.objects.filter(id__in=series_ids)
            .annotate(games_count=Count("games"))
            .filter(games_count__gte=2)
            .order_by("name")
        )

        # Total game count for rank context (e.g., "#47 of 3,240")
        # Cached since it rarely changes
        total_game_count = cache.get("total_game_count")
        if total_game_count is None:
            total_game_count = models.Game.objects.count()
            cache.set(
                "total_game_count", total_game_count, config.CACHE_TIMEOUT_24_HOURS
            )
        context["total_game_count"] = total_game_count

        # Decade and year counts for rank context - cached by decade/year
        if game.decade:
            cache_key = f"{config.CACHE_VERSION}:decade_count:{game.decade}"
            decade_count = cache.get(cache_key)
            if decade_count is None:
                decade_count = models.Game.objects.filter(
                    year_of_release__gte=game.decade,
                    year_of_release__lte=game.decade + 9,
                ).count()
                cache.set(cache_key, decade_count, config.CACHE_TIMEOUT_24_HOURS)
            context["decade_game_count"] = decade_count

        if game.year_of_release:
            cache_key = f"{config.CACHE_VERSION}:year_count:{game.year_of_release}"
            year_count = cache.get(cache_key)
            if year_count is None:
                year_count = models.Game.objects.filter(
                    year_of_release=game.year_of_release
                ).count()
                cache.set(cache_key, year_count, config.CACHE_TIMEOUT_24_HOURS)
            context["year_game_count"] = year_count

        return context


@method_decorator(vary_on_headers("X-Requested-With", "HX-Request"), name="dispatch")
class HomePageView(RobustPaginationMixin, ListView):
    model = models.Game
    template_name = "games/home.html"
    context_object_name = "games"
    paginate_by = 100
    paginate_orphans = 0
    CACHE_HEADER_SKIP = {
        "content-length",
        "content-type",
        "transfer-encoding",
        "connection",
    }

    @classmethod
    def _serialize_headers(cls, response):
        headers = {}
        for name, value in response.headers.items():
            if name.lower() in cls.CACHE_HEADER_SKIP:
                continue
            headers[name] = value
        return headers

    @staticmethod
    def _serialize_cookies(response):
        cookies = {}
        for name, morsel in response.cookies.items():
            max_age = morsel["max-age"] or None
            if max_age is not None:
                try:
                    max_age = int(max_age)
                except (TypeError, ValueError):
                    max_age = None
            cookies[name] = {
                "value": morsel.value,
                "expires": morsel["expires"] or None,
                "max_age": max_age,
                "path": morsel["path"] or "/",
                "domain": morsel["domain"] or None,
                "secure": bool(morsel["secure"]),
                "httponly": bool(morsel["httponly"]),
                "samesite": morsel["samesite"] or None,
            }
        return cookies

    @classmethod
    def _apply_cached_headers(cls, response, headers):
        for name, value in (headers or {}).items():
            if name.lower() in cls.CACHE_HEADER_SKIP:
                continue
            response[name] = value

    @staticmethod
    def _apply_cached_cookies(response, cookies):
        for name, data in (cookies or {}).items():
            response.set_cookie(
                name,
                data.get("value", ""),
                expires=data.get("expires") or None,
                max_age=data.get("max_age"),
                path=data.get("path") or "/",
                domain=data.get("domain") or None,
                secure=bool(data.get("secure")),
                httponly=bool(data.get("httponly")),
                samesite=data.get("samesite") or None,
            )

    def dispatch(self, request, *args, **kwargs):
        """Cache rendered home page content for anonymous users to reduce TTFB."""
        # Only cache for anonymous, non-HTMX full-page requests
        is_htmx = (
            request.headers.get("HX-Request")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.GET.get("partial") == "true"
            or request.GET.get("append") == "true"
        )

        if request.user.is_authenticated or is_htmx or request.method != "GET":
            return super().dispatch(request, *args, **kwargs)

        # Only cache the default home page (no query string)
        query_string = request.META.get("QUERY_STRING", "")
        if query_string:
            return super().dispatch(request, *args, **kwargs)
        cache_key = f"home_page:{config.CACHE_VERSION}:default"

        # Check cache (store only rendered content to avoid retaining request/context)
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            if isinstance(cached_payload, dict) and "content" in cached_payload:
                from django.http import HttpResponse

                content = cached_payload.get("content", b"")
                status = cached_payload.get("status", 200)
                content_type = cached_payload.get("content_type")
                response = HttpResponse(
                    content,
                    status=status,
                    content_type=content_type or "text/html; charset=utf-8",
                )
                self._apply_cached_headers(response, cached_payload.get("headers"))
                self._apply_cached_cookies(response, cached_payload.get("cookies"))
                return response
            # Drop legacy cached payloads (response objects) and rebuild.
            cache.delete(cache_key)

        # Generate response and cache it
        response = super().dispatch(request, *args, **kwargs)

        # Only cache successful, non-streaming responses (render first)
        if response.status_code == 200 and not getattr(response, "streaming", False):
            if hasattr(response, "render"):
                response.render()
            cache.set(
                cache_key,
                {
                    "content": response.content,
                    "status": response.status_code,
                    "content_type": response.get("Content-Type"),
                    "headers": self._serialize_headers(response),
                    "cookies": self._serialize_cookies(response),
                },
                config.CACHE_TIMEOUT_HOME_PAGE,
            )

        return response

    def get_paginate_by(self, queryset):
        """Always use standard page size - client-side handles deep jumps."""
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
        qs = (
            models.Game.objects.with_relations()
            .with_played_status(self.request.user)
            .with_list_count()
        )

        # Basic search by name (accent-insensitive via name_normalized)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(name_normalized__icontains=q))

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
                f"search_platforms_list:{config.CACHE_VERSION}",
                models.Platform.objects.all(),
                ["id", "name", "code", "year_start", "year_end"],
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

        # Played status filtering (authenticated users only)
        played_param = self.request.GET.get("played")
        qs = _apply_played_filter(qs, self.request.user, played_param)

        # HLTB playtime filtering
        hltb_mode = self.request.GET.get("hltb_mode", "main")
        hltb_preset = self.request.GET.get("hltb_preset")
        pt_min_param = self.request.GET.get("pt_min") or self.request.GET.get(
            "hltb_min"
        )
        pt_max_param = self.request.GET.get("pt_max") or self.request.GET.get(
            "hltb_max"
        )

        # Convert to int or None
        pt_min = None
        pt_max = None
        if pt_min_param:
            try:
                pt_min = int(pt_min_param)
                # Ensure non-negative
                if pt_min < 0:
                    pt_min = 0
            except (ValueError, TypeError):
                pass
        if pt_max_param and pt_max_param != "unlimited":
            try:
                pt_max = int(pt_max_param)
                # Ensure non-negative
                if pt_max < 0:
                    pt_max = 0
            except (ValueError, TypeError):
                pass

        # Parse preset into min/max if provided (overrides manual values)
        if hltb_preset:
            preset_ranges = {
                "short": (0, 10),  # Under 10 hours
                "medium": (10, 30),  # 10-30 hours
                "long": (30, None),  # 30+ hours (no upper bound)
            }
            if hltb_preset in preset_ranges:
                pt_min, pt_max = preset_ranges[hltb_preset]

        # If max is set but min is not, default min to 0
        if pt_max is not None and pt_min is None:
            pt_min = 0

        # Ensure max >= min (if both are set)
        if pt_min is not None and pt_max is not None:
            if pt_max < pt_min:
                pt_max = pt_min

        # Determine field based on mode
        if hltb_mode == "completionist":
            field_prefix = "primary_hltb_game_data__completionist_hours"
        else:
            field_prefix = "primary_hltb_game_data__main_story_hours"

        # Apply filters and exclude games without HLTB data when filter is active
        # Filter on exact decimal values (no rounding in logic)
        if pt_min is not None or pt_max is not None:
            if pt_min is not None:
                try:
                    qs = qs.filter(**{f"{field_prefix}__gte": int(pt_min)})
                    qs = qs.exclude(**{field_prefix: None})
                except (ValueError, TypeError):  # pragma: no cover
                    pass  # pragma: no cover
            if pt_max is not None:
                try:
                    qs = qs.filter(**{f"{field_prefix}__lte": int(pt_max)})
                    qs = qs.exclude(**{field_prefix: None})
                except (ValueError, TypeError):  # pragma: no cover
                    pass  # pragma: no cover

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
            f"search_platforms_list:{config.CACHE_VERSION}",
            models.Platform.objects.all(),
            ["id", "name", "code", "year_start", "year_end"],
            order_by="name",
            transform_id=True,
        )

        # Get series list with game counts (only show series with 2+ games)
        # Use version-based cache key (bump CACHE_VERSION in config to invalidate)
        MIN_SERIES_GAMES = 2
        series_cache_key = f"search_series_list_with_counts:{config.CACHE_VERSION}"
        series_list = cache.get(series_cache_key)
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
                series_cache_key,
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
        dir_param = self.request.GET.get("dir", "asc")
        genres_param = self.request.GET.get("genres")
        platforms_param = self.request.GET.get("platforms")
        series_param = self.request.GET.get("series")
        played_param = self.request.GET.get("played")

        # Parse HLTB parameters
        hltb_mode = self.request.GET.get("hltb_mode", "main")
        hltb_min_param = self.request.GET.get("hltb_min")
        hltb_max_param = self.request.GET.get("hltb_max")

        # Convert hltb_min and hltb_max to int or None
        hltb_min = None
        hltb_max = None
        if hltb_min_param:
            try:
                hltb_min = int(hltb_min_param)
                # Ensure non-negative
                if hltb_min < 0:
                    hltb_min = 0
            except (ValueError, TypeError):
                pass
        if hltb_max_param and hltb_max_param != "unlimited":
            try:
                hltb_max = int(hltb_max_param)
                # Ensure non-negative
                if hltb_max < 0:
                    hltb_max = 0
            except (ValueError, TypeError):
                pass
        # If hltb_max_param is "unlimited", leave hltb_max as None

        # If max is set but min is not, default min to 0
        # This ensures "under 10 hours" means "0-10 hours" not "any-10 hours"
        if hltb_max is not None and hltb_min is None:
            hltb_min = 0

        # Ensure max >= min (if both are set)
        if hltb_min is not None and hltb_max is not None:
            if hltb_max < hltb_min:
                hltb_max = hltb_min

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
            or dir_param != "asc"
            or (played_param and self.request.user.is_authenticated)
            or hltb_min is not None
            or hltb_max is not None
        )

        filters = {
            "q": q_param,
            "start": start_val,
            "end": end_val,
            "genres": genres_param.split(",") if genres_param else [],
            "platforms": platforms_param.split(",") if platforms_param else [],
            "series": series_param.split(",") if series_param else [],
            "played": (
                played_param
                if played_param and self.request.user.is_authenticated
                else ""
            ),
            "rank_display": "filtered" if has_any_filter else "alltime",
            "sort": sort_param,
            "sortDirection": dir_param,
            "hltb_mode": hltb_mode,
            "hltb_min": hltb_min,
            "hltb_max": hltb_max,
            # Keep legacy params for context
            "year": year_param,
            "decade": decade_param,
        }
        q = q_param
        played_cache_user_id = (
            self.request.user.id
            if played_param and self.request.user.is_authenticated
            else None
        )
        apply_played_filter = played_cache_user_id is not None

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
        # Always include full range 1970-present for year dropdowns
        context["year_range"] = range(1970, max_year + 1)
        # Convert highlight to int for comparison with game.id in template
        highlight_str = self.request.GET.get("highlight")
        context["highlight"] = (
            int(highlight_str) if highlight_str and highlight_str.isdigit() else None
        )
        context["is_filtered"] = True  # GameSearch is always filtered
        context["filter_title"] = _build_filter_title(
            filters, genres, platforms, min_year, max_year, series_list
        )
        # Genre subtitle not needed for single-select mode
        context["genre_subtitle"] = ""

        # Get year counts for heatmap grid based on current filters (excluding year)
        # This allows users to see which years have games given their other filters
        year_counts_cache_key = _build_filter_cache_key(
            "home_year_counts",
            filters,
            keys=["q", "genres", "platforms", "played"],
            user_id=played_cache_user_id,
        )
        year_counts = cache.get(year_counts_cache_key)
        if year_counts is None:
            base_qs = models.Game.objects.all()

            # Add played status annotation only when the played filter is active
            if apply_played_filter:
                base_qs = base_qs.with_played_status(self.request.user)

            # Apply search filter (same as get_queryset)
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

            # Apply played status filter
            base_qs = _apply_played_filter(base_qs, self.request.user, played_param)

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
            year_counts = [
                {"year": x, "count": year_count_map.get(x, 0)} for x in all_years
            ]
            cache.set(
                year_counts_cache_key, year_counts, config.CACHE_TIMEOUT_5_MINUTES
            )

        context["year_counts"] = year_counts

        # FACETED COUNTS FOR GENRES
        # Apply all filters EXCEPT genres (standard faceting for single-select)
        genre_counts_cache_key = _build_filter_cache_key(
            "home_genre_counts",
            filters,
            keys=["q", "start", "end", "platforms", "played"],
            user_id=played_cache_user_id,
        )
        genre_counts = cache.get(genre_counts_cache_key)
        if genre_counts is None:
            genre_facet_qs = models.Game.objects.all()
            if apply_played_filter:
                genre_facet_qs = genre_facet_qs.with_played_status(self.request.user)
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
                genre_facet_qs = utils.apply_platform_filter(
                    genre_facet_qs, platform_ids
                )
            genre_facet_qs = _apply_played_filter(
                genre_facet_qs, self.request.user, played_param
            )

            # Standard faceted counting (single-select mode)
            genre_counts = dict(
                genre_facet_qs.values("wikipedia_genres__id")
                .exclude(wikipedia_genres__id__isnull=True)
                .annotate(count=Count("id", distinct=True))
                .values_list("wikipedia_genres__id", "count")
            )
            cache.set(
                genre_counts_cache_key, genre_counts, config.CACHE_TIMEOUT_5_MINUTES
            )

        # FACETED COUNTS FOR PLATFORMS
        # Base: apply all filters EXCEPT platforms (q, year, genres)
        platform_counts_cache_key = _build_filter_cache_key(
            "home_platform_counts",
            filters,
            keys=["q", "start", "end", "genres", "played"],
            user_id=played_cache_user_id,
        )
        platform_counts = cache.get(platform_counts_cache_key)
        if platform_counts is None:
            platform_facet_qs = models.Game.objects.all()
            if apply_played_filter:
                platform_facet_qs = platform_facet_qs.with_played_status(
                    self.request.user
                )
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
            platform_facet_qs = _apply_played_filter(
                platform_facet_qs, self.request.user, played_param
            )

            # Count games per platform
            platform_counts = dict(
                platform_facet_qs.values("platforms__id")
                .exclude(platforms__id__isnull=True)
                .annotate(count=Count("id", distinct=True))
                .values_list("platforms__id", "count")
            )
            cache.set(
                platform_counts_cache_key,
                platform_counts,
                config.CACHE_TIMEOUT_5_MINUTES,
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

        # HLTB preset counts for filter (short/medium/long buckets)
        # Uses main_story_hours by default (same as client-side filter initial state)
        hltb_counts = models.Game.objects.filter(
            primary_hltb_game_data__main_story_hours__isnull=False
        ).aggregate(
            short=Count(
                "id",
                filter=Q(primary_hltb_game_data__main_story_hours__lt=10),
                distinct=True,
            ),
            medium=Count(
                "id",
                filter=Q(
                    primary_hltb_game_data__main_story_hours__gte=10,
                    primary_hltb_game_data__main_story_hours__lt=30,
                ),
                distinct=True,
            ),
            long=Count(
                "id",
                filter=Q(primary_hltb_game_data__main_story_hours__gte=30),
                distinct=True,
            ),
        )
        context["hltb_counts_json"] = hltb_counts

        # Rank distribution (10 bins of 100 ranks each)
        # Uses the filtered queryset to show distribution of current results
        rank_dist_cache_key = _build_filter_cache_key(
            "home_rank_dist",
            filters,
            keys=[
                "q",
                "start",
                "end",
                "genres",
                "platforms",
                "series",
                "played",
                "hltb_mode",
                "hltb_min",
                "hltb_max",
            ],
            user_id=played_cache_user_id,
        )
        cached_rank_data = cache.get(rank_dist_cache_key)
        if cached_rank_data is None:
            # Get global max rank for consistent bin structure
            max_rank = (
                models.Game.objects.filter(rank__isnull=False).aggregate(
                    max_rank=Max("rank")
                )["max_rank"]
                or 0
            )

            rank_bins = []
            if max_rank > 0:
                bin_count = config.RANK_DISTRIBUTION_BIN_COUNT
                bin_size = math.ceil(max_rank / bin_count)
                counts = [0] * bin_count

                # Get ranks from current queryset (respects filters)
                ranks = (
                    self.get_queryset()
                    .filter(rank__gte=1, rank__lte=max_rank)
                    .order_by()
                    .values_list("id", "rank")
                )
                for _, rank in ranks:
                    if rank:
                        idx = (rank - 1) // bin_size
                        if 0 <= idx < bin_count:
                            counts[idx] += 1

                for i in range(bin_count):
                    bin_start = i * bin_size + 1
                    bin_end = min((i + 1) * bin_size, max_rank)
                    rank_bins.append(
                        {"binStart": bin_start, "binEnd": bin_end, "count": counts[i]}
                    )

            cached_rank_data = {"rank_bins": rank_bins, "max_rank": max_rank}
            cache.set(
                rank_dist_cache_key, cached_rank_data, config.CACHE_TIMEOUT_5_MINUTES
            )
        else:
            rank_bins = cached_rank_data["rank_bins"]
            max_rank = cached_rank_data["max_rank"]

        context["rank_distribution"] = rank_bins
        context["max_rank"] = max_rank

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
            context["max_loaded"] = page_obj.end_index() >= page_obj.paginator.count

        # Enable client-side filtering for fast subsequent interactions
        context["enable_client_filtering"] = True

        # Add played/want-to-play game IDs for client-side rendering (cached per-user)
        if self.request.user.is_authenticated:
            context["played_game_ids"] = _get_played_game_ids(self.request.user)
            context["want_to_play_game_ids"] = _get_want_to_play_game_ids(
                self.request.user
            )

        # Hero section context (for homepage at /)
        hero_stats = _get_hero_stats()
        context["list_count"] = hero_stats["list_count"]
        context["publication_count"] = hero_stats["publication_count"]
        context["game_count"] = hero_stats["game_count"]
        metadata = models.SiteMetadata.get_instance()
        context["last_update"] = metadata.last_full_update

        return context


class DeveloperListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    """
    List view for developers with game counts and hierarchy support.

    Uses the unified Developer model with self-referential parent FK for hierarchy.
    Leverages cached hierarchy data for performance optimization.
    """

    model = models.Developer
    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 100
    paginate_orphans = 0
    htmx_partial_template = "developers/includes/_developer_list_content.html"

    def get_template_names(self):
        # Append mode for Load More - returns just rows
        if self.request.GET.get("append") == "true":
            return ["developers/includes/_developer_list_append.html"]
        return super().get_template_names()

    def get_paginate_by(self, queryset):
        # Disable Django's pagination when sorting by games, studios, or rank
        # We'll handle pagination manually after sorting with cached counts
        sort = self.request.GET.get("sort", "games")
        if sort in ("games", "studios", "rank"):
            return None
        return self.paginate_by

    def get_queryset(self):
        qs = (
            models.Developer.objects.annotate(
                games_count=Count("developed_games"),
            )
            .select_related("parent")
            .prefetch_related("subsidiaries")
            .distinct()
        )

        # Search filter
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Sort parameter - "games", "studios", "rank" sorts are handled in
        # get_context_data using cached hierarchy data
        sort = self.request.GET.get("sort", "games")
        direction = self.request.GET.get("dir", "asc")
        if sort == "name":
            if direction == "desc":
                qs = qs.order_by(Lower("name").desc())
            else:
                qs = qs.order_by(Lower("name"))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort = self.request.GET.get("sort", "games")
        direction = self.request.GET.get("dir", "asc")
        context["sort"] = sort

        # Get cached hierarchy data (precomputed counts, game IDs, etc.)
        from games.services.developer_service import get_developer_hierarchy

        hierarchy = get_developer_hierarchy()

        # Get developers list
        developers = list(context.get("developers", []))

        # Attach precomputed counts from cache (no recursive queries!)
        for dev in developers:
            dev.recursive_games_count = hierarchy["recursive_game_counts"].get(
                dev.id, 0
            )
            dev.recursive_studios_count = hierarchy["recursive_subsidiary_counts"].get(
                dev.id, 0
            )
            dev._cached_game_ids = hierarchy["recursive_game_ids"].get(dev.id, set())

        # Filter out developers with no games (direct or through subsidiaries)
        developers = [d for d in developers if d.recursive_games_count > 0]

        # Pre-attach root developers to avoid template N+1 queries
        root_ids = set(
            hierarchy["root_developer_id"].get(dev.id, dev.id) for dev in developers
        )
        root_devs = {d.id: d for d in models.Developer.objects.filter(id__in=root_ids)}
        for dev in developers:
            root_id = hierarchy["root_developer_id"].get(dev.id, dev.id)
            dev._prefetched_root = root_devs.get(root_id, dev)

        # Handle pagination and sorting
        if sort in ("games", "studios", "rank"):
            # For rank sorting, fetch top games using cached top_game_id
            if sort == "rank":
                top_game_ids = [
                    hierarchy["top_game_id"].get(dev.id)
                    for dev in developers
                    if hierarchy["top_game_id"].get(dev.id) is not None
                ]
                if top_game_ids:
                    top_games = {
                        g.id: g
                        for g in models.Game.objects.filter(id__in=top_game_ids)
                        .select_related("primary_igdb_game_data")
                        .only("id", "name", "slug", "rank", "primary_igdb_game_data")
                    }
                    for dev in developers:
                        top_game_id = hierarchy["top_game_id"].get(dev.id)
                        if top_game_id and top_game_id in top_games:
                            dev.top_game = top_games[top_game_id]

            # Sort by cached counts (with direction support)
            is_desc = direction == "desc"
            if sort == "games":
                developers.sort(
                    key=lambda d: (
                        (
                            -d.recursive_games_count
                            if not is_desc
                            else d.recursive_games_count
                        ),
                        d.name.lower(),
                    )
                )
            elif sort == "studios":
                developers.sort(
                    key=lambda d: (
                        (
                            -d.recursive_studios_count
                            if not is_desc
                            else d.recursive_studios_count
                        ),
                        d.name.lower(),
                    )
                )
            else:  # rank
                developers.sort(
                    key=lambda d: (
                        getattr(d, "top_game", None) is None,  # No game = always last
                        (
                            (
                                getattr(getattr(d, "top_game", None), "rank", 9999)
                                or 9999
                            )
                            if not is_desc
                            else -(
                                getattr(getattr(d, "top_game", None), "rank", 9999)
                                or 9999
                            )
                        ),
                        d.name.lower(),
                    )
                )

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
            # Use Django's built-in pagination
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

        # Fetch top game for each developer on the current page (if not already set)
        page_developers = context.get("developers", [])
        devs_needing_top_game = [
            dev for dev in page_developers if not hasattr(dev, "top_game")
        ]

        if devs_needing_top_game:
            top_game_ids = [
                hierarchy["top_game_id"].get(dev.id)
                for dev in devs_needing_top_game
                if hierarchy["top_game_id"].get(dev.id) is not None
            ]
            if top_game_ids:
                top_games = {
                    g.id: g
                    for g in models.Game.objects.filter(id__in=top_game_ids)
                    .select_related("primary_igdb_game_data")
                    .only("id", "name", "slug", "rank", "primary_igdb_game_data")
                }
                for dev in devs_needing_top_game:
                    top_game_id = hierarchy["top_game_id"].get(dev.id)
                    if top_game_id and top_game_id in top_games:
                        dev.top_game = top_games[top_game_id]

        return context


# Legacy alias for backward compatibility
StudioListView = DeveloperListView


class DeveloperDetailView(DetailView):
    """
    Detail view for a developer showing all games and subsidiary hierarchy.

    Uses the unified Developer model with self-referential parent FK.
    Caches expensive context computation for 24 hours.
    """

    CACHE_SCHEMA_VERSION = 2

    model = models.Developer
    template_name = "developers/developer_detail.html"
    context_object_name = "developer"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        # Prefetch subsidiaries and games with optimized queryset
        games_queryset = models.Game.objects.prefetch_related(
            "developers",
            "developers__parent",
            "platforms",
            "wikipedia_genres",
        ).order_by("rank")

        return models.Developer.objects.prefetch_related(
            Prefetch(
                "subsidiaries",
                queryset=models.Developer.objects.order_by("name"),
            ),
            Prefetch("developed_games", queryset=games_queryset),
        )

    def _get_cached_context(self, developer):
        """Get cached context for this developer, or None if not cached."""
        from django.core.cache import cache

        from games import config

        cache_key = f"{config.CACHE_VERSION}:developer_detail:{developer.id}"
        cached = cache.get(cache_key)
        if isinstance(cached, dict):
            cached_schema = cached.get("cache_schema_version")
            if cached_schema is not None and cached_schema != self.CACHE_SCHEMA_VERSION:
                cache.delete(cache_key)
                return None
            if cached_schema == self.CACHE_SCHEMA_VERSION:
                return cached
            # Drop legacy cached payloads that stored model objects.
            if "all_games" in cached and "subsidiaries_with_games" in cached:
                cache.delete(cache_key)
                return None
        return cached

    def _set_cached_context(self, developer, context_data):
        """Cache the expensive context data for this developer."""
        from django.core.cache import cache

        from games import config

        cache_key = f"{config.CACHE_VERSION}:developer_detail:{developer.id}"
        cache.set(cache_key, context_data, config.CACHE_TIMEOUT_24_HOURS)

    @staticmethod
    def _serialize_developer(developer):
        return {
            "id": developer.id,
            "name": developer.name,
            "igdb_url": developer.igdb_url,
            "slug": developer.slug,
        }

    def _serialize_subsidiaries(self, devs_data):
        serialized = []
        for dev_data in devs_data:
            serialized.append(
                {
                    "developer_id": dev_data["developer"].id,
                    "developer": self._serialize_developer(dev_data["developer"]),
                    "game_ids": [g.id for g in dev_data["games"]],
                    "games_count": dev_data["games_count"],
                    "sub_developers": self._serialize_subsidiaries(
                        dev_data["sub_developers"]
                    ),
                    "total_games_count": dev_data["total_games_count"],
                    "total_developers_count": dev_data["total_developers_count"],
                }
            )
        return serialized

    @staticmethod
    def _collect_developer_ids(serialized):
        developer_ids = set()
        stack = list(serialized or [])
        while stack:
            dev_data = stack.pop()
            if not isinstance(dev_data, dict):
                continue
            dev_id = dev_data.get("developer_id")
            if dev_id is None:
                dev = dev_data.get("developer")
                if isinstance(dev, dict):
                    dev_id = dev.get("id")
                else:
                    dev_id = getattr(dev, "id", None)
            if dev_id is not None:
                developer_ids.add(dev_id)
            stack.extend(dev_data.get("sub_developers", []) or [])
        return developer_ids

    def _hydrate_subsidiaries(self, serialized, games_by_id, developers_by_id):
        hydrated = []
        for dev_data in serialized:
            game_ids = dev_data.get("game_ids", [])
            games = [games_by_id[gid] for gid in game_ids if gid in games_by_id]
            dev_id = dev_data.get("developer_id")
            dev = dev_data.get("developer")
            if dev_id is None:
                if isinstance(dev, dict):
                    dev_id = dev.get("id")
                else:
                    dev_id = getattr(dev, "id", None)
            dev_obj = developers_by_id.get(dev_id) if dev_id is not None else None
            if dev_obj is None:
                dev_obj = dev
            sub_devs = self._hydrate_subsidiaries(
                dev_data.get("sub_developers", []), games_by_id, developers_by_id
            )
            hydrated.append(
                {
                    "developer": dev_obj,
                    "games": games,
                    "games_count": dev_data.get("games_count", len(games)),
                    "sub_developers": sub_devs,
                    "total_games_count": dev_data.get("total_games_count", len(games)),
                    "total_developers_count": dev_data.get(
                        "total_developers_count", len(sub_devs)
                    ),
                }
            )
        return hydrated

    @staticmethod
    def _fetch_games_by_ids(game_ids):
        from games.models import Game

        if not game_ids:
            return [], {}

        games = list(
            Game.objects.filter(id__in=game_ids)
            .select_related("primary_hltb_game_data")
            .prefetch_related("developers", "platforms", "wikipedia_genres")
        )
        games_by_id = {game.id: game for game in games}
        ordered_games = [games_by_id[gid] for gid in game_ids if gid in games_by_id]
        return ordered_games, games_by_id

    def flatten_developers(
        self, devs_data, parent_id=None, level=0, continues_at_levels=None
    ):
        """Flatten recursive developer structure for checkbox tree.

        Tracks tree structure for proper tree line rendering:
        - is_last_child: whether item is last sibling (vertical line stops at 50%)
        - continues_at_levels: ancestor levels with more siblings (need vertical lines)
        """
        if continues_at_levels is None:
            continues_at_levels = []

        flat = []
        total = len(devs_data)
        for idx, dev_data in enumerate(devs_data):
            is_last = idx == total - 1
            child_ids = [s["developer"].id for s in dev_data["sub_developers"]]

            flat.append(
                {
                    "id": dev_data["developer"].id,
                    "name": dev_data["developer"].name,
                    "igdb_url": dev_data["developer"].igdb_url,
                    "game_ids": [g.id for g in dev_data["games"]],
                    "total_game_count": dev_data[
                        "total_games_count"
                    ],  # Includes descendants
                    "parent_id": parent_id,
                    "level": level,
                    "child_ids": child_ids,
                    "is_last_child": is_last,
                    "continues_at_levels": list(continues_at_levels),
                }
            )

            # For children: if this item is NOT the last, add current level to continues
            child_continues = continues_at_levels + ([level] if not is_last else [])

            # Recursively flatten sub-developers
            flat.extend(
                self.flatten_developers(
                    dev_data["sub_developers"],
                    parent_id=dev_data["developer"].id,
                    level=level + 1,
                    continues_at_levels=child_continues,
                )
            )
        return flat

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        developer = context["developer"]

        # Try to get cached context first
        cached = self._get_cached_context(developer)
        if cached is not None:
            if (
                isinstance(cached, dict)
                and cached.get("cache_schema_version") == self.CACHE_SCHEMA_VERSION
            ):
                all_game_ids = cached.get("all_game_ids", [])
                all_games, games_by_id = self._fetch_games_by_ids(all_game_ids)
                developer_ids = self._collect_developer_ids(
                    cached.get("subsidiaries_serialized", [])
                )
                developers_by_id = models.Developer.objects.in_bulk(developer_ids)
                root_game_ids = cached.get("root_game_ids", [])
                root_games = [
                    games_by_id[gid] for gid in root_game_ids if gid in games_by_id
                ]
                subsidiaries_with_games = self._hydrate_subsidiaries(
                    cached.get("subsidiaries_serialized", []),
                    games_by_id,
                    developers_by_id,
                )

                context.update(
                    {
                        "subsidiaries_with_games": subsidiaries_with_games,
                        "root_games": root_games,
                        "total_games": cached.get("total_games", 0),
                        "subsidiaries_count": cached.get("subsidiaries_count", 0),
                        "developers_flat": cached.get("developers_flat", []),
                        "all_games": all_games,
                        "developer_game_map_json": cached.get(
                            "developer_game_map_json", "{}"
                        ),
                        "developer_child_map_json": cached.get(
                            "developer_child_map_json", "{}"
                        ),
                        "game_rank_map_json": cached.get("game_rank_map_json", "{}"),
                        "game_data_map_json": cached.get("game_data_map_json", "{}"),
                        "game_developer_map": cached.get("game_developer_map", {}),
                        "rank_distribution": cached.get("rank_distribution", []),
                        "max_rank": cached.get("max_rank", 0),
                    }
                )
            else:
                context.update(cached)
            return context

        # Recursively gather subsidiaries with nested structure
        def gather_subsidiaries(parent_dev, visited=None):
            """Recursively gather subsidiaries and their games."""
            if visited is None:
                visited = set()

            if parent_dev.id in visited:
                return []
            visited.add(parent_dev.id)

            devs_data = []
            for sub_dev in parent_dev.subsidiaries.all():
                dev_games = list(sub_dev.developed_games.all())

                # Recursively get sub-subsidiaries
                sub_devs = gather_subsidiaries(sub_dev, visited)

                # Filter out games that belong to sub-developers
                # (show at most specific level)
                if sub_devs:

                    def collect_sub_game_ids(devs):
                        """Recursively collect all game IDs from sub-developers."""
                        ids = set()
                        for d in devs:
                            ids.update(g.id for g in d["games"])
                            ids.update(collect_sub_game_ids(d["sub_developers"]))
                        return ids

                    sub_game_ids = collect_sub_game_ids(sub_devs)
                    dev_games = [g for g in dev_games if g.id not in sub_game_ids]

                # Only include developers that have games OR sub-developers
                if dev_games or sub_devs:
                    dev_games.sort(key=lambda g: (g.rank or 999999))

                    # Calculate total unique games including all nested developers
                    def calc_total_games(games, sub_devs_list):
                        """Count unique games to prevent double-counting."""
                        game_ids = {g.id for g in games}
                        for sub in sub_devs_list:
                            sub_ids = calc_unique_game_ids(
                                sub["games"], sub["sub_developers"]
                            )
                            game_ids.update(sub_ids)
                        return len(game_ids)

                    def calc_unique_game_ids(games, sub_devs_list):
                        """Recursively collect unique game IDs."""
                        game_ids = {g.id for g in games}
                        for sub in sub_devs_list:
                            game_ids.update(
                                calc_unique_game_ids(
                                    sub["games"], sub["sub_developers"]
                                )
                            )
                        return game_ids

                    # Calculate total nested developers
                    def calc_total_devs(sub_devs_list):
                        total = len(sub_devs_list)
                        for sub in sub_devs_list:
                            total += calc_total_devs(sub["sub_developers"])
                        return total

                    devs_data.append(
                        {
                            "developer": sub_dev,
                            "games": dev_games,
                            "games_count": len(dev_games),
                            "sub_developers": sub_devs,
                            "total_games_count": calc_total_games(dev_games, sub_devs),
                            "total_developers_count": calc_total_devs(sub_devs),
                        }
                    )

            # Sort by total_games_count descending at each level
            devs_data.sort(key=lambda d: d["total_games_count"], reverse=True)
            return devs_data

        # Get root developer's direct games
        root_games = list(developer.developed_games.all())

        # Get all subsidiaries recursively
        subsidiaries_with_games = gather_subsidiaries(developer)

        # Filter out games from root that belong to subsidiaries
        if subsidiaries_with_games:

            def collect_all_sub_game_ids(devs):
                """Recursively collect all game IDs from sub-developers."""
                ids = set()
                for d in devs:
                    ids.update(g.id for g in d["games"])
                    ids.update(collect_all_sub_game_ids(d["sub_developers"]))
                return ids

            sub_game_ids = collect_all_sub_game_ids(subsidiaries_with_games)
            root_games = [g for g in root_games if g.id not in sub_game_ids]

        root_games.sort(key=lambda g: (g.rank or 999999))

        # Count unique games across all developers
        def collect_unique_game_ids(devs):
            """Recursively collect unique game IDs across all developers."""
            game_ids = set()
            for dev_data in devs:
                game_ids.update(g.id for g in dev_data["games"])
                game_ids.update(collect_unique_game_ids(dev_data["sub_developers"]))
            return game_ids

        total_games = len(collect_unique_game_ids(subsidiaries_with_games)) + len(
            root_games
        )

        # Count unique developers (flatten the hierarchy)
        def count_devs(devs):
            total = len(devs)
            for dev_data in devs:
                total += count_devs(dev_data["sub_developers"])
            return total

        subsidiaries_count = count_devs(subsidiaries_with_games)

        context["subsidiaries_with_games"] = subsidiaries_with_games
        context["root_games"] = root_games
        context["total_games"] = total_games
        # Include root developer in count (+1) to match filter selection
        context["subsidiaries_count"] = subsidiaries_count + 1

        # Add flattened developer data for filter UI
        devs_flat = self.flatten_developers(subsidiaries_with_games)

        # Prepend root developer as root node for the checkbox tree
        all_top_level_dev_ids = [s["id"] for s in devs_flat if s["level"] == 0]
        all_game_ids = collect_unique_game_ids(subsidiaries_with_games)
        all_game_ids.update(g.id for g in root_games)
        # Root entry only stores ROOT'S DIRECT GAMES (not all games)
        # This ensures proper counting when all children are selected
        root_game_ids = [g.id for g in root_games]
        root_entry = {
            "id": 0,  # Special ID for root (DB IDs start at 1)
            "name": developer.name,
            "game_ids": root_game_ids,  # Only root's direct games
            "total_game_count": len(all_game_ids),  # Total including all descendants
            "level": 0,
            "child_ids": all_top_level_dev_ids,
        }

        # Increment all developer levels by 1 (root is now level 0)
        for dev in devs_flat:
            dev["level"] += 1

        # Insert root at the beginning
        devs_flat.insert(0, root_entry)

        context["developers_flat"] = devs_flat

        # Collect all unique games for filter view
        all_games = list(
            models.Game.objects.filter(id__in=all_game_ids)
            .select_related("primary_hltb_game_data")
            .prefetch_related("developers", "platforms", "wikipedia_genres")
            .order_by("rank")
        )
        context["all_games"] = all_games

        # Build developer -> game IDs mapping for Alpine.js
        # Each developer maps to ONLY its direct games (not descendants)
        # JavaScript handles hierarchical selection by checking/unchecking children
        dev_game_map = {}
        for dev in devs_flat:
            dev_game_map[dev["id"]] = dev["game_ids"]

        # Build developer -> child IDs mapping for Alpine.js
        dev_child_map = {d["id"]: d["child_ids"] for d in devs_flat}

        # Serialize to JSON for Alpine.js
        import json
        from django.core.serializers.json import DjangoJSONEncoder

        context["developer_game_map_json"] = json.dumps(
            dev_game_map, cls=DjangoJSONEncoder
        )
        context["developer_child_map_json"] = json.dumps(
            dev_child_map, cls=DjangoJSONEncoder
        )

        # Game rank map for JavaScript to calculate filtered rank distribution
        game_rank_map = {game.id: game.rank for game in all_games if game.rank}
        context["game_rank_map_json"] = json.dumps(game_rank_map, cls=DjangoJSONEncoder)

        # Game data map with playtime for sorting
        game_data_map = {}
        for game in all_games:
            game_data_map[game.id] = {
                "pt": (
                    game.primary_hltb_game_data.main_story_hours
                    if game.primary_hltb_game_data
                    else None
                )
            }
        context["game_data_map_json"] = json.dumps(game_data_map, cls=DjangoJSONEncoder)

        # Build game -> developer IDs map for anchor links
        # This maps each game_id to the list of developer_ids that have it
        game_developer_map = {}
        for dev_id, game_ids in dev_game_map.items():
            for game_id in game_ids:
                if game_id not in game_developer_map:
                    game_developer_map[game_id] = []
                game_developer_map[game_id].append(dev_id)
        context["game_developer_map"] = game_developer_map

        # Rank distribution for visualization - uses global max rank for consistency
        # with the games list page (same bin structure across all pages)
        max_rank = (
            models.Game.objects.filter(rank__isnull=False).aggregate(
                max_rank=Max("rank")
            )["max_rank"]
            or 0
        )

        rank_bins = []
        if max_rank > 0:
            bin_count = config.RANK_DISTRIBUTION_BIN_COUNT
            bin_size = math.ceil(max_rank / bin_count)
            for i in range(bin_count):
                bin_start = i * bin_size + 1
                bin_end = min((i + 1) * bin_size, max_rank)
                count = sum(
                    1 for g in all_games if g.rank and bin_start <= g.rank <= bin_end
                )
                rank_bins.append(
                    {"binStart": bin_start, "binEnd": bin_end, "count": count}
                )

        context["rank_distribution"] = rank_bins
        context["max_rank"] = max_rank

        # Cache the expensive context data (excluding objects that can't be cached)
        # We cache everything that's JSON-serializable or simple Python objects
        serialized_subsidiaries = self._serialize_subsidiaries(subsidiaries_with_games)
        all_game_ids_ordered = [game.id for game in all_games]
        cacheable_context = {
            "cache_schema_version": self.CACHE_SCHEMA_VERSION,
            "subsidiaries_serialized": serialized_subsidiaries,
            "root_game_ids": root_game_ids,
            "all_game_ids": all_game_ids_ordered,
            "total_games": total_games,
            "subsidiaries_count": context["subsidiaries_count"],
            "developers_flat": devs_flat,
            "developer_game_map_json": context["developer_game_map_json"],
            "developer_child_map_json": context["developer_child_map_json"],
            "game_rank_map_json": context["game_rank_map_json"],
            "game_data_map_json": context["game_data_map_json"],
            "game_developer_map": game_developer_map,
            "rank_distribution": rank_bins,
            "max_rank": max_rank,
        }
        self._set_cached_context(developer, cacheable_context)

        return context


class DeveloperRedirectView(View):
    """
    Redirects developer by ID to the root developer's detail page.
    Handles legacy /developer-alias/:id/ URLs.
    """

    def get(self, request, id):
        developer = get_object_or_404(models.Developer, id=id)
        root = developer.root_developer
        return redirect("developer-detail", slug=root.slug, permanent=True)


class ListListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    """
    Source Lists page - displays lists grouped by publication.

    Publications are paginated (30 per page) and can be sorted by:
    - importance (default): weighted score based on list type counts
    - alpha: alphabetical by name

    Lists within each publication are sorted by type importance
    (All-time > Decade > Misc > EOY) then by year descending.
    """

    model = models.Publication
    template_name = "lists/list_list.html"
    context_object_name = "publication_groups"
    paginate_by = 50
    paginate_orphans = 0
    htmx_partial_template = "lists/includes/_list_list_content.html"

    def get_template_names(self):
        # Append mode for Load More (publication grouping only)
        if self.request.GET.get("append") == "true":
            group_by = self.request.GET.get("group_by", "publication")
            if group_by == "publication":
                return ["lists/includes/_list_list_append.html"]
        return super().get_template_names()

    def _get_list_filters(self):
        """Parse and validate filter parameters from request."""
        year_value = self.request.GET.get("year")
        type_slug = self.request.GET.get("type")
        search_query = self.request.GET.get("q", "").strip()
        group_by = self.request.GET.get("group_by", "publication").strip().lower()

        try:
            year_value = int(year_value) if year_value else None
        except (ValueError, TypeError):
            year_value = None

        type_code = constants.LIST_TYPE_CODES.get(type_slug) if type_slug else None

        if group_by not in ("publication", "type"):
            group_by = "publication"

        return year_value, type_slug, type_code, search_query, group_by

    def _get_filtered_list_queryset(self, year_value, type_code):
        """Build base list queryset with filters applied."""
        qs = models.List.objects.all()
        if year_value:
            qs = qs.filter(year=year_value)
        if type_code:
            qs = qs.filter(type=type_code)
        return qs

    def _build_type_group_context(
        self,
        context,
        year_value,
        type_slug,
        type_code,
        search_query,
        sort,
        sort_direction,
        group_by,
    ):
        """Build context for type-grouped view.

        Groups lists by type (All-time, Decade, Misc, EOY), showing a flat
        list of all lists within each type section.
        """
        type_groups = []
        grand_total_lists = 0

        for type_code_iter in constants.LIST_TYPE_IMPORTANCE_ORDER:
            type_label = constants.get_list_type_label(type_code_iter)

            # Skip if filtering by type and this isn't the selected type
            if type_code and type_code != type_code_iter:
                continue

            # Build list queryset for this type
            lists_qs = models.List.objects.filter(type=type_code_iter)
            if year_value:
                lists_qs = lists_qs.filter(year=year_value)
            if search_query:
                lists_qs = lists_qs.filter(publisher__name__icontains=search_query)

            # Select related publisher for efficient access
            lists_qs = lists_qs.select_related("publisher")

            total_list_count = lists_qs.count()
            if total_list_count == 0:
                continue

            grand_total_lists += total_list_count

            # Apply sorting
            if sort == "alpha":
                # Sort by publication name, then list name
                if sort_direction == "asc":
                    lists_qs = lists_qs.order_by(
                        Lower("publisher__name"), Lower("name")
                    )
                else:
                    lists_qs = lists_qs.order_by(
                        Lower("publisher__name").desc(), Lower("name").desc()
                    )
            else:  # "release" - sort by year
                if sort_direction == "desc":
                    lists_qs = lists_qs.order_by(
                        "-year", Lower("publisher__name"), Lower("name")
                    )
                else:
                    lists_qs = lists_qs.order_by(
                        "year", Lower("publisher__name"), Lower("name")
                    )

            # Load all lists for this type
            lists = list(lists_qs)

            type_groups.append(
                {
                    "type_code": type_code_iter,
                    "type_label": type_label,
                    "lists": lists,
                    "total_count": total_list_count,
                }
            )

        # --- FACETED COUNTS FOR FILTERS ---
        # Year counts: filtered by type only (NOT year)
        year_base_qs = models.List.objects.all()
        if type_code:
            year_base_qs = year_base_qs.filter(type=type_code)

        list_year_counts = list(
            year_base_qs.values("year").annotate(count=Count("id")).order_by("-year")
        )

        year_str = str(year_value) if year_value else None
        filtered_years = [
            y for y in list_year_counts if y["count"] > 0 or str(y["year"]) == year_str
        ]

        # Type counts: filtered by year only (NOT type)
        type_base_qs = models.List.objects.all()
        if year_value:
            type_base_qs = type_base_qs.filter(year=year_value)

        type_counts_raw = list(
            type_base_qs.values("type").annotate(count=Count("id")).order_by("type")
        )

        filtered_types = []
        for t in type_counts_raw:
            t["slug"] = constants.LIST_TYPE_SLUGS.get(t["type"], t["type"])
            if t["count"] > 0 or t["type"] == type_code:
                filtered_types.append(t)

        filtered_types.sort(
            key=lambda t: constants.LIST_TYPE_PRIORITY.get(t["type"], 99)
        )

        # Build context
        context["type_groups"] = type_groups
        context["meta"] = {"lists": {"years": filtered_years}}
        context["list_types"] = constants.LIST_TYPES
        context["type_counts"] = filtered_types
        context["filters"] = {
            "year": str(year_value) if year_value else None,
            "type": type_slug,
            "q": search_query,
        }
        context["sort"] = sort
        context["sort_direction"] = sort_direction
        context["group_by"] = group_by
        # Grand total: all lists (filtered by year/search but NOT type)
        grand_total_qs = models.List.objects.all()
        if year_value:
            grand_total_qs = grand_total_qs.filter(year=year_value)
        if search_query:
            grand_total_qs = grand_total_qs.filter(
                publisher__name__icontains=search_query
            )
        context["grand_total_list_count"] = grand_total_qs.count()

        # Sort options for type grouping mode
        context["sort_options"] = [
            ("release", "Year"),
            ("alpha", "Alphabetical"),
        ]

        # Total lists count (filtered by type)
        context["total_list_count"] = grand_total_lists

        return context

    def get_queryset(self):
        """Get publications with list counts, filtered and sorted."""
        year_value, type_slug, type_code, search_query, group_by = (
            self._get_list_filters()
        )

        # Store group_by for use in get_context_data
        self.group_by = group_by

        # For type grouping, we handle data in get_context_data instead
        if group_by == "type":
            return models.Publication.objects.none()

        raw_sort = self.request.GET.get("sort", "")
        sort = raw_sort if raw_sort in ("importance", "alpha") else "importance"
        # Default direction depends on sort type: desc for importance, asc for alpha
        default_dir = "asc" if sort == "alpha" else "desc"
        sort_direction = self.request.GET.get("dir", default_dir)

        # Base list queryset for filtering
        list_filter = Q()
        if year_value:
            list_filter &= Q(lists__year=year_value)
        if type_code:
            list_filter &= Q(lists__type=type_code)

        # Annotate publications with list counts by type
        # Only count lists that match the current filters
        count_filter = Q()
        if year_value:
            count_filter &= Q(year=year_value)
        if type_code:
            count_filter &= Q(type=type_code)

        # Build filter conditions for badge counts
        # Year filter applies to all counts
        # Type filter: only show count for matching type (others become 0)
        year_filter = Q(lists__year=year_value) if year_value else Q()

        qs = models.Publication.objects.annotate(
            # Filtered counts for display - responsive to both year and type filters
            alltime_count=Count(
                "lists",
                filter=Q(lists__type=constants.LIST_ALLTIME)
                & year_filter
                & (
                    Q()
                    if not type_code or type_code == constants.LIST_ALLTIME
                    else Q(pk__in=[])
                ),
            ),
            decade_count=Count(
                "lists",
                filter=Q(lists__type=constants.LIST_DECADE)
                & year_filter
                & (
                    Q()
                    if not type_code or type_code == constants.LIST_DECADE
                    else Q(pk__in=[])
                ),
            ),
            misc_count=Count(
                "lists",
                filter=Q(lists__type=constants.LIST_MISC)
                & year_filter
                & (
                    Q()
                    if not type_code or type_code == constants.LIST_MISC
                    else Q(pk__in=[])
                ),
            ),
            eoy_count=Count(
                "lists",
                filter=Q(lists__type=constants.LIST_EOY)
                & year_filter
                & (
                    Q()
                    if not type_code or type_code == constants.LIST_EOY
                    else Q(pk__in=[])
                ),
            ),
            # Total filtered count
            total_count=Count("lists", filter=list_filter if list_filter else Q()),
            # Importance score for sorting
            # When type filter is applied: sort by count of that type
            # When no type filter: weighted score
            # (All-time: 1000, Decade: 100, Misc: 10, EOY: 1)
            importance_score=(
                Count("lists", filter=list_filter if list_filter else Q())
                if type_code
                else (
                    Count(
                        "lists",
                        filter=Q(lists__type=constants.LIST_ALLTIME) & year_filter,
                    )
                    * 1000
                    + Count(
                        "lists",
                        filter=Q(lists__type=constants.LIST_DECADE) & year_filter,
                    )
                    * 100
                    + Count(
                        "lists",
                        filter=Q(lists__type=constants.LIST_MISC) & year_filter,
                    )
                    * 10
                    + Count(
                        "lists",
                        filter=Q(lists__type=constants.LIST_EOY) & year_filter,
                    )
                )
            ),
        )

        # Only include publications with matching lists
        qs = qs.filter(total_count__gt=0)

        # Apply search filter if provided
        if search_query:
            qs = qs.filter(name__icontains=search_query)

        # Sort by importance or alphabetically, respecting direction
        if sort == "alpha":
            if sort_direction == "asc":
                qs = qs.order_by(Lower("name"))
            else:
                qs = qs.order_by(Lower("name").desc())
        else:
            # Sort by importance score, then alphabetically as tiebreaker
            if sort_direction == "asc":
                qs = qs.order_by("importance_score", Lower("name"))
            else:
                qs = qs.order_by("-importance_score", Lower("name"))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year_value, type_slug, type_code, search_query, group_by = (
            self._get_list_filters()
        )

        # Default sort depends on group_by mode
        # Normalize sort to valid options for the current mode to handle
        # stale values when the type filter switches the grouping mode
        raw_sort = self.request.GET.get("sort", "")
        if group_by == "type":
            sort = raw_sort if raw_sort in ("release", "alpha") else "release"
            default_dir = "desc" if sort == "release" else "asc"
        else:
            sort = raw_sort if raw_sort in ("importance", "alpha") else "importance"
            default_dir = "asc" if sort == "alpha" else "desc"

        sort_direction = self.request.GET.get("dir", default_dir)

        # Handle type grouping mode
        if group_by == "type":
            return self._build_type_group_context(
                context,
                year_value,
                type_slug,
                type_code,
                search_query,
                sort,
                sort_direction,
                group_by,
            )

        # Build the publication groups with their lists
        publication_groups = []
        publications = context.get("publication_groups", [])

        # Build type priority ordering for lists
        type_priority = Case(
            *[
                When(type=code, then=Value(idx))
                for idx, code in enumerate(constants.LIST_TYPE_IMPORTANCE_ORDER)
            ],
            default=Value(99),
            output_field=IntegerField(),
        )

        for pub in publications:
            # Get lists for this publication, filtered and sorted
            lists_qs = models.List.objects.filter(publisher=pub)
            if year_value:
                lists_qs = lists_qs.filter(year=year_value)
            if type_code:
                lists_qs = lists_qs.filter(type=type_code)

            # Sort by type importance, then year descending
            lists_qs = lists_qs.annotate(type_priority=type_priority).order_by(
                "type_priority", "-year", "name"
            )

            publication_groups.append(
                {
                    "publication": pub,
                    "alltime_count": pub.alltime_count,
                    "decade_count": pub.decade_count,
                    "misc_count": pub.misc_count,
                    "eoy_count": pub.eoy_count,
                    "total_count": pub.total_count,
                    "lists": list(lists_qs),
                }
            )

        context["publication_groups"] = publication_groups

        # --- FACETED COUNTS FOR FILTERS ---
        # Year counts: filtered by type only (NOT year)
        year_base_qs = models.List.objects.all()
        if type_code:
            year_base_qs = year_base_qs.filter(type=type_code)

        list_year_counts = list(
            year_base_qs.values("year").annotate(count=Count("id")).order_by("-year")
        )

        # Filter years: include count > 0 OR currently selected
        year_str = str(year_value) if year_value else None
        filtered_years = [
            y for y in list_year_counts if y["count"] > 0 or str(y["year"]) == year_str
        ]

        # Type counts: filtered by year only (NOT type)
        type_base_qs = models.List.objects.all()
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

        # Sort by importance priority (All-time > Decade > Misc > EOY)
        filtered_types.sort(
            key=lambda t: constants.LIST_TYPE_PRIORITY.get(t["type"], 99)
        )

        # Build context
        context["meta"] = {"lists": {"years": filtered_years}}
        context["list_types"] = constants.LIST_TYPES
        context["type_counts"] = filtered_types
        context["filters"] = {
            "year": str(year_value) if year_value else None,
            "type": type_slug,  # Keep as slug for template comparison
            "q": search_query,
        }
        context["sort"] = sort
        context["sort_direction"] = sort_direction
        context["group_by"] = group_by

        # Sort options for publication grouping mode
        context["sort_options"] = [
            ("importance", "# Lists"),
            ("alpha", "Alphabetical"),
        ]

        # Total list count for display (loaded publications only)
        total_lists = sum(g["total_count"] for g in publication_groups)
        context["total_list_count"] = total_lists

        # Grand total list count across ALL publications (for "X of Y lists")
        grand_total_qs = models.List.objects.all()
        if year_value:
            grand_total_qs = grand_total_qs.filter(year=year_value)
        if type_code:
            grand_total_qs = grand_total_qs.filter(type=type_code)
        context["grand_total_list_count"] = grand_total_qs.count()

        # Load More context (paginating publications)
        page_obj = context.get("page_obj")
        if page_obj:
            context["has_more"] = page_obj.has_next()
            context["next_page"] = (
                page_obj.next_page_number() if page_obj.has_next() else None
            )
            context["total_count"] = page_obj.paginator.count  # Total publications
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


class NewsListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    """News list showing all active posts with pagination."""

    model = models.Post
    template_name = "posts/post_list.html"
    context_object_name = "posts"
    paginate_by = 10
    paginate_orphans = 0
    htmx_partial_template = "posts/includes/_post_list_content.html"

    def get_queryset(self):
        return models.Post.objects.filter(active=True).order_by("-date")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pagination context
        page_obj = context.get("page_obj")
        if page_obj:
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()

        return context


class ArticleListView(RobustPaginationMixin, HTMXPartialMixin, ListView):
    """Blog article list with pagination."""

    model = models.Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 10
    paginate_orphans = 0
    htmx_partial_template = "articles/includes/_article_list_content.html"

    def get_queryset(self):
        return (
            models.Article.objects.filter(status=models.Article.Status.PUBLISHED)
            .select_related("author")
            .order_by("-published_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_obj = context.get("page_obj")
        if page_obj:
            context["total_count"] = page_obj.paginator.count
            context["loaded_count"] = page_obj.end_index()
        return context


class ArticleDetailView(DetailView):
    """Individual article detail page."""

    model = models.Article
    template_name = "articles/article_detail.html"
    context_object_name = "article"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        qs = models.Article.objects.select_related("author")
        # Staff can preview drafts
        if self.request.user.is_staff:
            return qs
        return qs.filter(status=models.Article.Status.PUBLISHED)


class NotFoundView(TemplateView):
    """
    Custom 404 page with auto-redirect.
    """

    template_name = "404.html"

    def dispatch(self, request, *args, **kwargs):
        # Handle all HTTP methods (GET, POST, etc.) the same way
        context = self.get_context_data(**kwargs)
        response = self.render_to_response(context)
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

    Blocks aggressive/low-value crawlers and disallows expensive filtered
    query patterns that can overwhelm the server.
    """
    content = """\
# Aggressive/low-value crawlers - block entirely
User-agent: AhrefsBot
Disallow: /

User-agent: SemrushBot
Disallow: /

User-agent: MJ12bot
Disallow: /

User-agent: DotBot
Disallow: /

User-agent: BLEXBot
Disallow: /

User-agent: PetalBot
Disallow: /

User-agent: BaiduSpider
Disallow: /

# All other crawlers
User-agent: *
Allow: /
Crawl-delay: 10
Disallow: /admin/
Disallow: /import/
Disallow: /api/
Disallow: /*?*start=
Disallow: /*?*end=
Disallow: /*?*highlight=
Disallow: /*?*page=

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

        try:
            # Get all counts in a single aggregation query (optimized)
            total_games = models.Game.objects.count()

            # Count metadata records (not games)
            # This persists when games are deleted (metadata is orphaned)
            total_igdb_metadata = models.IGDBGameData.objects.count()
            orphaned_igdb = models.IGDBGameData.objects.filter(
                game__isnull=True
            ).count()
            connected_igdb = total_igdb_metadata - orphaned_igdb

            total_wikipedia_metadata = models.WikipediaGameData.objects.count()
            orphaned_wikipedia = models.WikipediaGameData.objects.filter(
                game__isnull=True
            ).count()
            connected_wikipedia = total_wikipedia_metadata - orphaned_wikipedia

            total_hltb_metadata = models.HLTBGameData.objects.count()
            orphaned_hltb = models.HLTBGameData.objects.filter(
                game__isnull=True
            ).count()
            connected_hltb = total_hltb_metadata - orphaned_hltb

            # Count games that need metadata (for fetch button)
            games_needing_igdb = models.Game.objects.filter(
                primary_igdb_game_data__isnull=True
            ).count()
            games_needing_wikipedia = models.Game.objects.filter(
                Q(primary_wikipedia_game_data__isnull=True)
                | Q(primary_wikipedia_game_data__page_title="")
            ).count()
            games_needing_hltb = models.Game.objects.filter(
                primary_hltb_game_data__isnull=True
            ).count()

            context["counts"] = {
                "platforms": models.Platform.objects.count(),
                "publications": models.Publication.objects.count(),
                "lists": models.List.objects.count(),
                "games": total_games,
                "memberships": models.ListMembership.objects.count(),
                "developers": models.Developer.objects.count(),
                "series": models.Series.objects.count(),
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
            context["hltb_counts"] = {
                "total": total_hltb_metadata,
                "connected": connected_hltb,
                "orphaned": orphaned_hltb,
                "games_needing": games_needing_hltb,
                "percentage": int(
                    (connected_hltb / total_hltb_metadata * 100)
                    if total_hltb_metadata > 0
                    else 0
                ),
            }
        except Exception as e:
            # If database queries fail, provide safe defaults so page still loads
            logger.exception("Error loading import page counts")
            context["counts"] = {
                "platforms": 0,
                "publications": 0,
                "lists": 0,
                "games": 0,
                "memberships": 0,
                "developers": 0,
                "series": 0,
                "wikipedia_genres": 0,
            }
            context["igdb_counts"] = {
                "total": 0,
                "connected": 0,
                "orphaned": 0,
                "games_needing": 0,
                "percentage": 0,
                "estimate_seconds": 0,
            }
            context["wikipedia_counts"] = {
                "total": 0,
                "connected": 0,
                "orphaned": 0,
                "games_needing": 0,
                "percentage": 0,
                "estimate_seconds": 0,
                "has_auth": False,
            }
            context["hltb_counts"] = {
                "total": 0,
                "connected": 0,
                "orphaned": 0,
                "games_needing": 0,
                "percentage": 0,
            }
            context["import_errors"] = [
                f"Error loading page data: {e}. The database may be in an "
                "inconsistent state."
            ]
            context["import_success_message"] = None
            return context

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


class BatchImportProgressView(LoginRequiredMixin, View):
    """
    Streams batch file import progress via Server-Sent Events (SSE).

    Accepts POST requests with file uploads and streams progress in real-time.
    This prevents Gunicorn timeout for large imports by keeping the connection alive.
    """

    def post(self, request, *args, **kwargs):
        """Stream batch import progress as SSE events."""
        import_data = {
            "platforms_file": request.FILES.get("platforms_file"),
            "lists_file": request.FILES.get("lists_file"),
            "games_file": request.FILES.get("games_file"),
            "memberships_file": request.FILES.get("memberships_file"),
        }

        # Check if any files were provided
        if not any(import_data.values()):

            def error_generator():
                payload = {"event": "error", "message": "No files provided"}
                yield f"data: {json.dumps(payload)}\n\n"

            return StreamingHttpResponse(
                error_generator(),
                content_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        return StreamingHttpResponse(
            utils.import_batch_with_progress(import_data),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


# =============================================================================
# Newsletter Subscription Views
# =============================================================================


class UnsubscribeView(TemplateView):
    """Handle unsubscribe requests."""

    template_name = "unsubscribe.html"

    def get(self, request, token):  # pragma: no cover
        """Process unsubscribe token."""
        try:
            user = User.objects.get(unsubscribe_token=token)
            user.email_subscribed = False
            user.save()
            return self.render_to_response({"success": True, "email": user.email})
        except User.DoesNotExist:
            return self.render_to_response({"success": False})


# =============================================================================
# Auth Modal Views (HTMX partials for modal-based authentication)
# =============================================================================


class AuthModalLoginView(View):
    """Handle email login form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_login_form.html"

    def get(self, request):
        from allauth.account.forms import LoginForm

        form = LoginForm(request=request)
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import LoginForm
        from allauth.account.models import EmailAddress
        from django.contrib.auth import login

        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            user = form.user

            # Check if email is verified (mandatory verification)
            # Look for user's email in EmailAddress table
            email_address = EmailAddress.objects.filter(
                user=user, email__iexact=user.email
            ).first()

            # If no EmailAddress record or not verified, block login
            if not email_address or not email_address.verified:
                # User exists but email not verified - show resend option
                response = TemplateResponse(
                    request,
                    "auth/partials/_unverified_email.html",
                    {"email": user.email},
                )
                response["HX-Push-Url"] = "false"
                return response

            # Email verified - proceed with login
            login(
                request,
                user,
                backend="allauth.account.auth_backends.AuthenticationBackend",
            )
            # Redirect to home page (or referer if available)
            redirect_url = request.META.get("HTTP_REFERER", "/")
            # Don't redirect back to auth endpoints
            if "/auth/" in redirect_url or "/accounts/" in redirect_url:
                redirect_url = "/"
            response = HttpResponse()
            response["HX-Redirect"] = redirect_url
            return response

        # Re-render form with errors
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response


class AuthModalSignupView(View):
    """Handle email signup form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_signup_form.html"

    def get(self, request):
        from allauth.account.forms import SignupForm

        form = SignupForm()
        # Hide back button when accessed directly (not from auth options)
        show_back = request.GET.get("direct") != "1"
        response = TemplateResponse(
            request, self.template_name, {"form": form, "show_back": show_back}
        )
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import SignupForm
        from allauth.account.models import EmailAddress

        form = SignupForm(request.POST)
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        username_error = None

        # Validate username if provided (skip if it matches email - that's the default)
        if username and username.lower() != email.lower():
            if len(username) < 3:
                username_error = "Username must be at least 3 characters."
            elif len(username) > 30:
                username_error = "Username must be 30 characters or fewer."
            elif not username.replace("_", "").replace("-", "").isalnum():
                username_error = (
                    "Username can only contain letters, numbers, "
                    "underscores, and hyphens."
                )
            elif User.objects.filter(username__iexact=username).exists():
                username_error = "This username is already taken."

        if form.is_valid() and not username_error:
            # Save the user (creates user and EmailAddress, but doesn't send email)
            user = form.save(request)

            # Set email subscription preference from checkbox
            email_subscribed = request.POST.get("email_subscribed") == "on"
            if email_subscribed:
                user.email_subscribed = True
                user.date_subscribed = timezone.now()
                user.generate_unsubscribe_token()
                user.save()

            # Send verification email (form.save doesn't do this automatically)
            email_address = EmailAddress.objects.filter(
                user=user, email__iexact=user.email
            ).first()
            if email_address and not email_address.verified:
                email_address.send_confirmation(request, signup=True)

            # Don't log in - show verification screen instead
            response = TemplateResponse(
                request,
                "auth/partials/_verification_sent.html",
                {"email": user.email},
            )
            response["HX-Push-Url"] = "false"
            return response

        # Check if email already exists with unverified account
        email = request.POST.get("email", "").strip()
        if email and form.errors.get("email"):
            existing_email = EmailAddress.objects.filter(email__iexact=email).first()
            if existing_email and not existing_email.verified:
                # Show resend verification option instead of error
                response = TemplateResponse(
                    request,
                    "auth/partials/_unverified_email.html",
                    {"email": existing_email.email},
                )
                response["HX-Push-Url"] = "false"
                return response

        # Re-render form with errors
        response = TemplateResponse(
            request,
            self.template_name,
            {
                "form": form,
                "username_error": username_error,
                "username_value": username,
            },
        )
        response["HX-Push-Url"] = "false"
        return response


class AuthModalForgotPasswordView(View):
    """Handle forgot password form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_forgot_password_form.html"

    def get(self, request):
        from allauth.account.forms import ResetPasswordForm

        form = ResetPasswordForm()
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        from allauth.account.forms import ResetPasswordForm

        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            form.save(request)
            # Show success message
            response = TemplateResponse(
                request, "auth/partials/_forgot_password_sent.html", {}
            )
            response["HX-Push-Url"] = "false"
            return response

        # Re-render form with errors
        response = TemplateResponse(request, self.template_name, {"form": form})
        response["HX-Push-Url"] = "false"
        return response


class AuthModalResendVerificationView(View):
    """Handle resending verification email from the auth modal."""

    def post(self, request):
        from allauth.account.models import EmailAddress

        email = request.POST.get("email", "").strip()

        if email:
            try:
                email_address = EmailAddress.objects.get(email__iexact=email)
                if not email_address.verified:
                    email_address.send_confirmation(request, signup=False)
            except EmailAddress.DoesNotExist:
                pass  # Don't reveal if email exists

        # Always show success (prevents email enumeration)
        response = TemplateResponse(
            request,
            "auth/partials/_verification_resent.html",
            {"email": email},
        )
        response["HX-Push-Url"] = "false"
        return response


class EmailConfirmationView(TemplateView):
    """Custom email confirmation page matching the site style."""

    template_name = "account/email_confirmed.html"

    def get(self, request, key):
        """Process email confirmation key."""
        from allauth.account.models import EmailConfirmationHMAC
        from django.contrib.auth import login

        try:
            # Validate the confirmation key
            email_confirmation = EmailConfirmationHMAC.from_key(key)
            if email_confirmation:
                # Confirm the email
                email_confirmation.confirm(request)
                email_address = email_confirmation.email_address

                # Log the user in (matches ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION)
                user = email_address.user
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )

                return self.render_to_response(
                    {
                        "success": True,
                        "email": email_address.email,
                    }
                )
        except Exception:
            pass

        # Invalid or expired key
        return self.render_to_response({"success": False})


@method_decorator(never_cache, name="get")
class AuthModalProfileView(View):
    """Handle profile editing form in the auth modal (HTMX partial)."""

    template_name = "auth/partials/_profile_form.html"

    def get(self, request):
        if not request.user.is_authenticated:
            # Redirect to login form via HTMX
            response = HttpResponse()
            response["HX-Redirect"] = reverse("auth-modal-login")
            return response

        # User fields are now directly on the user model
        user = request.user

        # Get played games stats (only count non-orphaned games)
        played_count = user.played_games.filter(game__isnull=False).count()
        want_to_play_count = user.want_to_play_games.filter(game__isnull=False).count()
        total_games = models.Game.objects.count()

        # Calculate estimated playtime for want-to-play backlog
        backlog_playtime = {"main": None, "completionist": None}
        if want_to_play_count > 0:
            from django.db.models import Sum

            # Get games in user's want-to-play list that have HLTB data
            want_to_play_game_ids = user.want_to_play_games.filter(
                game__isnull=False
            ).values_list("game_id", flat=True)

            playtime_totals = models.HLTBGameData.objects.filter(
                game_id__in=want_to_play_game_ids, is_primary=True
            ).aggregate(
                main_total=Sum("main_story_hours"),
                completionist_total=Sum("completionist_hours"),
            )

            backlog_playtime["main"] = playtime_totals["main_total"]
            backlog_playtime["completionist"] = playtime_totals["completionist_total"]

        # Calculate percentile ranking
        percentile_data = calculate_percentile(played_count)

        response = TemplateResponse(
            request,
            self.template_name,
            {
                "profile": user,
                "form": {},
                "played_count": played_count,
                "want_to_play_count": want_to_play_count,
                "backlog_playtime": backlog_playtime,
                "total_games": total_games,
                "percentile": percentile_data["percentile"],
                "percentile_message": percentile_data["message"],
            },
        )
        response["HX-Push-Url"] = "false"
        return response

    def post(self, request):
        if not request.user.is_authenticated:
            response = HttpResponse()
            response["HX-Redirect"] = "/"
            return response

        user = request.user
        new_username = request.POST.get("username", "").strip()

        # Validate username (if changed, skip validation if it matches user's email)
        username_error = None
        if (
            new_username
            and new_username != user.username
            and new_username.lower() != user.email.lower()
        ):
            if len(new_username) < 3:
                username_error = "Username must be at least 3 characters."
            elif len(new_username) > 30:
                username_error = "Username must be 30 characters or fewer."
            elif not new_username.replace("_", "").replace("-", "").isalnum():
                username_error = (
                    "Username can only contain letters, numbers, "
                    "underscores, and hyphens."
                )
            elif (
                User.objects.filter(username__iexact=new_username)
                .exclude(pk=user.pk)
                .exists()
            ):
                username_error = "This username is already taken."

            if username_error:
                # Re-render with full context including stats
                from django.db.models import Sum

                played_count = user.played_games.filter(game__isnull=False).count()
                want_to_play_count = user.want_to_play_games.filter(
                    game__isnull=False
                ).count()
                total_games = models.Game.objects.count()
                percentile_data = calculate_percentile(played_count)

                # Calculate backlog playtime for error re-render
                backlog_playtime = {"main": None, "completionist": None}
                if want_to_play_count > 0:
                    want_to_play_game_ids = user.want_to_play_games.filter(
                        game__isnull=False
                    ).values_list("game_id", flat=True)
                    playtime_totals = models.HLTBGameData.objects.filter(
                        game_id__in=want_to_play_game_ids, is_primary=True
                    ).aggregate(
                        main_total=Sum("main_story_hours"),
                        completionist_total=Sum("completionist_hours"),
                    )
                    backlog_playtime["main"] = playtime_totals["main_total"]
                    backlog_playtime["completionist"] = playtime_totals[
                        "completionist_total"
                    ]

                return render(
                    request,
                    "auth/partials/_profile_form.html",
                    {
                        "profile": user,
                        "form": {"username": {"errors": [username_error]}},
                        "played_count": played_count,
                        "want_to_play_count": want_to_play_count,
                        "backlog_playtime": backlog_playtime,
                        "total_games": total_games,
                        "percentile": percentile_data["percentile"],
                        "percentile_message": percentile_data["message"],
                    },
                )
            user.username = new_username

        email_subscribed = request.POST.get("email_subscribed") == "on"

        if email_subscribed and not user.email_subscribed:
            # Subscribing - logged in user already has verified email
            user.email_subscribed = True
            user.generate_unsubscribe_token()
            if not user.date_subscribed:
                from django.utils import timezone

                user.date_subscribed = timezone.now()
        elif not email_subscribed:
            user.email_subscribed = False

        user.save()

        # Refresh page to show updated name in sidebar
        response = HttpResponse()
        response["HX-Refresh"] = "true"
        return response


class AuthLogoutView(View):
    """Handle logout and redirect back to previous page."""

    def post(self, request):
        from django.contrib.auth import logout

        logout(request)
        # Redirect back to referer or home
        redirect_url = request.META.get("HTTP_REFERER", "/")
        if "/auth/" in redirect_url or "/accounts/" in redirect_url:
            redirect_url = "/"
        return redirect(redirect_url)


class TogglePlayedGameView(LoginRequiredMixin, View):
    """
    Set or cycle a game's tracking status.

    If `status` query param is provided (none, want, played), sets directly.
    Otherwise cycles: none → want → played → none.

    States are mutually exclusive - a game cannot be both
    "want to play" and "played" simultaneously.
    """

    def post(self, request, igdb_id):
        game = get_object_or_404(models.Game, igdb_id=igdb_id)

        # Check current state
        is_played = models.PlayedGame.objects.filter(
            user=request.user, igdb_id=igdb_id
        ).exists()
        is_want_to_play = models.WantToPlayGame.objects.filter(
            user=request.user, igdb_id=igdb_id
        ).exists()

        # Check for explicit status parameter
        target_status = request.GET.get("status")

        if target_status in ("none", "want", "played"):
            # Direct status set - clear existing and set new
            if is_played:
                models.PlayedGame.objects.filter(
                    user=request.user, igdb_id=igdb_id
                ).delete()
            if is_want_to_play:
                models.WantToPlayGame.objects.filter(
                    user=request.user, igdb_id=igdb_id
                ).delete()

            if target_status == "played":
                models.PlayedGame.objects.create(
                    user=request.user, igdb_id=igdb_id, game=game
                )
                new_is_played = True
                new_is_want_to_play = False
            elif target_status == "want":
                models.WantToPlayGame.objects.create(
                    user=request.user, igdb_id=igdb_id, game=game
                )
                new_is_played = False
                new_is_want_to_play = True
            else:  # none
                new_is_played = False
                new_is_want_to_play = False
        else:
            # Legacy cycle behavior: none → want → played → none
            if is_played:
                models.PlayedGame.objects.filter(
                    user=request.user, igdb_id=igdb_id
                ).delete()
                new_is_played = False
                new_is_want_to_play = False
            elif is_want_to_play:
                models.WantToPlayGame.objects.filter(
                    user=request.user, igdb_id=igdb_id
                ).delete()
                models.PlayedGame.objects.create(
                    user=request.user, igdb_id=igdb_id, game=game
                )
                new_is_played = True
                new_is_want_to_play = False
            else:
                models.WantToPlayGame.objects.create(
                    user=request.user, igdb_id=igdb_id, game=game
                )
                new_is_played = False
                new_is_want_to_play = True

        # Invalidate caches
        cache.delete("user_played_games_distribution")
        invalidate_played_games_cache(request.user.id)
        invalidate_want_to_play_cache(request.user.id)

        # Preserve button size (large on game detail page, default elsewhere)
        size = request.GET.get("size")

        response = render(
            request,
            "games/includes/_played_button.html",
            {
                "game": game,
                "is_played": new_is_played,
                "is_want_to_play": new_is_want_to_play,
                "size": size,
                "just_toggled": True,
            },
        )
        # Prevent URL push for this HTMX action
        response["HX-Push-Url"] = "false"
        return response

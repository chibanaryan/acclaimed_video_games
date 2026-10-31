import logging
from urllib.parse import urljoin

from django.db import Error as DatabaseError, connection
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.utils.encoding import escape_uri_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from core import sites
from core.mixins import AnonymousResponseCacheMixin
from games import config as games_config
from games.models import Game, List
from games.services.game_filters import DIMENSIONS
from music.models import Album, MusicList

logger = logging.getLogger(__name__)

# How many covers each card on the landing page shows
LANDING_TOP_COUNT = 5

# What an old rankings link at `/` carried. The set is closed, where tracking
# tags are not: `igsh`, `gbraid` and whatever comes next stay on the landing page.
OLD_FILTER_PARAMS = frozenset(
    param for params in DIMENSIONS.values() for param in params
) | {"sort", "dir", "page", "highlight", "append", "partial"}

# Where the apex's old music paths live on the music host
MUSIC_PATH_PREFIXES = (("/api/music", "/api/"), ("/music", "/"))


def healthz(request):
    """200 when Django can reach the database, 503 when it cannot.

    For uptime monitoring. Neither existing check proves the database is up:
    the gzip-less monitor gets UncompressedUptimeCheckMiddleware's 2-byte
    answer, which touches nothing, and the other fetches `/`, which can be
    served from the per-process page cache for minutes. Exempt from rate
    limiting, never cached. Catches ``django.db.Error``, which also covers
    an ``InterfaceError`` from a connection the database dropped.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        response = HttpResponse("ok", content_type="text/plain")
    except DatabaseError:
        logger.exception("Health check could not reach the database")
        response = HttpResponse(
            "database unavailable", status=503, content_type="text/plain"
        )
    response["Cache-Control"] = "no-store"
    return response


class LandingView(AnonymousResponseCacheMixin, TemplateView):
    """The apex, acclaimedmedia.org: one card per site, leading to it.

    Each card shows the site's size and its top few covers.
    """

    template_name = "core/landing.html"
    page_cache_timeout = games_config.CACHE_TIMEOUT_LANDING_PAGE

    def _is_old_filter_link(self):
        """The rankings lived at `/` until the split, so every filtered link
        out there is `/?genres=5`."""
        return not OLD_FILTER_PARAMS.isdisjoint(self.request.GET)

    def get(self, request, *args, **kwargs):
        if self._is_old_filter_link():
            return redirect_to_site(request)
        return super().get(request, *args, **kwargs)

    def get_page_cache_key(self):
        # The cache is read before `get` runs, so an old filter link has to
        # miss it to reach the redirect. Anything else, such as a tracking tag,
        # changes nothing on the page and shares the entry.
        if self._is_old_filter_link():
            return None
        return f"landing_root:{games_config.CACHE_VERSION}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        context["games_card"] = {
            "url": sites.site_url(sites.GAMES, "home", request=request),
            "count": Game.objects.count(),
            "list_count": List.objects.count(),
            "top": [
                {
                    "name": game.name,
                    "image": game.thumbnail,
                    "image_2x": game.thumbnail_2x,
                }
                for game in Game.objects.select_related(
                    "primary_igdb_game_data"
                ).order_by("rank")[:LANDING_TOP_COUNT]
            ],
        }
        music_origin = sites.site_origin(sites.MUSIC, request)
        context["music_card"] = {
            "url": sites.site_url(sites.MUSIC, "music:home", request=request),
            "count": Album.objects.count(),
            "list_count": MusicList.objects.count(),
            "top": [
                {
                    "name": album.name,
                    # A stored cover is a path on the music host
                    "image": (
                        urljoin(music_origin, album.thumbnail)
                        if album.thumbnail
                        else None
                    ),
                }
                for album in Album.objects.select_related(
                    "primary_musicbrainz_album_data"
                ).order_by("rank")[:LANDING_TOP_COUNT]
            ],
        }
        return context


@csrf_exempt
def redirect_to_site(request):
    """Send a path the apex no longer serves to the site that serves it now.

    Until the split every page lived at the apex: games at their paths and
    music under ``/music/`` and ``/api/music/``. Those links are out in
    search indexes, bookmarks and emails, so each keeps working: music's
    paths move to the root of music.acclaimedmedia.org, everything else to
    the same path on games.acclaimedmedia.org, query string and all. No
    308 for a POST: the browser would re-send it with the apex's Origin and
    the old cookies, which the new host's CSRF check refuses. CSRF-exempt
    because it acts on nothing.
    """
    site, path = sites.GAMES, request.path
    for old_prefix, new_prefix in MUSIC_PATH_PREFIXES:
        if path == old_prefix or path.startswith(f"{old_prefix}/"):
            site = sites.MUSIC
            path = new_prefix + path[len(old_prefix) :].lstrip("/")
            break
    query = request.META.get("QUERY_STRING", "")
    # request.path is decoded, so it goes back through escaping: a "#" or "?"
    # that was %-encoded in the old link must not end the path here
    url = sites.site_origin(site, request) + escape_uri_path(path)
    if query:
        url += f"?{query}"
    return HttpResponsePermanentRedirect(url)

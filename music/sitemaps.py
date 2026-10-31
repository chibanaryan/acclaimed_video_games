"""
The music host's ``/sitemap.xml`` sections, put on its origin by
``core.sitemaps.for_site``.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from music import models
from music.services import landing_pages
from music.services.credits import album_ids_by_artist


class MusicStaticSitemap(Sitemap):
    """The section's index pages."""

    priority = 0.5
    changefreq = "weekly"

    def items(self):
        return ["music:home", "music:artist-list", "music:list-list", "music:browse"]

    def location(self, item):
        return reverse(item)


class MusicLandingPageSitemap(Sitemap):
    """The /genres/<slug>/ and /<decade>s/ ranking pages."""

    priority = 0.7
    changefreq = "weekly"

    def items(self):
        items = [
            ("music:by-genre", {"slug": genre["slug"]})
            for genre in landing_pages.get_landing_genres()
        ]
        items += [
            ("music:by-decade", {"decade": decade})
            for decade in landing_pages.get_landing_decades()
        ]
        return items

    def location(self, item):
        name, kwargs = item
        return reverse(name, kwargs=kwargs)


class AlbumSitemap(Sitemap):
    """One entry per album, best-ranked first."""

    priority = 0.8
    changefreq = "monthly"

    def items(self):
        return models.Album.objects.order_by("rank")

    def lastmod(self, obj):
        return obj.modified


class ArtistSitemap(Sitemap):
    """Artists with at least one ranked album, as the list shows."""

    priority = 0.6
    changefreq = "monthly"

    def items(self):
        album_ids = album_ids_by_artist()
        return (
            models.Artist.objects.filter(id__in=list(album_ids))
            .exclude(slug__isnull=True)
            .exclude(slug="")
            .order_by("name")
        )


music_sitemaps = {
    "music-static": MusicStaticSitemap,
    "music-landing": MusicLandingPageSitemap,
    "music-albums": AlbumSitemap,
    "music-artists": ArtistSitemap,
}

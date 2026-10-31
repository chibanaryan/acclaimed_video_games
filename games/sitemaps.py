"""
Sitemap configuration for the games site.

Generates XML sitemaps for search engines to index the site efficiently.
"""

import re

from django.contrib.flatpages.models import FlatPage
from django.contrib.sitemaps import Sitemap
from django.contrib.sites.models import Site
from django.urls import reverse

from . import models

SLUG = re.compile(r"[-a-zA-Z0-9_]+")


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages."""

    priority = 0.5
    changefreq = "weekly"

    def items(self):
        # Book pages are staff-only (they 404 for anonymous visitors and
        # crawlers), so they stay out of the sitemap until books launches.
        # Music has its own sections in music/sitemaps.py
        return [
            "home",
            "developers-list",
            "list-list",
            "article-list",
        ]

    def location(self, item):
        return reverse(item)


class LandingPageSitemap(Sitemap):
    """Sitemap for the /games/... SEO ranking pages."""

    changefreq = "weekly"
    priority = 0.7

    def items(self):
        from games.services import landing_pages

        items = [("games-browse", {})]
        items += [
            ("games-by-category", {"slug": genre["slug"]})
            for genre in landing_pages.get_landing_genres()
        ]
        items += [
            ("games-by-category", {"slug": platform["slug"]})
            for platform in landing_pages.get_landing_platforms()
        ]
        items += [
            ("games-by-decade", {"decade": decade})
            for decade in landing_pages.get_landing_decades()
        ]
        items += [
            ("games-by-year", {"year": year})
            for year in landing_pages.get_landing_years()
        ]
        return items

    def location(self, item):
        name, kwargs = item
        return reverse(name, kwargs=kwargs)


class GameSitemap(Sitemap):
    """Sitemap for individual game pages."""

    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return models.Game.objects.all()

    def location(self, obj):
        return reverse("game-detail", kwargs={"slug": obj.slug})

    def lastmod(self, obj):
        # Game has `modified`, not `updated_at`; reading the latter gave no
        # game a <lastmod> at all. An import recreates every game, so after
        # one this is the import's date - which is when the page changed.
        return obj.modified


class DeveloperSitemap(Sitemap):
    """Sitemap for developer pages."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Subsidiary developers don't have slugs or detail pages
        return models.Developer.objects.exclude(slug="")

    def location(self, obj):
        return reverse("developer-detail", kwargs={"slug": obj.slug})


class ArticleSitemap(Sitemap):
    """Sitemap for published blog articles."""

    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return models.Article.objects.filter(
            status=models.Article.Status.PUBLISHED
        ).order_by("-published_at")

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(Sitemap):
    """Sitemap for the flat pages (about, donate, legal, privacy).

    They are linked as ``/page/<slug>/`` whether the FlatPage's own url is
    ``/about/`` or ``/page/about/`` (``PageDetailView`` accepts either), so
    that is the address listed. A page behind a login is left out.
    """

    changefreq = "yearly"
    priority = 0.3

    def items(self):
        pages = FlatPage.objects.filter(
            registration_required=False, sites=Site.objects.get_current()
        ).order_by("url")
        # dict.fromkeys: /about/ and /page/about/ are both "about"
        return list(dict.fromkeys(slug for slug in map(self._slug, pages) if slug))

    @staticmethod
    def _slug(page):
        # Only what PageDetailView finds and <slug:slug> can reverse: a
        # FlatPage url may hold "." or "~", and one NoReverseMatch here
        # would take the whole sitemap down.
        if not page.url.endswith("/"):
            return None
        slug = page.url.strip("/").removeprefix("page/")
        return slug if SLUG.fullmatch(slug) else None

    def location(self, item):
        return reverse("page-detail", kwargs={"slug": item})


# Dictionary of all sitemaps for URL configuration
sitemaps = {
    "static": StaticViewSitemap,
    "landing": LandingPageSitemap,
    "games": GameSitemap,
    "developers": DeveloperSitemap,
    "articles": ArticleSitemap,
}

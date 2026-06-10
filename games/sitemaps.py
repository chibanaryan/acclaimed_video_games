"""
Sitemap configuration for Acclaimed Games.

Generates XML sitemaps for search engines to index the site efficiently.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from . import models


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages."""

    priority = 0.5
    changefreq = "weekly"

    def items(self):
        # Book pages are staff-only (they 404 for anonymous visitors and
        # crawlers), so they stay out of the sitemap until books launch
        # publicly
        return [
            "home",
            "developers-list",
            "list-list",
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
            ("games-by-category", {"slug": family["slug"]})
            for family in landing_pages.get_landing_families()
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
        return obj.updated_at if hasattr(obj, "updated_at") else None


class DeveloperSitemap(Sitemap):
    """Sitemap for developer pages."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Subsidiary developers don't have slugs or detail pages
        return models.Developer.objects.exclude(slug="")

    def location(self, obj):
        return reverse("developer-detail", kwargs={"slug": obj.slug})


# Dictionary of all sitemaps for URL configuration
sitemaps = {
    "static": StaticViewSitemap,
    "landing": LandingPageSitemap,
    "games": GameSitemap,
    "developers": DeveloperSitemap,
}

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
        return ["home", "games-list", "developers-list", "list-list", "post-list"]

    def location(self, item):
        return reverse(item)


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


class CompanySitemap(Sitemap):
    """Sitemap for company/developer pages."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return models.Company.objects.all()

    def location(self, obj):
        return reverse("developer-detail", kwargs={"slug": obj.slug})


# Dictionary of all sitemaps for URL configuration
sitemaps = {
    "static": StaticViewSitemap,
    "games": GameSitemap,
    "developers": CompanySitemap,
}

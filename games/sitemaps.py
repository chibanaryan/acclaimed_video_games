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
        # Static pages for games; books static pages will be added when books app is enabled
        return ["home", "developers-list", "list-list"]

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


class DeveloperSitemap(Sitemap):
    """Sitemap for developer pages."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Subsidiary developers don't have slugs or detail pages
        return models.Developer.objects.exclude(slug="")

    def location(self, obj):
        return reverse("developer-detail", kwargs={"slug": obj.slug})


# TODO: Add BookSitemap and AuthorSitemap when books app is enabled
# class BookSitemap(Sitemap):
#     """Sitemap for individual book pages."""
#     changefreq = "monthly"
#     priority = 0.8
#
#     def items(self):
#         from books.models import Book
#         return Book.objects.all()
#
#     def location(self, obj):
#         return reverse("book-detail", kwargs={"slug": obj.slug})
#
# class AuthorSitemap(Sitemap):
#     """Sitemap for author pages."""
#     changefreq = "monthly"
#     priority = 0.6
#
#     def items(self):
#         from books.models import Author
#         return Author.objects.all()
#
#     def location(self, obj):
#         return reverse("author-detail", kwargs={"slug": obj.slug})


# Dictionary of all sitemaps for URL configuration
sitemaps = {
    "static": StaticViewSitemap,
    "games": GameSitemap,
    "developers": DeveloperSitemap,
    # "books": BookSitemap,  # Enable when books app is ready
    # "authors": AuthorSitemap,  # Enable when books app is ready
}

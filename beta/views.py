from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from games import models


class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch latest posts (limit 5, matching Vue version)
        context["posts"] = models.Post.objects.filter(active=True).order_by("-date")[:5]

        # Fetch top 10 games (matching Vue version)
        context["games"] = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        ).order_by("rank")[:10]

        # Fetch front-page snippet
        try:
            context["snippet"] = models.Snippet.objects.get(slug="front-page")
        except models.Snippet.DoesNotExist:
            context["snippet"] = None

        # Fetch meta data for last update (matching Vue version which uses meta.games.last_update)
        # This is the max modified date from all games
        from django.db.models import Max

        last_update = models.Game.objects.aggregate(Max("modified"))["modified__max"]
        context["last_update"] = last_update

        return context


class GameListView(ListView):
    model = models.Game
    template_name = "games/game_list.html"
    context_object_name = "games"
    paginate_by = 100

    def get_queryset(self):
        # Prefetch relationships for GameRowProperties component
        qs = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",  # Access the Developer through DeveloperAlias
            "platforms",
            "genres",
        ).order_by("rank")

        # TODO: Add filtering logic (year, decade, etc.)
        return qs


class GameDetailView(DetailView):
    model = models.Game
    template_name = "games/game_detail.html"
    context_object_name = "game"
    slug_field = "slug"
    slug_url_kwarg = "slug"


class GameSearchView(ListView):
    model = models.Game
    template_name = "games/game_search.html"
    context_object_name = "games"
    paginate_by = 100

    def get_queryset(self):
        # TODO: Add search/filtering logic
        return super().get_queryset()


class DeveloperListView(ListView):
    model = models.DeveloperAlias
    template_name = "developers/developer_list.html"
    context_object_name = "developers"
    paginate_by = 100


class DeveloperDetailView(DetailView):
    model = models.Developer
    template_name = "developers/developer_detail.html"
    context_object_name = "developer"
    slug_field = "slug"
    slug_url_kwarg = "slug"


class ListListView(ListView):
    model = models.List
    template_name = "lists/list_list.html"
    context_object_name = "lists"
    paginate_by = 100


class PostListView(ListView):
    model = models.Post
    template_name = "posts/post_list.html"
    context_object_name = "posts"
    paginate_by = 5


class PageDetailView(TemplateView):
    template_name = "pages/page_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Add page context
        return context

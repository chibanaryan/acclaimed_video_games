from django.urls import path
from . import views
from . import api_views

app_name = "beta"

urlpatterns = [
    path("", views.HomePageView.as_view(), name="home"),
    path("games/", views.GameListView.as_view(), name="games-list"),
    path("games/search/", views.GameSearchView.as_view(), name="games-search"),
    path("game/<slug:slug>/", views.GameDetailView.as_view(), name="game-detail"),
    path("developers/", views.DeveloperListView.as_view(), name="developers-list"),
    path(
        "developers/<slug:slug>/",
        views.DeveloperDetailView.as_view(),
        name="developer-detail",
    ),
    path("lists/", views.ListListView.as_view(), name="list-list"),
    path("posts/", views.PostListView.as_view(), name="post-list"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page-detail"),
    # API endpoints for HTMX/Alpine.js
    path(
        "api/games/search/",
        api_views.GameSearchAPIView.as_view(),
        name="api-games-search",
    ),
]

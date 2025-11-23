from django.urls import path, re_path
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
    path(
        "developer-alias/<int:id>/",
        views.DeveloperAliasRedirectView.as_view(),
        name="developer-alias-redirect",
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
    # Import functionality
    path("import/", views.ImportView.as_view(), name="import"),
    path(
        "import/igdb-progress/",
        views.IGDBProgressView.as_view(),
        name="igdb-progress",
    ),
    # Catch-all 404 handler (must be last!)
    # Matches any URL under /beta/ that didn't match above routes
    re_path(r".*", views.NotFoundView.as_view(), name="not-found"),
]

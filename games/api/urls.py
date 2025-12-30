from django.urls import path

from . import views

app_name = "games-api"

urlpatterns = [
    path("games/", views.GameListView.as_view(), name="game-list"),
    path("games/all/", views.GameAllDataView.as_view(), name="game-all-data"),
    path(
        "games/version/", views.GameDataVersionView.as_view(), name="game-data-version"
    ),
    path("games/<slug:slug>/", views.GameDetailView.as_view(), name="game-detail"),
    path(
        "developers/<slug:slug>/",
        views.CompanyDetailView.as_view(),
        name="developer-detail",
    ),
    path(
        "developer-aliases/",
        views.StudioListView.as_view(),
        name="developeralias-list",
    ),
    path(
        "developer-aliases/<int:igdb_id>/",
        views.StudioDetailView.as_view(),
        name="developeralias-detail",
    ),
    path("lists/", views.ListListView.as_view(), name="list-list"),
    path("publications/", views.PublicationListView.as_view(), name="publication-list"),
    path(
        "publications/<int:pk>/",
        views.PublicationDetailView.as_view(),
        name="publication-detail",
    ),
    path(
        "snippets/<slug:slug>/",
        views.SnippetDetailView.as_view(),
        name="snippet-detail",
    ),
    path("pages/<slug:url>/", views.PageDetailView.as_view(), name="page-detail"),
    path("meta/", views.MetaView.as_view(), name="meta"),
    path("genres/", views.GenreListView.as_view(), name="genre-list"),
    path(
        "wikipedia-genres/",
        views.WikipediaGenreListView.as_view(),
        name="wikipedia-genre-list",
    ),
    path(
        "wikipedia-genres/tree/",
        views.WikipediaGenreTreeView.as_view(),
        name="wikipedia-genre-tree",
    ),
    path("platforms/", views.PlatformListView.as_view(), name="platform-list"),
]

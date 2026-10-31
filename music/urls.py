from django.urls import path, re_path

from music import views

app_name = "music"

urlpatterns = [
    # Album rankings
    path("", views.AlbumHomePageView.as_view(), name="home"),
    # Album search (HTMX endpoint)
    path("search/", views.AlbumSearchView.as_view(), name="search"),
    # The current filter state as a CSV, as the games sidebar offers
    path("download/", views.AlbumDownloadView.as_view(), name="download"),
    # Toggle an album's listen status (HTMX endpoint). Before <slug:slug>/
    # so a numeric id is never read as an album slug.
    path(
        "<int:album_id>/toggle-listened/",
        views.ToggleListenedAlbumView.as_view(),
        name="toggle-listened",
    ),
    # Source lists behind the rankings
    path("lists/", views.MusicListListView.as_view(), name="list-list"),
    # Data import (staff only)
    path("import/", views.MusicImportView.as_view(), name="import"),
    # Cover art, served from our own store rather than hotlinked. Before
    # <slug:slug>/ so "cover" is not read as an album slug.
    path(
        "cover/<str:release_mbid>/<str:image_id>-<int:size>.jpg",
        views.AlbumCoverView.as_view(),
        name="cover",
    ),
    # Artist routes (before <slug:slug>/ so "artists" is not read as a slug)
    path("artists/", views.ArtistListView.as_view(), name="artist-list"),
    path(
        "artists/<slug:slug>/", views.ArtistDetailView.as_view(), name="artist-detail"
    ),
    # SEO ranking pages, reached from the sitemap only. Before <slug:slug>/;
    # config.RESERVED_ALBUM_SLUGS keeps an album from slugifying onto any of
    # these first segments.
    path("browse/", views.MusicBrowseIndexView.as_view(), name="browse"),
    path("genres/<slug:slug>/", views.GenreLandingView.as_view(), name="by-genre"),
    re_path(
        r"^(?P<decade>\d{3}0)s/$", views.DecadeLandingView.as_view(), name="by-decade"
    ),
    # Album detail (catch-all slug pattern, must be last)
    path("<slug:slug>/", views.AlbumDetailView.as_view(), name="album-detail"),
]

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from games import views
from games.api import views as api_views
from games.sitemaps import sitemaps

# Custom 404 handler
handler404 = "games.views.custom_404_view"

urlpatterns = [
    # Sitemap and robots.txt for SEO
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("robots.txt", views.robots_txt, name="robots-txt"),
    # API search endpoint for HTMX/Alpine.js (must be before REST API include)
    path(
        "api/games/search/",
        api_views.GameSearchAPIView.as_view(),
        name="api-games-search",
    ),
    path("api/", include("games.api.urls", namespace="games-api")),
    path("admin/", admin.site.urls),
    path("import/", views.ImportView.as_view(), name="import"),
    path(
        "import/igdb-progress/", views.IGDBProgressView.as_view(), name="igdb-progress"
    ),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    # Main site routes (Django + HTMX + Alpine.js)
    path("", views.HomePageView.as_view(), name="home"),
    path(
        "contact/thank-you/",
        views.ContactThankYouView.as_view(),
        name="contact_thank_you",
    ),
    path("games/", views.GameListView.as_view(), name="games-list"),
    path("games/download/", views.download_games_csv, name="games-download"),
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
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    import debug_toolbar
    from django.views.defaults import page_not_found

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
        # Test route to preview custom 404 page
        path(
            "test-404/", lambda request: page_not_found(request, Exception("Test 404"))
        ),
        *urlpatterns,
    ]

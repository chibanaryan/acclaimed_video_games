from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView

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
    path(
        "import/wikipedia-page-progress/",
        views.WikipediaPageProgressView.as_view(),
        name="wikipedia-page-progress",
    ),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    # Main site routes (Django + HTMX + Alpine.js)
    path("", views.HomePageView.as_view(), name="home"),
    path(
        "contact/thank-you/",
        views.ContactThankYouView.as_view(),
        name="contact_thank_you",
    ),
    # Newsletter subscription routes
    path("subscribe/", views.SubscribeView.as_view(), name="subscribe"),
    path(
        "subscribe/pending/",
        views.SubscribePendingView.as_view(),
        name="subscribe_pending",
    ),
    path(
        "subscribe/already/",
        views.SubscribeAlreadyView.as_view(),
        name="subscribe_already",
    ),
    path(
        "subscribe/confirm/<str:token>/",
        views.ConfirmSubscriptionView.as_view(),
        name="subscribe_confirm",
    ),
    path(
        "unsubscribe/<str:token>/", views.UnsubscribeView.as_view(), name="unsubscribe"
    ),
    path("rankings/", views.GameSearchView.as_view(), name="games-list"),
    path("rankings/download/", views.download_games_csv, name="games-download"),
    # Redirect old URLs to new rankings page (preserves query params)
    path(
        "games/",
        RedirectView.as_view(url="/rankings/", permanent=True, query_string=True),
        name="games-redirect",
    ),
    path(
        "games/search/",
        RedirectView.as_view(url="/rankings/", permanent=True, query_string=True),
        name="games-search",
    ),
    path("game/<slug:slug>/", views.GameDetailView.as_view(), name="game-detail"),
    path("developers/", views.StudioListView.as_view(), name="developers-list"),
    path(
        "developers/<slug:slug>/",
        views.CompanyDetailView.as_view(),
        name="developer-detail",
    ),
    path(
        "developer-alias/<int:id>/",
        views.StudioRedirectView.as_view(),
        name="developer-alias-redirect",
    ),
    path("lists/", views.ListListView.as_view(), name="list-list"),
    path("posts/", views.PostListView.as_view(), name="post-list"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page-detail"),
]

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
    ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

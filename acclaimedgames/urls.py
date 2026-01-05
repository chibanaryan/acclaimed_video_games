from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
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
    path(
        "api/unified-search/",
        api_views.UnifiedSearchView.as_view(),
        name="api-unified-search",
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
    # Custom email confirmation page (must be before allauth include)
    path(
        "accounts/confirm-email/<str:key>/",
        views.EmailConfirmationView.as_view(),
        name="account_confirm_email",
    ),
    path("accounts/", include("allauth.urls")),
    # Auth modal partials (HTMX)
    path(
        "auth/modal/login/",
        views.AuthModalLoginView.as_view(),
        name="auth-modal-login",
    ),
    path(
        "auth/modal/signup/",
        views.AuthModalSignupView.as_view(),
        name="auth-modal-signup",
    ),
    path(
        "auth/modal/profile/",
        views.AuthModalProfileView.as_view(),
        name="auth-modal-profile",
    ),
    path(
        "auth/modal/forgot-password/",
        views.AuthModalForgotPasswordView.as_view(),
        name="auth-modal-forgot-password",
    ),
    path(
        "auth/modal/resend-verification/",
        views.AuthModalResendVerificationView.as_view(),
        name="auth-modal-resend-verification",
    ),
    path(
        "auth/logout/",
        views.AuthLogoutView.as_view(),
        name="auth-logout",
    ),
    # Main site routes (Django + HTMX + Alpine.js)
    # Rankings is the homepage
    path("", views.HomePageView.as_view(), name="home"),
    path("contact/", views.ContactFormView.as_view(), name="contact"),
    path(
        "contact/thank-you/",
        views.ContactThankYouView.as_view(),
        name="contact_thank_you",
    ),
    # Newsletter unsubscribe (for links in notification emails)
    path(
        "unsubscribe/<str:token>/", views.UnsubscribeView.as_view(), name="unsubscribe"
    ),
    path("download/", views.download_games_csv, name="games-download"),
    # Redirect old URLs to homepage (preserves query params)
    path(
        "rankings/",
        RedirectView.as_view(url="/", permanent=True, query_string=True),
        name="rankings-redirect",
    ),
    path(
        "games/",
        RedirectView.as_view(url="/", permanent=True, query_string=True),
        name="games-redirect",
    ),
    path(
        "games/search/",
        RedirectView.as_view(url="/", permanent=True, query_string=True),
        name="games-search",
    ),
    path("game/<slug:slug>/", views.GameDetailView.as_view(), name="game-detail"),
    path(
        "game/<int:igdb_id>/toggle-played/",
        views.TogglePlayedGameView.as_view(),
        name="toggle-played-game",
    ),
    path("developers/", views.DeveloperListView.as_view(), name="developers-list"),
    path(
        "developers/<slug:slug>/",
        views.DeveloperDetailView.as_view(),
        name="developer-detail",
    ),
    path(
        "developer-alias/<int:id>/",
        views.DeveloperRedirectView.as_view(),
        name="developer-alias-redirect",
    ),
    path("lists/", views.ListListView.as_view(), name="list-list"),
    path("news/", views.NewsListView.as_view(), name="news-list"),
    # Blog/Articles
    path("blog/", views.ArticleListView.as_view(), name="article-list"),
    path("blog/<slug:slug>/", views.ArticleDetailView.as_view(), name="article-detail"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page-detail"),
    # Books app routes (Phase 4.5 will add views)
    path("books/", include("books.urls", namespace="books")),
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

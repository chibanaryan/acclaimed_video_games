from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from games import views
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
    # REST API includes (search endpoints now in app modules)
    path("api/", include("games.api.urls", namespace="games-api")),
    # path("api/books/", include("books.api.urls", namespace="books-api")),
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
    path(
        "import/batch-progress/",
        views.BatchImportProgressView.as_view(),
        name="batch-import-progress",
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
    # SEO ranking pages under /games/ (the bare /games/ redirect above must
    # stay - the client-side filter JS pushes /games/?params URLs whose
    # reloads depend on it). Order matters: browse, then decade (digits+s),
    # then year (digits), then the catch-all slug.
    path("games/browse/", views.BrowseIndexView.as_view(), name="games-browse"),
    re_path(
        r"^games/(?P<decade>\d{3}0)s/$",
        views.DecadeRankingView.as_view(),
        name="games-by-decade",
    ),
    re_path(
        r"^games/(?P<year>\d{4})/$",
        views.YearRankingView.as_view(),
        name="games-by-year",
    ),
    re_path(
        r"^games/(?P<slug>[a-z0-9-]+)/$",
        views.CategoryRankingView.as_view(),
        name="games-by-category",
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
    path("news/", views.news_gone, name="news-list"),
    # Blog/Articles
    path("blog/", views.ArticleListView.as_view(), name="article-list"),
    path("blog/<slug:slug>/", views.ArticleDetailView.as_view(), name="article-detail"),
    path("page/<slug:slug>/", views.PageDetailView.as_view(), name="page-detail"),
    # TODO: Uncomment when books app is enabled on production
    # Books routes (multi-media expansion)
    # path("books/", include("books.urls", namespace="books")),
]

# Forum routes (django-machina) - only mounted when the feature flag is on.
# Machina's apps/migrations are always installed so the tables exist in
# production before the flag is flipped (mirrors the books rollout pattern).
if settings.FORUM_ENABLED:
    from haystack.views import search_view_factory
    from machina import urls as machina_urls

    from games.forum import ForumSearchForm, ForumSearchView

    urlpatterns = [
        # Shadows machina's forum_search:search URL (must come first):
        # the stock form's SearchQuerySet filters return zero results on
        # haystack's simple backend - see games.forum.ForumSearchForm.
        path(
            "forum/search/",
            search_view_factory(view_class=ForumSearchView, form_class=ForumSearchForm),
            name="forum-search",
        ),
        path("forum/", include(machina_urls)),
    ] + urlpatterns

# Books routes - always included, but views require staff access
# Access is controlled at the view level via StaffOnlyMixin / IsStaffOrHide permission
# Search endpoints are now in books/api/urls.py
books_urlpatterns = [
    path("api/books/", include("books.api.urls", namespace="books-api")),
    path("books/", include("books.urls", namespace="books")),
]
urlpatterns = books_urlpatterns + urlpatterns

if settings.DEBUG:
    import debug_toolbar

    from django.views.defaults import page_not_found

    urlpatterns = (
        [
            path("__debug__/", include(debug_toolbar.urls)),
            # Test route to preview custom 404 page
            path(
                "test-404/",
                lambda request: page_not_found(request, Exception("Test 404")),
            ),
            *urlpatterns,
        ]
        + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
        + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    )
else:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

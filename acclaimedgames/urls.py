from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path

from games import views

urlpatterns = [
    path("api/", include("games.api.urls", namespace="games-api")),
    path("admin/", admin.site.urls),
    path("import/", views.ImportView.as_view(), name="import"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    # Beta version routes (new Django + HTMX version)
    path("beta/", include("beta.urls")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
        *urlpatterns,
    ]

# All other urls should get directed to the SPA (must be last!)
# SPAWithPrerenderedView serves pre-rendered HTML files if they exist,
# otherwise falls back to index.html for client-side routing
urlpatterns += [
    re_path(".*", views.SPAWithPrerenderedView.as_view()),
]

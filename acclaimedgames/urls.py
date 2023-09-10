from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from games import views

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('games/', views.GameListView.as_view(), name='games-list'),
    path('developer-aliases/<int:pk>/', views.DeveloperAliasRedirectView.as_view(),
         name='developer-alias-redirect'),
    path('developers/', views.DeveloperListView.as_view(), name='developer-list'),
    path('developers/<int:pk>/', views.DeveloperDetailView.as_view(),
         name='developer-detail'),
    path('lists/', views.ListListView.as_view(), name='list-list'),
    path('publications/', views.PublicationListView.as_view(),
         name='publication-list'),
    path('publications/<slug:slug>/', views.PublicationDetailView.as_view(),
         name='publication-detail'),
    path('games/<int:pk>/', views.GameDetailView.as_view(), name='game-detail'),
    path('import/', views.ImportView.as_view(), name='import'),
    
    path('admin/', admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name='login'),

    path('__debug__/', include('debug_toolbar.urls')),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from games import views

urlpatterns = [
    path('', views.GameListView.as_view(), name='index'),
    path('__debug__/', include('debug_toolbar.urls')),
    path('admin/', admin.site.urls),
    #     path('developer-aliases/<int:pk>/', views.DeveloperAliasRedirectView.as_view(),
    #          name='developer-alias-redirect'),
    path('developer-aliases/<int:pk>/',
         views.DeveloperAliasDetailView.as_view(), name='developer-alias-detail'),
    path('developers/', views.DeveloperListView.as_view(), name='developer-list'),
    path('developers/<int:pk>/', views.DeveloperDetailView.as_view(),
         name='developer-detail'),
    path('lists/', views.ListListView.as_view(), name='list-list'),
    path('publications/', views.PublicationListView.as_view(),
         name='publication-list'),
    path('publications/<int:pk>/', views.PublicationDetailView.as_view(),
         name='publication-detail'),
    path('games/<int:pk>/', views.GameDetailView.as_view(), name='game-detail'),
    path('pages/', include('django.contrib.flatpages.urls')),
    path('platforms/<int:pk>/', views.PlatformDetailView.as_view(),
         name='platform-detail'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

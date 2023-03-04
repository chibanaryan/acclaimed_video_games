from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from games.views import GameDetailView, GameListView, DeveloperDetailView

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', GameListView.as_view(), name='index'),
    path('games/<int:pk>/', GameDetailView.as_view(), name='game-detail'),
    path('developers/<int:pk>/', DeveloperDetailView.as_view(), name='developer-detail'),

    path('__debug__/', include('debug_toolbar.urls')),

]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

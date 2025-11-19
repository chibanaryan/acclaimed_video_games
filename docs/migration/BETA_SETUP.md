# Beta Directory Setup Guide

This guide walks you through setting up the beta directory for parallel development of the Django + HTMX + Alpine.js version.

## Step 1: Create Beta Directory Structure

```bash
# From project root
mkdir -p beta/templates/games/includes
mkdir -p beta/templates/includes
mkdir -p beta/static/beta
```

## Step 2: Create Beta App Files

### Create `beta/__init__.py`
```python
# beta/__init__.py
# Empty file to make beta a Python package
```

### Create `beta/apps.py`
```python
# beta/apps.py
from django.apps import AppConfig

class BetaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'beta'
    verbose_name = 'Beta Version'
```

### Create `beta/urls.py`
```python
# beta/urls.py
from django.urls import path
from . import views

app_name = 'beta'

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('games/', views.GameListView.as_view(), name='games-list'),
    path('games/search/', views.GameSearchView.as_view(), name='games-search'),
    path('game/<slug:slug>/', views.GameDetailView.as_view(), name='game-detail'),
    path('developers/', views.DeveloperListView.as_view(), name='developers-list'),
    path('developers/<slug:slug>/', views.DeveloperDetailView.as_view(), name='developer-detail'),
    path('lists/', views.ListListView.as_view(), name='list-list'),
    path('posts/', views.PostListView.as_view(), name='post-list'),
    path('page/<slug:slug>/', views.PageDetailView.as_view(), name='page-detail'),
]
```

### Create `beta/views.py` (Initial Placeholder)
```python
# beta/views.py
from django.shortcuts import render
from django.views.generic import TemplateView, ListView, DetailView
from games import models

class HomePageView(TemplateView):
    template_name = 'beta/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Add context data
        return context

class GameListView(ListView):
    model = models.Game
    template_name = 'beta/games/game_list.html'
    context_object_name = 'games'
    paginate_by = 100
    
    def get_queryset(self):
        # TODO: Add filtering logic
        return super().get_queryset()

class GameDetailView(DetailView):
    model = models.Game
    template_name = 'beta/games/game_detail.html'
    context_object_name = 'game'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

class GameSearchView(ListView):
    model = models.Game
    template_name = 'beta/games/game_search.html'
    context_object_name = 'games'
    paginate_by = 100
    
    def get_queryset(self):
        # TODO: Add search/filtering logic
        return super().get_queryset()

class DeveloperListView(ListView):
    model = models.DeveloperAlias
    template_name = 'beta/developers/developer_list.html'
    context_object_name = 'developers'
    paginate_by = 100

class DeveloperDetailView(DetailView):
    model = models.Developer
    template_name = 'beta/developers/developer_detail.html'
    context_object_name = 'developer'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

class ListListView(ListView):
    model = models.List
    template_name = 'beta/lists/list_list.html'
    context_object_name = 'lists'
    paginate_by = 100

class PostListView(ListView):
    model = models.Post
    template_name = 'beta/posts/post_list.html'
    context_object_name = 'posts'
    paginate_by = 5

class PageDetailView(TemplateView):
    template_name = 'beta/pages/page_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # TODO: Add page context
        return context
```

## Step 3: Update Main URLs

### Update `acclaimedgames/urls.py`
```python
# acclaimedgames/urls.py
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
```

## Step 4: Register Beta App

### Update `acclaimedgames/settings.py`
```python
# acclaimedgames/settings.py
INSTALLED_APPS = [
    # ... existing apps ...
    'beta',  # Add beta app
    # ... rest of apps ...
]
```

## Step 5: Create Base Template

### Create `beta/templates/base.html`
```django
{# beta/templates/base.html #}
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Acclaimed Games{% endblock %}</title>
    
    {# CRITICAL: These CSS dependencies must match Vue.js version exactly #}
    {# Bulma CSS Framework #}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
    
    {# Bulmaswatch Cyborg Theme (Dark Theme) - MUST INCLUDE #}
    <link rel="stylesheet" href="https://unpkg.com/bulmaswatch/cyborg/bulmaswatch.min.css">
    
    {# Material Design Icons #}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@7.2.96/css/materialdesignicons.min.css">
    
    {# Handjet Font (for rank numbers) - MUST INCLUDE #}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Handjet:wght@800&display=swap" rel="stylesheet">
    
    {# HTMX #}
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    {# Alpine.js #}
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    
    {# Global Styles from App.vue - MUST MATCH EXACTLY #}
    <style>
        html {
            background-color: #000;
        }
        
        header {
            border-bottom: 2px solid;
            margin-bottom: 1em;
        }
        
        section {
            min-height: 800px;
        }
        
        footer {
            min-height: 15em;
            background-color: #444;
            margin-top: 2em;
            padding-top: 2em;
            text-align: center;
            color: #8b8b8b;
        }
        
        footer a {
            color: #8b8b8b;
        }
        
        dl.detail dt {
            font-weight: bold;
            float: left;
            width: 10em;
        }
        
        #content {
            min-height: 1024px;
        }
        
        header,
        .container {
            padding: 0 1em;
        }
        
        .messages {
            position: fixed;
            top: 20px;
            left: 43%;
            right: 43%;
            z-index: 100;
        }
        
        /* Dark theme changes */
        .navbar {
            border: None;
            background-color: transparent;
        }
        
        .table {
            background-color: transparent;
        }
        
        .table.plain th,
        .table.plain td {
            border: none;
        }
        
        .game-row {
            border-bottom: 1px solid #4a4a4a;
        }
        
        .game-header {
            border-bottom: 1px solid #4a4a4a;
            color: #fff;
        }
        
        header,
        footer {
            background-color: #131313;
        }
        
        header {
            border-bottom: 1px solid #4a4a4a;
        }
        
        footer {
            border-top: 1px solid #4a4a4a;
        }
        
        .box {
            background-color: #242424;
            color: rgb(235, 236, 240);
            box-shadow: none;
        }
        
        .title {
            font-weight: 600;
        }
        
        .loading {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
        
        .navbar .navbar-menu {
            background-color: #131313;
        }
        
        a.dropdown-item:hover {
            color: #fff;
        }
    </style>
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <header id="header">
        <div class="container">
            {% include 'beta/includes/_nav.html' %}
        </div>
    </header>
    
    <section>
        <div class="container">
            {% block content %}{% endblock %}
        </div>
    </section>
    
    <footer>
        <div class="container">
            <a href="{% url 'beta:home' %}">Home</a>
            •
            <a href="{% url 'beta:post-list' %}">News</a>
            •
            <a href="{% url 'beta:page-detail' slug='about' %}">About / FAQ</a>
        </div>
    </footer>
    
    {% block extra_scripts %}{% endblock %}
</body>
</html>
```

### Create `beta/templates/includes/_nav.html` (Placeholder)
```django
{# beta/templates/includes/_nav.html #}
<nav class="navbar" role="navigation" aria-label="main navigation">
    <div class="navbar-brand">
        <a href="{% url 'beta:home' %}" class="navbar-item has-text-weight-bold pl-0">
            <img src="/static/avg_logo_small.png" alt="Acclaimed Games">
        </a>
        {# TODO: Add search component #}
        <a href="{% url 'beta:games-list' %}" class="navbar-item">
            Top 1000
        </a>
        {# TODO: Add mobile menu toggle with Alpine.js #}
    </div>
    <div class="navbar-menu">
        <div class="navbar-start">
            <a href="{% url 'beta:developers-list' %}" class="navbar-item">Developers</a>
            <a href="{% url 'beta:list-list' %}" class="navbar-item">Lists</a>
            <a href="{% url 'beta:page-detail' slug='about' %}" class="navbar-item">About</a>
        </div>
    </div>
</nav>
```

## Step 6: Create Placeholder Templates

### Create `beta/templates/home.html`
```django
{# beta/templates/home.html #}
{% extends 'beta/base.html' %}

{% block title %}Acclaimed Games{% endblock %}

{% block content %}
<div class="columns">
    <div class="column">
        <h1>Home Page (Beta)</h1>
        <p>This is the beta version. The Vue.js version is at <a href="/">/</a></p>
        <p>TODO: Migrate HomePage.vue</p>
    </div>
</div>
{% endblock %}
```

### Create `beta/templates/games/game_list.html`
```django
{# beta/templates/games/game_list.html #}
{% extends 'beta/base.html' %}

{% block title %}Games - Acclaimed Games{% endblock %}

{% block content %}
<h1 class="title">Games List (Beta)</h1>
<p>This is the beta version. The Vue.js version is at <a href="/games/">/games/</a></p>
<p>TODO: Migrate GameList.vue</p>

<div id="game-list">
    {# Games will be rendered here #}
    {% for game in games %}
        <div>{{ game.name }} - Rank: {{ game.rank }}</div>
    {% endfor %}
</div>
{% endblock %}
```

## Step 7: Test Setup

1. **Run migrations** (if needed):
   ```bash
   python manage.py migrate
   ```

2. **Start development server**:
   ```bash
   python manage.py runserver
   ```

3. **Test URLs**:
   - Vue.js version: http://localhost:8000/
   - Beta version: http://localhost:8000/beta/
   - Beta games list: http://localhost:8000/beta/games/

4. **Verify both versions work**:
   - Vue.js version should work as before
   - Beta version should show placeholder pages

## Step 8: Directory Structure Checklist

Your final structure should look like:

```
acclaimedgames/
├── beta/
│   ├── __init__.py
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── home.html
│   │   ├── includes/
│   │   │   └── _nav.html
│   │   ├── games/
│   │   │   ├── game_list.html
│   │   │   ├── game_detail.html
│   │   │   └── includes/
│   │   │       ├── _game_row.html
│   │   │       └── ...
│   │   ├── developers/
│   │   │   └── ...
│   │   └── ...
│   └── static/
│       └── beta/
├── frontend/          # Existing Vue.js (unchanged)
├── games/             # Existing Django app (unchanged)
└── ...
```

## Next Steps

1. ✅ Beta directory structure created
2. ✅ Beta URLs configured
3. ✅ Placeholder views and templates created
4. ⏭️ Start migrating components (see MIGRATION_ASSESSMENT.md Phase 1)

## Troubleshooting

### Issue: Beta URLs not working
- Check that `beta` is in `INSTALLED_APPS`
- Verify `path("beta/", include("beta.urls"))` is before the catch-all route
- Check for URL conflicts

### Issue: Templates not found
- Verify template directory structure matches `TEMPLATES` setting
- Check that `beta/templates/` is in `TEMPLATES['DIRS']` or `beta` is in `INSTALLED_APPS`

### Issue: Static files not loading
- Check `STATIC_URL` and `STATIC_ROOT` settings
- Run `python manage.py collectstatic` if needed

## Comparison Testing

To compare pages side-by-side:

1. Open Vue.js version: http://localhost:8000/games/
2. Open Beta version: http://localhost:8000/beta/games/
3. Compare functionality, styling, and behavior
4. Note any differences in a comparison document


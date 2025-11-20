# Vue.js to Django + HTMX + Alpine.js Migration Patterns

This document provides quick reference patterns for common Vue.js to Django + HTMX + Alpine.js migrations.

## Table of Contents
1. [Component Patterns](#component-patterns)
2. [Data Fetching Patterns](#data-fetching-patterns)
3. [State Management Patterns](#state-management-patterns)
4. [Routing Patterns](#routing-patterns)
5. [Form Handling Patterns](#form-handling-patterns)
6. [Event Handling Patterns](#event-handling-patterns)

## Component Patterns

### Vue Component → Django Template Partial

**Vue:**
```vue
<template>
  <div class="game-row">
    <span>{{ game.name }}</span>
    <span>{{ game.rank }}</span>
  </div>
</template>

<script>
export default {
  props: ['game']
}
</script>
```

**Django:**
```django
{# games/templates/games/_game_row.html #}
<div class="game-row">
  <span>{{ game.name }}</span>
  <span>{{ game.rank }}</span>
</div>
```

**Usage:**
```django
{% include 'games/_game_row.html' with game=game_obj %}
```

### Vue Component with Logic → Django Template + View

**Vue:**
```vue
<template>
  <div v-for="game in games" :key="game.id">
    {{ game.name }}
  </div>
</template>

<script>
export default {
  data() {
    return { games: [] }
  },
  async created() {
    const response = await fetch('/api/games/')
    this.games = await response.json()
  }
}
</script>
```

**Django:**
```python
# games/views.py
class GameListView(ListView):
    model = Game
    template_name = 'games/game_list.html'
    context_object_name = 'games'
```

```django
{# games/templates/games/game_list.html #}
{% for game in games %}
  <div>{{ game.name }}</div>
{% endfor %}
```

## Data Fetching Patterns

### Vue API Call → Django View

**Vue:**
```javascript
async created() {
  const response = await fetch('/api/games/')
  const data = await response.json()
  this.games = data.results
}
```

**Django:**
```python
# games/views.py
class GameListView(ListView):
    model = Game
    template_name = 'games/game_list.html'
    
    def get_queryset(self):
        return Game.objects.all()
```

### Vue Filtered API Call → Django Filtered View

**Vue:**
```javascript
async loadItems() {
  const params = new URLSearchParams({
    start: this.filters.start,
    end: this.filters.end
  })
  const response = await fetch(`/api/games/?${params}`)
  const data = await response.json()
  this.items = data.results
}
```

**Django:**
```python
# games/views.py
class GameListView(ListView):
    model = Game
    
    def get_queryset(self):
        qs = Game.objects.all()
        
        start = self.request.GET.get('start')
        if start:
            qs = qs.filter(year_of_release__gte=start)
        
        end = self.request.GET.get('end')
        if end:
            qs = qs.filter(year_of_release__lte=end)
        
        return qs
```

### Vue Debounced Search → HTMX Debounced Request

**Vue:**
```vue
<input v-model="q" @input="loadResults" />
<script>
loadResults: _.debounce(async function() {
  const response = await fetch(`/api/games/?q=${this.q}`)
  // ...
}, 200)
</script>
```

**Django + HTMX:**
```django
<input 
  name="q"
  hx-get="/games/search/"
  hx-target="#results"
  hx-trigger="keyup changed delay:200ms"
  hx-swap="innerHTML"
/>
```

## State Management Patterns

### Vuex Store → Django Context

**Vue:**
```javascript
// store.js
state: {
  genres: [],
  platforms: []
},
actions: {
  async loadGenres({ commit }) {
    const data = await fetch('/api/genres/').then(r => r.json())
    commit('setGenres', data.results)
  }
}
```

**Django:**
```python
# games/views.py
class GameListView(ListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['genres'] = Genre.objects.all()
        context['platforms'] = Platform.objects.all()
        return context
```

### Vue Local State → Alpine.js

**Vue:**
```vue
<template>
  <div>
    <button @click="open = !open">Toggle</button>
    <div v-show="open">Content</div>
  </div>
</template>
<script>
export default {
  data() {
    return { open: false }
  }
}
</script>
```

**Alpine.js:**
```django
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">Content</div>
</div>
```

### Vue Computed Properties → Django Template Tags/Filters

**Vue:**
```vue
<template>
  <div>{{ filteredGames }}</div>
</template>
<script>
computed: {
  filteredGames() {
    return this.games.filter(g => g.year > 2000)
  }
}
</script>
```

**Django:**
```python
# games/templatetags/game_tags.py
@register.filter
def filter_by_year(games, year):
    return [g for g in games if g.year_of_release > year]
```

```django
{% load game_tags %}
<div>
  {% for game in games|filter_by_year:2000 %}
    {{ game.name }}
  {% endfor %}
</div>
```

## Routing Patterns

### Vue Router → Django URLs

**Vue:**
```javascript
// router.js
{
  path: '/games/',
  component: GameList,
  name: 'games-list'
}
```

**Django:**
```python
# games/urls.py
urlpatterns = [
    path('games/', views.GameListView.as_view(), name='games-list'),
]
```

### Vue Router Link → Django URL Tag

**Vue:**
```vue
<router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
  {{ game.name }}
</router-link>
```

**Django:**
```django
<a href="{% url 'game-detail' slug=game.slug %}">
  {{ game.name }}
</a>
```

### Vue Router Navigation → HTMX Navigation

**Vue:**
```javascript
this.$router.push({
  name: 'games-list',
  query: { start: 2000, end: 2010 }
})
```

**Django + HTMX:**
```django
<a 
  href="{% url 'games-list' %}?start=2000&end=2010"
  hx-get="{% url 'games-list' %}?start=2000&end=2010"
  hx-target="#main-content"
  hx-push-url="true"
>
  Filter Games
</a>
```

## Form Handling Patterns

### Vue Form with v-model → Django Form

**Vue:**
```vue
<template>
  <form @submit.prevent="onSubmit">
    <input v-model="filters.year" />
    <input v-model="filters.decade" />
    <button type="submit">Submit</button>
  </form>
</template>
<script>
export default {
  data() {
    return {
      filters: { year: null, decade: null }
    }
  },
  methods: {
    onSubmit() {
      this.$router.push({
        query: this.filters
      })
    }
  }
}
</script>
```

**Django + HTMX:**
```django
<form 
  hx-get="{% url 'games-list' %}"
  hx-target="#game-list"
  hx-push-url="true"
>
  <input name="year" value="{{ request.GET.year }}" />
  <input name="decade" value="{{ request.GET.decade }}" />
  <button type="submit">Submit</button>
</form>
```

### Vue Form with Alpine.js State

**Vue:**
```vue
<template>
  <form>
    <select v-model="filters.genre">
      <option v-for="genre in genres" :value="genre.id">
        {{ genre.name }}
      </option>
    </select>
  </form>
</template>
```

**Django + Alpine.js:**
```django
<form x-data="{ filters: { genre: '{{ request.GET.genre }}' } }">
  <select x-model="filters.genre" name="genre">
    {% for genre in genres %}
      <option value="{{ genre.id }}">{{ genre.name }}</option>
    {% endfor %}
  </select>
</form>
```

## Event Handling Patterns

### Vue @click → HTMX or Alpine.js

**Vue:**
```vue
<button @click="loadMore">Load More</button>
<script>
methods: {
  loadMore() {
    this.offset += 100
    this.loadItems()
  }
}
</script>
```

**HTMX:**
```django
<button 
  hx-get="{% url 'games-list' %}?offset={{ next_offset }}"
  hx-target="#game-list"
  hx-swap="beforeend"
>
  Load More
</button>
```

**Alpine.js:**
```django
<div x-data="{ offset: 0 }">
  <button @click="offset += 100; loadMore()">Load More</button>
</div>
```

### Vue Watchers → HTMX Triggers

**Vue:**
```vue
<template>
  <input v-model="q" />
</template>
<script>
watch: {
  q(val) {
    if (val.length > 2) {
      this.search()
    }
  }
}
</script>
```

**HTMX:**
```django
<input 
  name="q"
  hx-get="{% url 'games-search' %}"
  hx-target="#results"
  hx-trigger="keyup changed delay:300ms"
  hx-include="[name='q']"
/>
```

### Vue Event Emitter → HTMX Events

**Vue:**
```vue
<script>
this.emitter.emit('title', 'New Title')
</script>
```

**HTMX:**
```django
<div 
  hx-get="/games/"
  hx-trigger="load"
  hx-swap="innerHTML"
>
  Content
</div>

<script>
htmx.trigger('body', 'load')
</script>
```

## Conditional Rendering Patterns

### Vue v-if → Django {% if %}

**Vue:**
```vue
<div v-if="games.length > 0">
  <div v-for="game in games">{{ game.name }}</div>
</div>
<div v-else>No games found</div>
```

**Django:**
```django
{% if games %}
  {% for game in games %}
    <div>{{ game.name }}</div>
  {% endfor %}
{% else %}
  <div>No games found</div>
{% endif %}
```

### Vue v-show → Alpine.js x-show

**Vue:**
```vue
<div v-show="isLoading">Loading...</div>
```

**Alpine.js:**
```django
<div x-data="{ isLoading: false }" x-show="isLoading">
  Loading...
</div>
```

## List Rendering Patterns

### Vue v-for → Django {% for %}

**Vue:**
```vue
<div v-for="game in games" :key="game.id">
  {{ game.name }}
</div>
```

**Django:**
```django
{% for game in games %}
  <div>{{ game.name }}</div>
{% endfor %}
```

### Vue v-for with Index → Django {% forloop %}

**Vue:**
```vue
<div v-for="(game, index) in games" :key="game.id">
  {{ index + 1 }}. {{ game.name }}
</div>
```

**Django:**
```django
{% for game in games %}
  <div>{{ forloop.counter }}. {{ game.name }}</div>
{% endfor %}
```

## Pagination Patterns

### Vue Pagination → HTMX Pagination

**Vue:**
```vue
<template>
  <button @click="onPageChange(2)">Page 2</button>
</template>
<script>
methods: {
  onPageChange(page) {
    this.offset = (page - 1) * this.limit
    this.loadItems()
  }
}
</script>
```

**HTMX:**
```django
<a 
  href="?page=2"
  hx-get="?page=2"
  hx-target="#game-list"
  hx-push-url="true"
>
  Page 2
</a>
```

## Search Patterns

### Vue Debounced Search → HTMX Search

**Vue:**
```vue
<input v-model="q" @input="search" />
<script>
search: _.debounce(async function() {
  const response = await fetch(`/api/games/?q=${this.q}`)
  this.results = await response.json()
}, 200)
</script>
```

**HTMX:**
```django
<input 
  name="q"
  hx-get="{% url 'games-search' %}"
  hx-target="#search-results"
  hx-trigger="keyup changed delay:200ms"
  hx-include="[name='q']"
/>

<div id="search-results"></div>
```

## HTMX Middleware Patterns

### HTMX Push URL Middleware

When using `hx-push-url="true"` in templates, HTMX expects the server to return an `HX-Push-URL` header. This middleware ensures that header is present, preventing `htmx:historyCacheError`.

**Implementation:**

```python
# beta/middleware.py
class HTMXPushURLMiddleware:
    """
    Middleware that adds HX-Push-URL header to HTMX responses.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Check if this is an HTMX request
        is_htmx_request = (
            request.META.get("HTTP_HX_REQUEST") == "true"
            or request.headers.get("HX-Request") == "true"
        )

        if is_htmx_request:
            # Check if HX-Push-URL is already set
            hx_push_url = response.get("HX-Push-URL")
            if not hx_push_url:
                # Build the full URL with query parameters
                full_url = request.get_full_path()
                response["HX-Push-URL"] = full_url

        return response
```

**Settings Configuration:**

```python
# acclaimedgames/settings.py
MIDDLEWARE = [
    # ... other middleware
    'beta.middleware.HTMXPushURLMiddleware',
    # ... rest of middleware
]
```

## Pagination Patterns

### Graceful Pagination Error Handling

Override `paginate_queryset()` to handle invalid page numbers gracefully instead of raising 404 errors.

**Pattern:**

```python
# beta/views.py
from django.core.paginator import Paginator, EmptyPage

class GameListView(ListView):
    paginate_by = 100
    paginate_orphans = 0

    def paginate_queryset(self, queryset, page_size):
        """
        Paginate the queryset, and handle invalid page numbers gracefully.
        Instead of raising 404, return the last valid page.
        """
        paginator = Paginator(queryset, page_size, orphans=self.paginate_orphans)
        page = self.request.GET.get("page")

        try:
            page_number = int(page) if page else 1
        except (TypeError, ValueError):
            page_number = 1

        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            # If page is out of range, return the last valid page (or first if no pages)
            if paginator.num_pages > 0:
                page_obj = paginator.page(paginator.num_pages)
            else:
                # No results at all - create an empty page object
                try:
                    page_obj = paginator.page(1)
                except EmptyPage:
                    # Even page 1 is empty - return None and let Django handle it
                    return (paginator, None, [], False)

        return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())
```

**Benefits:**
- Prevents 404 errors when users manually enter invalid page numbers
- Better UX - redirects to last valid page instead of error
- Works well with HTMX pagination

## HTMX Partial Response Patterns

### Returning Partial Templates for HTMX Requests

Use `get_template_names()` to return partial templates when HTMX requests only need content updates, not full page reloads.

**Pattern:**

```python
# beta/views.py
class GameSearchView(ListView):
    template_name = "games/game_search.html"
    
    def get_template_names(self):
        # Support HTMX partial responses - return just the content block if HTMX request
        if self.request.META.get("HTTP_HX_REQUEST") == "true":
            return ["games/includes/_game_search_content.html"]
        return super().get_template_names()
```

**Template Structure:**

```django
{# games/game_search.html - Full page template #}
{% extends 'base.html' %}
{% block content %}
    {% include 'games/includes/_game_search_content.html' %}
{% endblock %}

{# games/includes/_game_search_content.html - Partial template for HTMX #}
<div id="content">
    {# Just the content that needs to be updated #}
    {% for game in games %}
        {% include 'games/includes/_game_row.html' with game=game %}
    {% endfor %}
</div>
```

**HTMX Usage:**

```django
<a 
  href="?page=2"
  hx-get="?page=2"
  hx-target="#content"
  hx-push-url="true"
>
  Page 2
</a>
```

**Benefits:**
- Faster page updates (only content is swapped)
- Maintains browser history with `hx-push-url`
- Reduces server load (smaller responses)
- Better user experience (no full page reload)

## Advanced Filtering Patterns

### Complex Multi-Parameter Filtering

Handle complex filtering with multiple query parameters (genres, platforms, year ranges) with "Any" or "All" logic.

**Pattern:**

```python
# beta/views.py
from django.db.models import Q

class GameSearchView(ListView):
    def get_queryset(self):
        qs = models.Game.objects.prefetch_related(
            "developers",
            "developers__developer",
            "platforms",
            "genres",
        )

        # Basic search by name
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)

        # Year range filtering
        start = self.request.GET.get("start")
        end = self.request.GET.get("end")
        if start:
            qs = qs.filter(year_of_release__gte=int(start))
        if end:
            qs = qs.filter(year_of_release__lte=int(end))

        # Genre filtering with "Any" or "All" option
        genre_option = self.request.GET.get("genre_option", "L")  # L = All, A = Any
        genres = self.request.GET.get("genres")
        if genres:
            genre_ids = [int(x) for x in genres.split(",")]
            if genre_option == "A":  # Any
                q = Q()
                for genre_id in genre_ids:
                    q |= Q(genres=genre_id)
                qs = qs.filter(q)
            else:  # All
                for genre_id in genre_ids:
                    qs = qs.filter(genres=genre_id)

        # Platform filtering
        platforms = self.request.GET.get("platforms")
        if platforms:
            platform_ids = [int(x) for x in platforms.split(",")]
            qs = qs.filter(platforms__in=platform_ids)

        return qs.distinct().order_by("rank")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Build filters dict from query params for template
        filters = {
            "q": self.request.GET.get("q", ""),
            "start": int(self.request.GET.get("start", min_year)),
            "end": int(self.request.GET.get("end", max_year)),
            "genres": [],
            "platforms": [],
            "genre_option": self.request.GET.get("genre_option", "L"),
        }
        
        # Parse selected genres and platforms for display
        genres_param = self.request.GET.get("genres")
        if genres_param:
            genre_ids = [int(x) for x in genres_param.split(",")]
            filters["genres"] = [g for g in all_genres if g["id"] in genre_ids]
        
        context["filters"] = filters
        return context
```

**Template Usage:**

```django
{# Template receives filters dict with current selections #}
<form hx-get="{% url 'beta:games-search' %}" hx-target="#content" hx-push-url="true">
    <input name="q" value="{{ filters.q }}" />
    <input name="start" value="{{ filters.start }}" />
    <input name="end" value="{{ filters.end }}" />
    
    {# Genre selection with "Any" or "All" option #}
    <select name="genre_option">
        <option value="L" {% if filters.genre_option == 'L' %}selected{% endif %}>All</option>
        <option value="A" {% if filters.genre_option == 'A' %}selected{% endif %}>Any</option>
    </select>
    
    {# Multi-select for genres #}
    {% for genre in genres %}
        <input type="checkbox" name="genres" value="{{ genre.id }}" 
               {% if genre.id in filters.genres|map:"id" %}checked{% endif %}>
    {% endfor %}
</form>
```

## External API Integration Patterns

### Graceful IGDB Credential Loading

Handle missing or invalid external API credentials gracefully with proper error handling.

**Pattern:**

```python
# games/igdb.py
import os
from django.conf import settings

def get_igdb_credentials():
    """
    Get IGDB API credentials from settings or environment variables.
    Returns tuple of (client_id, client_secret) or (None, None) if not available.
    """
    client_id = getattr(settings, 'IGDB_CLIENT_ID', None) or os.getenv('IGDB_CLIENT_ID')
    client_secret = getattr(settings, 'IGDB_CLIENT_SECRET', None) or os.getenv('IGDB_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return None, None
    
    return client_id, client_secret

def init_igdb():
    """
    Initialize IGDB API client with proper error handling.
    """
    client_id, client_secret = get_igdb_credentials()
    
    if not client_id or not client_secret:
        # Log warning but don't raise exception
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("IGDB credentials not configured. IGDB features will be disabled.")
        return None
    
    try:
        # Initialize IGDB client
        # ... initialization code ...
        return igdb_client
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to initialize IGDB client: {e}")
        return None
```

**Settings Configuration:**

```python
# acclaimedgames/settings.py
# IGDB API credentials (optional - can be set via environment variables)
IGDB_CLIENT_ID = os.getenv('IGDB_CLIENT_ID', '')
IGDB_CLIENT_SECRET = os.getenv('IGDB_CLIENT_SECRET', '')

# Only enable IGDB if credentials are available
if IGDB_CLIENT_ID and IGDB_CLIENT_SECRET:
    # Configure IGDB settings
    pass
```

**Usage in Views:**

```python
# beta/views.py
from games import igdb

class DeveloperDetailView(DetailView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Safely use IGDB if available
        igdb_client = igdb.init_igdb()
        if igdb_client:
            try:
                context['igdb_data'] = igdb_client.get_developer_data(...)
            except Exception as e:
                # Log error but don't break the page
                logger.error(f"IGDB API error: {e}")
                context['igdb_data'] = None
        else:
            context['igdb_data'] = None
        
        return context
```

**Benefits:**
- Application works even if external API credentials are missing
- Graceful degradation - features that require API are disabled, not broken
- Better error handling and logging
- Easier development/testing without API credentials

## Common Migration Checklist

- [ ] Replace `v-for` with `{% for %}`
- [ ] Replace `v-if` with `{% if %}`
- [ ] Replace `v-show` with `x-show` (Alpine.js)
- [ ] Replace `v-model` with `name` attribute + Alpine.js `x-model` (if needed)
- [ ] Replace `router-link` with `{% url %}` tag
- [ ] Replace `@click` with `@click` (Alpine.js) or HTMX
- [ ] Replace `fetch()` calls with Django views
- [ ] Replace Vuex store with Django context
- [ ] Replace Vue Router with Django URLs
- [ ] Replace Vue computed properties with Django template tags/filters
- [ ] Replace Vue watchers with HTMX triggers
- [ ] Replace Vue lifecycle hooks with Django view methods
- [ ] Add HTMX middleware for push URL support
- [ ] Implement graceful pagination error handling
- [ ] Set up partial template responses for HTMX requests
- [ ] Handle external API credentials gracefully
- [ ] Test all interactions work correctly
- [ ] Verify styling is maintained
- [ ] Check mobile responsiveness


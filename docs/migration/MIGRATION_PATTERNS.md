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
- [ ] Test all interactions work correctly
- [ ] Verify styling is maintained
- [ ] Check mobile responsiveness


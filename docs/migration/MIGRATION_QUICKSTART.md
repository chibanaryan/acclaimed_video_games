# Migration Quick Start Guide

This is a quick reference for the Vue.js to Django + HTMX + Alpine.js migration using the beta directory approach.

## Overview

We're migrating gradually by building the new version in a `beta/` directory while keeping the existing Vue.js app intact. This allows side-by-side comparison and zero-downtime migration.

## Key Documents

1. **MIGRATION_ASSESSMENT.md** - Complete migration strategy and component dependency graph
2. **MIGRATION_PATTERNS.md** - Code examples for common migration patterns
3. **BETA_SETUP.md** - Step-by-step setup guide for beta directory
4. **This file** - Quick reference

## Quick Start

### 1. Set Up Beta Directory

Follow `BETA_SETUP.md` to:
- Create `beta/` directory structure
- Set up beta URLs (`/beta/` routes)
- Create placeholder views and templates
- Test that both `/` (Vue) and `/beta/` (new) work

### 2. Access Both Versions

- **Vue.js version**: http://localhost:8000/
- **Beta version**: http://localhost:8000/beta/

### 3. Migration Workflow

For each component/page:

1. **Migrate** component to `beta/templates/`
2. **Test** at `/beta/` route
3. **Compare** with Vue version at `/` route
4. **Document** any differences
5. **Fix** any issues
6. **Move on** to next component

### 4. Migration Order (Leaf-to-Root)

Start with simplest components, work up to complex:

1. **Level 0 (Leaves)**: `GameRowProperties`, `PaginationComponent`, `PostItem`, etc.
2. **Level 1**: `GameRow`, `SimpleFilters`, `PostList`
3. **Level 2**: `GameDetail`, `DeveloperDetail`, `AdvancedFilters`
4. **Level 3**: `GameList`, `GameSearch`
5. **Level 4**: `HomePage`, `NavComponent`
6. **Level 5**: Base template, URL routing

See `MIGRATION_ASSESSMENT.md` for complete dependency graph.

## Common Tasks

### Creating a New Beta Template

```django
{# beta/templates/games/game_list.html #}
{% extends 'beta/base.html' %}

{% block title %}Games - Acclaimed Games{% endblock %}

{% block content %}
<h1 class="title">Games</h1>
{% include 'beta/games/includes/_game_row.html' with game=game %}
{% endblock %}
```

### Adding HTMX to a Template

```django
<a 
  hx-get="{% url 'beta:games-list' %}?page=2"
  hx-target="#game-list"
  hx-swap="innerHTML"
  hx-push-url="true"
>
  Next Page
</a>
```

### Adding Alpine.js to a Template

```django
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">Content</div>
</div>
```

### Creating a Beta View

```python
# beta/views.py
from django.views.generic import ListView
from games import models

class GameListView(ListView):
    model = models.Game
    template_name = 'beta/games/game_list.html'
    context_object_name = 'games'
    paginate_by = 100
```

### Adding a Beta URL

```python
# beta/urls.py
path('games/', views.GameListView.as_view(), name='games-list'),
```

## Testing Checklist

For each migrated page:

- [ ] Page loads at `/beta/` route
- [ ] Styling matches Vue version
- [ ] All links work correctly
- [ ] Forms submit correctly (if applicable)
- [ ] HTMX interactions work (if applicable)
- [ ] Alpine.js interactions work (if applicable)
- [ ] Mobile responsive
- [ ] No console errors
- [ ] Performance is acceptable

## Comparison Testing

1. Open Vue version: http://localhost:8000/games/
2. Open Beta version: http://localhost:8000/beta/games/
3. Compare:
   - Visual appearance
   - Functionality
   - Performance
   - User experience

## Common Issues

### Templates not found
- Check template path matches `template_name` in view
- Verify `beta/templates/` structure is correct

### URLs not working
- Check `beta/urls.py` has the route
- Verify `path("beta/", include("beta.urls"))` is in main `urls.py`
- Ensure beta route is before SPA catch-all

### HTMX not working
- Check HTMX script is loaded in base template
- Verify `hx-target` element exists
- Check browser console for errors

### Alpine.js not working
- Check Alpine.js script is loaded in base template
- Verify `x-data` is properly formatted
- Check browser console for errors

## Final Switchover

When all pages are migrated and tested:

1. Follow "Final Switchover Process" in `MIGRATION_ASSESSMENT.md`
2. Move beta templates/views to main
3. Update URLs to remove `/beta/` prefix
4. Remove SPA catch-all route
5. Test thoroughly
6. Deploy

## Resources

- [HTMX Docs](https://htmx.org/docs/)
- [Alpine.js Docs](https://alpinejs.dev/)
- [Django Templates](https://docs.djangoproject.com/en/stable/topics/templates/)
- [Django Class-Based Views](https://docs.djangoproject.com/en/stable/topics/class-based-views/)

## Getting Help

- Check `MIGRATION_PATTERNS.md` for code examples
- Review `MIGRATION_ASSESSMENT.md` for detailed strategy
- Compare with Vue.js version for reference


# Vue.js to Django + HTMX + Alpine.js Migration Assessment

## Executive Summary

This document provides a comprehensive assessment for migrating the Acclaimed Games website from a Vue.js SPA architecture to a Django + HTMX + Alpine.js architecture. The migration strategy follows a **leaf-to-root** approach, starting with the simplest components (leaves) and working up to the most complex (root).

## Parallel Development Strategy

### Beta Directory Approach

To enable gradual migration with side-by-side comparison, we will:

1. **Keep existing Vue.js app intact** in the current structure
2. **Build new Django + HTMX + Alpine.js version** in a `beta/` directory
3. **Route both versions** through Django URLs (e.g., `/` for Vue, `/beta/` for new version)
4. **Compare pages** during development to ensure feature parity
5. **Switch over** by moving beta to main when migration is complete

### Directory Structure

```
acclaimedgames/
├── frontend/                    # Existing Vue.js app (unchanged)
│   ├── src/
│   └── ...
├── games/                       # Existing Django app
│   ├── templates/
│   │   └── games/              # Existing templates
│   └── ...
├── beta/                        # NEW: Django + HTMX + Alpine.js version
│   ├── templates/
│   │   ├── base.html           # New base template
│   │   ├── games/
│   │   │   ├── game_list.html
│   │   │   ├── game_detail.html
│   │   │   └── includes/
│   │   │       ├── _game_row.html
│   │   │       └── ...
│   │   └── ...
│   ├── views.py                 # New views for beta version
│   └── urls.py                  # Beta URL patterns
└── ...
```

### URL Routing Strategy

**Django URLs Configuration:**
```python
# acclaimedgames/urls.py
urlpatterns = [
    path("api/", include("games.api.urls")),
    path("admin/", admin.site.urls),
    
    # Beta version routes (new Django + HTMX version)
    path("beta/", include("beta.urls")),
    
    # Existing Vue.js SPA (catch-all, must be last)
    re_path(".*", views.SPAWithPrerenderedView.as_view()),
]
```

**Beta URLs:**
```python
# beta/urls.py
urlpatterns = [
    path("", views.HomePageView.as_view(), name="beta-home"),
    path("games/", views.GameListView.as_view(), name="beta-games-list"),
    path("game/<slug:slug>/", views.GameDetailView.as_view(), name="beta-game-detail"),
    # ... other routes
]
```

### Accessing Both Versions

- **Current Vue.js version**: `http://localhost:8000/` (unchanged)
- **New Django + HTMX version**: `http://localhost:8000/beta/`
- **Comparison**: Open both in browser tabs to compare side-by-side

### Benefits of This Approach

1. **Zero downtime**: Current site remains fully functional
2. **Gradual migration**: Migrate one page/component at a time
3. **Easy comparison**: View both versions simultaneously
4. **Rollback safety**: Can always revert to Vue.js version
5. **Testing**: Test new version without affecting production
6. **Incremental deployment**: Deploy beta to production for testing before final switch

### Migration Workflow

1. **Create beta directory structure**
2. **Set up beta URLs** (all routes under `/beta/`)
3. **Migrate components incrementally** (one at a time)
4. **Test each migrated page** by comparing with Vue version
5. **Continue until all pages migrated**
6. **Final switchover**: Move beta templates/views to main, update URLs

### Final Switchover Process

When migration is complete and beta version is fully tested:

#### Pre-Switchover Checklist
- [ ] All pages migrated and tested in beta
- [ ] All functionality verified in beta version
- [ ] Performance benchmarks met
- [ ] SEO verified (meta tags, structured data)
- [ ] Mobile responsiveness confirmed
- [ ] Browser compatibility tested
- [ ] Backup current production code

#### Switchover Steps

1. **Backup current Vue.js app** (create a backup branch or tag)
   ```bash
   git tag vue-version-backup
   git push origin vue-version-backup
   ```

2. **Move beta templates to main**
   ```bash
   # Move templates
   mv beta/templates/* games/templates/
   # Or merge if games/templates already exists
   cp -r beta/templates/* games/templates/
   ```

3. **Move beta views to main**
   ```python
   # Option A: Replace games/views.py
   # Copy beta/views.py content to games/views.py
   
   # Option B: Create separate module
   # Keep beta views in games/views_beta.py and import
   ```

4. **Update URL patterns**
   ```python
   # acclaimedgames/urls.py
   # Remove beta route:
   # path("beta/", include("beta.urls")),  # Remove this
   
   # Update main routes to use new views:
   urlpatterns = [
       path("api/", include("games.api.urls")),
       path("admin/", admin.site.urls),
       path("", views.HomePageView.as_view(), name="home"),  # New
       path("games/", views.GameListView.as_view(), name="games-list"),  # New
       # ... all other routes
   ]
   
   # Remove SPA catch-all:
   # re_path(".*", views.SPAWithPrerenderedView.as_view()),  # Remove this
   ```

5. **Update template references**
   - Update all `{% url 'beta:...' %}` to `{% url '...' %}`
   - Update template extends from `beta/base.html` to `base.html`
   - Update includes from `beta/includes/` to `includes/`

6. **Remove Vue.js build step from deployment**
   - Update `Procfile` (if using Heroku)
   - Remove `npm run build` from deployment scripts
   - Update `collectstatic` to not include Vue dist files

7. **Clean up**
   ```bash
   # Option A: Remove beta directory
   rm -rf beta/
   
   # Option B: Archive for reference
   mv beta/ beta_archive/
   ```

8. **Update settings**
   ```python
   # acclaimedgames/settings.py
   # Remove 'beta' from INSTALLED_APPS (if you added it)
   ```

9. **Test locally**
   - Test all routes work correctly
   - Test all functionality
   - Compare with beta version one last time

10. **Deploy to staging** (if you have staging environment)
    - Deploy and test thoroughly
    - Get stakeholder approval

11. **Deploy to production**
    - Deploy during low-traffic period
    - Monitor for errors
    - Have rollback plan ready

#### Rollback Plan

If issues arise after switchover:

1. **Quick rollback**: Revert to Vue.js version
   ```bash
   git revert <switchover-commit>
   # Or
   git checkout vue-version-backup
   ```

2. **Restore SPA routing**:
   ```python
   # Restore SPA catch-all route
   urlpatterns += [
       re_path(".*", views.SPAWithPrerenderedView.as_view()),
   ]
   ```

3. **Restore Vue.js build** in deployment

#### Post-Switchover

- [ ] Monitor error logs
- [ ] Monitor performance metrics
- [ ] Gather user feedback
- [ ] Document any issues found
- [ ] Plan fixes for any issues

## Migration Progress

### ✅ Completed (2025-11-19)

**Page-Level Components:**
- ✅ `HomePage.vue` → `beta/templates/home.html` (fully migrated with visual parity)

**Navigation:**
- ✅ `NavComponent.vue` → `beta/templates/includes/_nav.html` (fully functional with search, mobile menu)

**Leaf Components (Level 0):**
- ✅ `GameRowProperties.vue` → `beta/templates/games/includes/_game_row_properties.html`
- ✅ `PostItem.vue` → `beta/templates/posts/includes/_post_item.html`
- ✅ `SnippetComponent.vue` → `beta/templates/includes/_snippet.html`

**Infrastructure:**
- ✅ Base template with all dependencies (Bulma, Bulmaswatch, HTMX, Alpine.js)
- ✅ Custom template filter: `from_now` (matching moment.js behavior)
- ✅ Django views and URLs for all routes
- ✅ Visual parity fixes (navbar height, hover effects, search styling, mobile menu)

### 🚧 In Progress

**Remaining Leaf Components:**
- [x] `PaginationComponent.vue` ✅
- [x] `ListResultsComponent.vue` ✅
- [x] `GameSearchResult.vue` ✅
- [x] `SelectableTagList.vue` ✅ (template created)
- [x] `RangeSlider.vue` ✅ (template created)
- [x] `SearchInput.vue` ✅ (template created)
- [x] `MultiSelectComponent.vue` ✅ (template created)
- [x] `GameProperties.vue` ✅

**Composition Components:**
- [x] `GameRow.vue` (depends on GameRowProperties ✅) ✅
- [x] `SimpleFilters.vue` ✅
- [x] `PostList.vue` (depends on PostItem ✅) ✅
- [x] `AdvancedFilters.vue` ✅ (template created)

**Page-Level Components:**
- [x] `GameList.vue` ✅
- [x] `GameDetail.vue` ✅
- [x] `GameSearch.vue` ✅
- [x] `DeveloperDetail.vue` ✅
- [x] `DeveloperList.vue` ✅
- [x] `ListList.vue` ✅

## Component Dependency Graph

### Dependency Hierarchy (Leaf to Root)

```
Level 0 (Leaves - No Vue Component Dependencies):
├── GameRowProperties.vue          [Pure presentation]
├── GameProperties.vue               [Pure presentation]
├── PaginationComponent.vue         [Pure presentation]
├── PostItem.vue                    [Pure presentation]
├── ListResultsComponent.vue        [Pure presentation]
├── GameSearchResult.vue            [Pure presentation]
├── SelectableTagList.vue           [Pure presentation]
├── RangeSlider.vue                 [Pure presentation]
├── SearchInput.vue                  [Pure presentation]
├── MultiSelectComponent.vue        [Pure presentation]
└── SnippetComponent.vue             [Fetches data, but no child components]

Level 1 (Simple Compositions):
├── GameRow.vue                      [Uses: GameRowProperties]
├── SimpleFilters.vue                [Uses: meta from store, no child components]
└── PostList.vue                     [Uses: PostItem, BaseListComponent mixin]

Level 2 (Medium Complexity):
├── GameDetail.vue                   [Uses: GameProperties, ListResultsComponent]
├── DeveloperList.vue                [Uses: PaginationComponent, BaseListComponent]
├── ListList.vue                     [Uses: ListResultsComponent, PaginationComponent, BaseListComponent]
├── AdvancedFilters.vue              [Uses: MultiSelectComponent, RangeSlider, SearchInput, SelectableTagList]
└── GameSearchComponent.vue           [Uses: GameSearchResult]

Level 3 (Complex Compositions):
├── GameList.vue                     [Uses: GameRow, PaginationComponent, SimpleFilters]
├── GameSearch.vue                   [Uses: AdvancedFilters, GameRow, PaginationComponent]
└── DeveloperDetail.vue               [Uses: GameRow]

Level 4 (Page-Level Components):
├── HomePage.vue                     [Uses: SnippetComponent, PostItem]
└── NavComponent.vue                 [Uses: GameSearchComponent]

Level 5 (Root):
└── App.vue                          [Uses: NavComponent, RouterView]
```

### Component Data Dependencies

| Component | Data Source | API Endpoint |
|-----------|-------------|--------------|
| HomePage | API | `/api/posts/`, `/api/games/`, `/api/meta/` |
| GameList | API | `/api/games/` |
| GameDetail | API | `/api/games/<slug>/` |
| GameSearch | API | `/api/games/` (with filters) |
| DeveloperDetail | API | `/api/developers/<slug>/`, `/api/games/?developer=...` |
| DeveloperList | API | `/api/developer-aliases/` |
| PostList | API | `/api/posts/` |
| ListList | API | `/api/lists/`, `/api/publications/` |
| SimpleFilters | Store | `/api/meta/` (cached) |
| AdvancedFilters | Props | Genres/Platforms from parent |
| GameSearchComponent | API | `/api/games/?q=...&limit=5` |
| SnippetComponent | API | `/api/snippets/<slug>/` |

## Migration Strategy: Leaf-to-Root Approach

### Phase 1: Leaf Components (Level 0)
**Goal**: Convert pure presentation components to Django templates with minimal Alpine.js

**Components to Migrate:**
1. `GameRowProperties.vue` → Django template partial
2. `GameProperties.vue` → Django template partial
3. `PaginationComponent.vue` → Django template partial (HTMX for navigation)
4. `PostItem.vue` → Django template partial
5. `ListResultsComponent.vue` → Django template partial
6. `GameSearchResult.vue` → Django template partial
7. `SelectableTagList.vue` → Django template + Alpine.js (for interactivity)
8. `RangeSlider.vue` → Django template + Alpine.js
9. `SearchInput.vue` → Django template + Alpine.js
10. `MultiSelectComponent.vue` → Django template + Alpine.js
11. `SnippetComponent.vue` → Django template partial (server-side include)

**Migration Pattern:**
- Convert Vue template to Django template
- Remove Vue-specific directives (`v-for`, `v-if`, etc.)
- Use Django template tags (`{% for %}`, `{% if %}`, etc.)
- For interactive components, add Alpine.js for client-side behavior
- Replace `router-link` with regular `<a>` tags or HTMX attributes

### Phase 2: Simple Compositions (Level 1)
**Goal**: Convert components that compose leaf components

**Components to Migrate:**
1. `GameRow.vue` → Django template (includes `GameRowProperties` partial)
2. `SimpleFilters.vue` → Django template + Alpine.js (for form state)
3. `PostList.vue` → Django view + template (uses `PostItem` partial)

**Migration Pattern:**
- Create Django views for data fetching
- Use Django templates with `{% include %}` for child components
- Use HTMX for filter changes (replace content dynamically)
- Use Alpine.js for local state management (form values, UI state)

### Phase 3: Medium Complexity (Level 2)
**Goal**: Convert components with multiple dependencies

**Components to Migrate:**
1. `GameDetail.vue` → Django view + template
2. `DeveloperDetail.vue` → Django view + template
3. `DeveloperList.vue` → Django view + template
4. `ListList.vue` → Django view + template
5. `AdvancedFilters.vue` → Django template + Alpine.js
6. `GameSearchComponent.vue` → Django template + HTMX + Alpine.js

**Migration Pattern:**
- Create Django class-based views (DetailView, ListView)
- Use HTMX for:
  - Search-as-you-type (GameSearchComponent)
  - Filter updates (AdvancedFilters)
  - Pagination
- Use Alpine.js for:
  - Dropdown menus
  - Form state
  - UI interactions (show/hide, active states)

### Phase 4: Complex Compositions (Level 3)
**Goal**: Convert page-level components with complex interactions

**Components to Migrate:**
1. `GameList.vue` → Django view + template
2. `GameSearch.vue` → Django view + template

**Migration Pattern:**
- Create Django views with filtering logic
- Use HTMX for:
  - Filter changes (replace game list)
  - Pagination (replace game list)
  - URL updates (hx-push-url)
- Use Alpine.js for:
  - Filter form state
  - Scroll position management
  - Highlight animations

### Phase 5: Page-Level Components (Level 4)
**Goal**: Convert top-level page components

**Components to Migrate:**
1. `HomePage.vue` → Django view + template
2. `NavComponent.vue` → Django template partial (base template)

**Migration Pattern:**
- Create Django views for each page
- Use base template with navigation partial
- Use HTMX for navigation (if needed for SPA-like feel)
- Use Alpine.js for mobile menu toggle

### Phase 6: Root Component (Level 5)
**Goal**: Replace Vue Router with Django URL routing

**Component to Migrate:**
1. `App.vue` → Django base template

**Migration Pattern:**
- Replace Vue Router with Django URL patterns
- Use Django's template inheritance
- Remove Vuex store (replace with Django context)
- Remove Vue Router navigation guards (replace with Django middleware if needed)

## Detailed Migration Recommendations

### 1. HTMX Integration Strategy

**When to Use HTMX:**
- **Pagination**: Replace list content without full page reload
- **Filtering**: Update results based on filter changes
- **Search**: Replace search results dynamically
- **Form submissions**: Submit forms without page reload
- **Navigation**: For SPA-like feel (optional, can use regular links)

**HTMX Attributes to Use:**
```html
<!-- Pagination -->
<a hx-get="/games/?page=2" hx-target="#game-list" hx-swap="innerHTML" hx-push-url="true">Next</a>

<!-- Filtering -->
<form hx-get="/games/" hx-target="#game-list" hx-swap="innerHTML" hx-push-url="true">
  <!-- filter inputs -->
</form>

<!-- Search -->
<input hx-get="/games/search/" hx-target="#search-results" hx-trigger="keyup changed delay:200ms">
```

### 2. Alpine.js Integration Strategy

**When to Use Alpine.js:**
- **Form state management**: Track form values, validation
- **UI interactions**: Dropdowns, modals, mobile menus
- **Client-side filtering**: Filter already-loaded data
- **Animations**: Transitions, highlights
- **Scroll position**: Remember scroll position (replaces Vuex)

**Alpine.js Patterns:**
```html
<!-- Mobile menu toggle -->
<div x-data="{ open: false }">
  <button @click="open = !open">Menu</button>
  <div x-show="open">Menu content</div>
</div>

<!-- Form state -->
<form x-data="{ filters: { year: null, decade: null } }">
  <select x-model="filters.year">...</select>
</form>
```

### 3. Django View Structure

**Recommended View Classes:**
- `ListView` for list pages (GameList, DeveloperList, PostList, ListList)
- `DetailView` for detail pages (GameDetail, DeveloperDetail)
- `TemplateView` for static pages (HomePage)
- Custom views for complex filtering (GameSearch)

**Example Structure:**
```python
# games/views.py
class GameListView(ListView):
    model = Game
    template_name = 'games/game_list.html'
    context_object_name = 'games'
    paginate_by = 100
    
    def get_queryset(self):
        # Filtering logic
        return super().get_queryset()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add filters, meta, etc.
        return context
```

### 4. Template Organization

**Recommended Structure:**
```
games/templates/
├── games/
│   ├── base.html              # Base template (replaces App.vue)
│   ├── _nav.html              # Navigation partial (replaces NavComponent)
│   ├── game_list.html         # Game list page
│   ├── game_detail.html       # Game detail page
│   ├── _game_row.html         # Game row partial (replaces GameRow)
│   ├── _game_properties.html  # Game properties partial
│   ├── _pagination.html       # Pagination partial
│   └── ...
└── includes/
    ├── _filters.html          # Filter components
    └── ...
```

### 5. URL Routing

**Replace Vue Router with Django URLs:**
```python
# games/urls.py
urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('games/', views.GameListView.as_view(), name='games-list'),
    path('games/search/', views.GameSearchView.as_view(), name='games-search'),
    path('game/<slug:slug>/', views.GameDetailView.as_view(), name='game-detail'),
    path('developers/', views.DeveloperListView.as_view(), name='developers-list'),
    path('developers/<slug:slug>/', views.DeveloperDetailView.as_view(), name='developer-detail'),
    # ... etc
]
```

### 6. State Management Replacement

**Vuex Store → Django Context:**
- **Genres/Platforms**: Load in view context (can cache with Django cache framework)
- **Meta data**: Load in view context or use template tags
- **Game/Developer caching**: Use Django cache framework instead of Vuex
- **Scroll position**: Use Alpine.js with localStorage

### 7. API Endpoints

**Keep or Remove?**
- **Option A**: Keep API endpoints, use HTMX to fetch HTML fragments
- **Option B**: Remove API endpoints, render HTML directly in views
- **Recommendation**: Keep API endpoints for now (easier migration), can remove later

**HTMX with API:**
```python
# Return HTML fragments for HTMX requests
def get(self, request, *args, **kwargs):
    if request.headers.get('HX-Request'):
        # Return partial template
        return render(request, 'games/_game_list.html', context)
    else:
        # Return full page
        return render(request, 'games/game_list.html', context)
```

## Migration Phases Timeline

### Phase 0: Beta Setup (Week 1, Days 1-2)
- [x] Create `beta/` directory structure
- [x] Create `beta/__init__.py` and `beta/urls.py`
- [x] Create `beta/templates/` directory structure
- [x] Set up base template with HTMX and Alpine.js
- [x] Configure Django URLs to route `/beta/` to beta app
- [x] Test that both `/` (Vue) and `/beta/` (new) are accessible
- [x] Create initial beta views (views for all routes exist, but templates are incomplete - only `home.html` and `games/game_list.html` have templates)

### Phase 1: Preparation (Week 1, Days 3-5)
- [x] Set up HTMX and Alpine.js in beta templates
- [x] Create base template structure in `beta/templates/`
- [x] Set up Django views for all routes in `beta/views.py` (all 9 routes have views)
- [x] Create template partials directory structure (`beta/templates/includes/`)
- [ ] Create templates for all routes (only `home.html` and `games/game_list.html` exist; missing: `game_detail.html`, `game_search.html`, `developer_list.html`, `developer_detail.html`, `list_list.html`, `post_list.html`, `page_detail.html`)
- [x] Set up static files for beta (if needed) - Using CDN, no static files needed

### Phase 2: Leaf Components (Week 2-3)
- [x] Migrate all Level 0 components to `beta/templates/includes/` - **Partially complete**: GameRowProperties ✅, PostItem ✅, SnippetComponent ✅ (3 of 11 done)
- [x] Test each component in isolation at `/beta/`
- [x] Compare with Vue version at `/` to ensure styling matches
- [x] Document any differences found

### Phase 3: Simple Compositions (Week 4)
- [ ] Migrate Level 1 components to `beta/templates/`
- [ ] Integrate with leaf components using `{% include %}`
- [ ] Test interactions at `/beta/`
- [ ] Compare functionality with Vue version

### Phase 4: Medium Complexity (Week 5-6)
- [ ] Migrate Level 2 components to `beta/templates/`
- [ ] Implement HTMX for dynamic updates in beta views
- [ ] Test filtering and search at `/beta/`
- [ ] Side-by-side comparison with Vue version

### Phase 5: Complex Compositions (Week 7)
- [ ] Migrate Level 3 components to `beta/templates/`
- [ ] Implement complex HTMX interactions in beta views
- [ ] Test pagination and filtering together at `/beta/`
- [ ] Comprehensive comparison with Vue version

### Phase 6: Page-Level (Week 8)
- [x] Migrate Level 4 components to `beta/templates/` - **Partially complete**: HomePage ✅, NavComponent ✅ (2 of 2 done)
- [x] Create navigation system in `beta/templates/includes/_nav.html`
- [x] Test full page flows at `/beta/` - HomePage fully tested
- [x] End-to-end comparison with Vue version - HomePage visual parity achieved

### Phase 7: Root & Cleanup (Week 9)
- [ ] Complete all beta migrations
- [ ] Final testing of beta version at `/beta/`
- [ ] Prepare for switchover (see Final Switchover Process below)
- [ ] Document any remaining differences

### Phase 8: Final Switchover (Week 10)
- [ ] Execute final switchover (see process below)
- [ ] Full regression testing of main site
- [ ] Performance optimization
- [ ] SEO verification
- [ ] Mobile responsiveness testing
- [ ] Remove or archive beta directory

## Maintaining Visual Parity (CRITICAL)

**This is the highest priority requirement**: The migrated version must look **exactly** like the Vue.js version, down to pixel-level accuracy.

### Visual Parity Checklist

**✅ Completed Components (HomePage, NavComponent, PostItem, SnippetComponent, GameRowProperties):**
- [x] **HTML structure** matches exactly (same divs, classes, nesting)
- [x] **CSS styles** match exactly (colors, fonts, spacing, borders)
- [x] **Fonts** match exactly (family, weight, size)
- [x] **Colors** match exactly (hex codes, RGB values)
- [x] **Spacing** matches exactly (padding, margin, gaps)
- [x] **Borders** match exactly (width, style, color)
- [x] **Layout** matches exactly (flexbox, grid, positioning)
- [x] **Responsive behavior** matches exactly (mobile, tablet, desktop)
- [x] **Hover states** match exactly
- [x] **Transitions/animations** match exactly

**For remaining components to migrate, verify:**
- [ ] **HTML structure** matches exactly (same divs, classes, nesting)
- [ ] **CSS styles** match exactly (colors, fonts, spacing, borders)
- [ ] **Fonts** match exactly (family, weight, size)
- [ ] **Colors** match exactly (hex codes, RGB values)
- [ ] **Spacing** matches exactly (padding, margin, gaps)
- [ ] **Borders** match exactly (width, style, color)
- [ ] **Layout** matches exactly (flexbox, grid, positioning)
- [ ] **Responsive behavior** matches exactly (mobile, tablet, desktop)
- [ ] **Hover states** match exactly
- [ ] **Transitions/animations** match exactly

### Required CSS Dependencies

The Vue.js app uses these CSS frameworks and fonts. **You must include all of them** in the beta base template:

```django
{# beta/templates/base.html #}
<head>
    {# Bulma CSS Framework #}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.4/css/bulma.min.css">
    
    {# Bulmaswatch Cyborg Theme (Dark Theme) #}
    <link rel="stylesheet" href="https://unpkg.com/bulmaswatch/cyborg/bulmaswatch.min.css">
    
    {# Material Design Icons #}
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@mdi/font@7.2.96/css/materialdesignicons.min.css">
    
    {# Handjet Font (for rank numbers) #}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Handjet:wght@800&display=swap" rel="stylesheet">
    
    {# Global Styles (from App.vue) #}
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
</head>
```

### Component-Specific Styles

Each Vue component has its own `<style>` section. **You must copy these exactly** to your Django templates.

#### Extraction Process

1. **For each component**, extract the `<style>` section from the `.vue` file
2. **Copy the styles** to a corresponding CSS file or `<style>` block in the Django template
3. **Maintain scoped styles** - if Vue component uses `scoped`, ensure styles only apply to that component
4. **Preserve SASS syntax** - if component uses `lang="sass"`, convert to CSS or use SASS in Django

#### Example: GameRow Component

**Vue Component Styles:**
```sass
// frontend/src/components/GameRow.vue
<style lang="sass" scoped>
.game-row 
    border-bottom: 1px solid #616161

    .thumbnail img 
        max-width: inherit

    &.desktop
        .rank 
            text-align: center
            display: flex
            align-items: center
            justify-content: center
            color: #fff
            font-family: Handjet, sans-serif
            font-weight: 800
            text-shadow: -3px 3px 0px #5d5b5b
            min-width: 122px
            font-size: 60px

    &.mobile
        .rank 
            color: #fff
            font-family: Handjet, sans-serif
            font-weight: 800
            text-shadow: -2px 2px 0px #5d5b5b
            font-size: 25px
            margin-right: 5px
            vertical-align: middle

    &.highlight
        background: #393939
</style>
```

**Django Template Styles:**
```django
{# beta/templates/games/includes/_game_row.html #}
<style>
.game-row {
    border-bottom: 1px solid #616161;
}

.game-row .thumbnail img {
    max-width: inherit;
}

.game-row.desktop .rank {
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-family: Handjet, sans-serif;
    font-weight: 800;
    text-shadow: -3px 3px 0px #5d5b5b;
    min-width: 122px;
    font-size: 60px;
}

.game-row.mobile .rank {
    color: #fff;
    font-family: Handjet, sans-serif;
    font-weight: 800;
    text-shadow: -2px 2px 0px #5d5b5b;
    font-size: 25px;
    margin-right: 5px;
    vertical-align: middle;
}

.game-row.highlight {
    background: #393939;
}
</style>

<div class="game-row {% if highlight %}highlight{% endif %}">
    {# HTML content #}
</div>
```

### HTML Structure Matching

**Critical**: The HTML structure must match **exactly**, including:
- Same element types (`<div>`, `<span>`, etc.)
- Same class names
- Same nesting structure
- Same data attributes (if any)
- Same IDs (if any)

#### Example: Matching HTML Structure

**Vue Template:**
```vue
<template>
  <div class="columns is-hidden-mobile game-row desktop" :id="`game-${game.id}`">
    <div class="column is-narrow">
      <div class="columns">
        <div v-if="showRank == 'alltime'" class="column is-narrow">
          <span class="rank">{{ game.rank }}</span>
        </div>
        <div class="column is-narrow">
          <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }">
            <img :src="game.thumbnail" />
          </router-link>
        </div>
      </div>
    </div>
    <div class="column">
      <div>
        <router-link :to="{ name: 'game-detail', params: { slug: game.slug } }"
          class="game-name has-text-weight-bold is-size-6 mb-3">
          {{ game.name }}
        </router-link>
      </div>
    </div>
  </div>
</template>
```

**Django Template (Must Match Exactly):**
```django
<div class="columns is-hidden-mobile game-row desktop" id="game-{{ game.id }}">
    <div class="column is-narrow">
        <div class="columns">
            {% if show_rank == 'alltime' %}
            <div class="column is-narrow">
                <span class="rank">{{ game.rank }}</span>
            </div>
            {% endif %}
            <div class="column is-narrow">
                <a href="{% url 'beta:game-detail' slug=game.slug %}">
                    <img src="{{ game.thumbnail }}" />
                </a>
            </div>
        </div>
    </div>
    <div class="column">
        <div>
            <a href="{% url 'beta:game-detail' slug=game.slug %}"
               class="game-name has-text-weight-bold is-size-6 mb-3">
                {{ game.name }}
            </a>
        </div>
    </div>
</div>
```

### Color Matching

**Extract all color values** from Vue components and use them exactly:

- Background colors: `#000`, `#131313`, `#242424`, `#444`, `#393939`, `#4a4a4a`, `#616161`
- Text colors: `#fff`, `#8b8b8b`, `rgb(235, 236, 240)`
- Border colors: `#4a4a4a`, `#616161`
- Shadow colors: `#5d5b5b`

**Use exact hex codes** - don't approximate or use color names.

### Font Matching

**Handjet Font** (for rank numbers):
- Family: `Handjet, sans-serif`
- Weight: `800`
- Used in: Rank numbers, game rankings

**Bulma Default Fonts**:
- Used for: Body text, headings, UI elements
- Inherited from Bulma framework

### Testing for Visual Parity

#### Side-by-Side Comparison

1. **Open both versions** in browser:
   - Vue.js: http://localhost:8000/games/
   - Beta: http://localhost:8000/beta/games/

2. **Use browser DevTools**:
   - Inspect elements in both versions
   - Compare computed styles
   - Compare box model (padding, margin, borders)
   - Compare font properties

3. **Visual Comparison Tools**:
   - Take screenshots of both versions
   - Use image comparison tools
   - Check pixel-by-pixel if needed

4. **Checklist for Each Component**:
   - [ ] Open Vue version in browser
   - [ ] Open Beta version in browser
   - [ ] Compare HTML structure (view source)
   - [ ] Compare CSS (inspect element)
   - [ ] Compare colors (use color picker)
   - [ ] Compare fonts (inspect computed styles)
   - [ ] Compare spacing (measure with DevTools)
   - [ ] Compare responsive behavior (resize window)
   - [ ] Compare hover states
   - [ ] Document any differences found

#### Browser DevTools Comparison

1. **Inspect Element** in Vue version
2. **Copy computed styles** (right-click → Copy → Copy styles)
3. **Inspect same element** in Beta version
4. **Compare**:
   - Font family, size, weight
   - Colors (background, text, border)
   - Padding, margin
   - Width, height
   - Display, position
   - Any other CSS properties

#### Automated Visual Regression Testing (Optional)

Consider using tools like:
- **Percy** - Visual regression testing
- **Chromatic** - Component visual testing
- **BackstopJS** - Visual regression testing

### Common Styling Issues to Watch For

1. **Missing CSS frameworks**: Ensure Bulma, Bulmaswatch, MDI icons are loaded
2. **Missing fonts**: Ensure Handjet font is loaded
3. **Scoped styles**: Vue `scoped` styles need to be converted to specific selectors
4. **SASS syntax**: Convert SASS to CSS if not using SASS compiler
5. **Class name differences**: Ensure Bulma classes match exactly
6. **Color approximations**: Use exact hex codes, not approximations
7. **Missing hover states**: Copy all `:hover` styles
8. **Missing responsive classes**: Ensure `is-hidden-mobile`, `is-hidden-tablet`, etc. work
9. **Missing transitions**: Copy Vue transition styles
10. **Box model differences**: Ensure padding/margin match exactly

### Style Extraction Checklist

For each component migration:

1. [ ] **Extract HTML structure** from Vue template
2. [ ] **Extract all styles** from `<style>` section
3. [ ] **Convert SASS to CSS** (if needed)
4. [ ] **Handle scoped styles** (make selectors specific)
5. [ ] **Copy to Django template** or separate CSS file
6. [ ] **Test in browser** - compare with Vue version
7. [ ] **Fix any differences** found
8. [ ] **Document any intentional changes** (if any)

### Style Organization Strategy

**Option 1: Inline Styles in Templates** (Recommended for component-specific styles)
```django
{# beta/templates/games/includes/_game_row.html #}
<style>
.game-row { /* styles */ }
</style>
<div class="game-row">...</div>
```

**Option 2: Separate CSS File** (For shared styles)
```django
{# beta/templates/base.html #}
<link rel="stylesheet" href="{% static 'beta/css/game-row.css' %}">
```

**Option 3: Global Stylesheet** (For all beta styles)
```django
{# beta/templates/base.html #}
<link rel="stylesheet" href="{% static 'beta/css/beta.css' %}">
```

**Recommendation**: Use inline `<style>` blocks in templates for component-specific styles (matches Vue component structure), and a global stylesheet for shared styles.

### Final Visual Parity Verification

Before considering a component/page complete:

1. [ ] **Screenshot comparison**: Take screenshots of both versions, compare side-by-side
2. [ ] **DevTools inspection**: Compare computed styles for key elements
3. [ ] **Responsive testing**: Test at different screen sizes
4. [ ] **Browser testing**: Test in Chrome, Firefox, Safari
5. [ ] **Mobile testing**: Test on actual mobile devices
6. [ ] **Accessibility**: Ensure colors meet contrast requirements (maintain existing contrast)
7. [ ] **Performance**: Ensure styles don't cause layout shifts

### Tools for Visual Comparison

- **Browser DevTools**: Inspect and compare computed styles
- **Browser Extensions**: 
  - "PerfectPixel" - Overlay images for pixel-perfect comparison
  - "PixelPerfect" - Compare designs pixel-by-pixel
- **Online Tools**:
  - **Diffy.website** - Compare two websites side-by-side
  - **BrowserStack** - Cross-browser testing
- **Screenshot Tools**:
  - Take full-page screenshots of both versions
  - Use image diff tools to find differences

## Key Considerations

### 1. SEO
- **Current**: Uses vite-ssg for pre-rendering
- **Migration**: Django renders HTML server-side (better SEO)
- **Action**: Ensure all pages are server-rendered

### 2. Performance
- **Current**: Client-side pagination for unfiltered game list
- **Migration**: Server-side pagination (better for large datasets)
- **Action**: Use Django pagination, consider caching

### 3. User Experience
- **Current**: SPA with client-side routing
- **Migration**: Traditional multi-page app with HTMX enhancements
- **Action**: Use HTMX to maintain SPA-like feel where beneficial

### 4. Caching
- **Current**: Vuex store caches API responses
- **Migration**: Use Django cache framework
- **Action**: Cache expensive queries (genres, platforms, meta)

### 5. Scroll Position
- **Current**: Custom scroll position preservation
- **Migration**: Use Alpine.js with localStorage
- **Action**: Implement scroll restoration for game list

### 6. Search Functionality
- **Current**: Debounced API calls in Vue
- **Migration**: HTMX with debouncing
- **Action**: Use `hx-trigger="keyup changed delay:200ms"`

## Risk Assessment

### Low Risk
- Leaf components (pure presentation)
- Static pages (HomePage)
- Simple list views

### Medium Risk
- Components with complex state (GameList, GameSearch)
- Components with client-side caching (scroll position)
- Components with debounced API calls

### High Risk
- Navigation system (NavComponent)
- Router integration (App.vue)
- State management migration (Vuex → Django context)

## Testing Strategy

### Unit Tests
- Test Django views in isolation
- Test template rendering
- Test HTMX endpoints

### Integration Tests
- Test full page flows
- Test HTMX interactions
- Test Alpine.js interactions

### E2E Tests
- Test user journeys
- Test mobile responsiveness
- Test browser compatibility

## Rollback Plan

1. Keep Vue.js code in a separate branch
2. Deploy Django version to staging first
3. Run A/B testing if possible
4. Keep API endpoints functional during migration
5. Can revert to Vue.js if critical issues arise

## Success Metrics

- [ ] All pages render correctly
- [ ] All interactions work (filters, pagination, search)
- [ ] Performance is equal or better than Vue version
- [ ] SEO scores maintained or improved
- [ ] Mobile experience maintained
- [ ] No regression in functionality

## Next Steps

1. Review and approve this migration plan
2. Set up development environment with HTMX and Alpine.js
3. Create a proof-of-concept for one leaf component
4. Begin Phase 1 migration
5. Regular check-ins to assess progress

## Resources

- [HTMX Documentation](https://htmx.org/)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [Django Class-Based Views](https://docs.djangoproject.com/en/stable/topics/class-based-views/)
- [Django Template Language](https://docs.djangoproject.com/en/stable/ref/templates/language/)


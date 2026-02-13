# AGENTS.md (Canonical)

Last synchronized: 2026-02-13

This file is the canonical instruction source for Codex in this repository.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Acclaimed Games is a video game ranking and aggregation website that combines data from multiple sources to create comprehensive rankings. The application uses Django with server-side rendering, HTMX for dynamic interactions, and Alpine.js for client-side reactivity. It integrates with the IGDB (Internet Game Database) API.

## Available Skills

Use these skills for common workflows:
- `/commit` - Commit and push to git (builds CSS, minifies JS, collects static, pushes to main)
- `/deploy` - Deploy to Heroku production (all commit steps + push to Heroku)
- `/minify` - Minify JavaScript files and regenerate bundles
- `/igdb` - Import IGDB game data
- `/wikipedia` - Fetch Wikipedia metadata and genres
- `/refresh-metadata` - Weekly metadata refresh (IGDB + Wikipedia)
- `/test` - Run tests with coverage
- `/icons` - Add Material Design Icons to the site
- `/openlibrary` - Fetch book metadata from Open Library API

## Development Commands

### Backend (Django)

**Activate virtual environment:**

On macOS/Linux:
```bash
source venv/bin/activate
```

On Windows (Git Bash/PowerShell):
```bash
source venv/Scripts/activate
```

**Run development server:**
```bash
DEBUG=True python3 manage.py runserver
```

**Note:** Always include `DEBUG=True` when running the development server locally to enable template reloading, detailed error pages, and the Django Debug Toolbar.

**Database migrations:**
```bash
python3 manage.py migrate
python3 manage.py makemigrations
```

**Create superuser:**
```bash
python3 manage.py createsuperuser
```

**Sync production database to local SQLite:**
```bash
python3 manage.py sync_from_prod
```
Downloads all game data from production Heroku and loads it into local SQLite. Auth users are excluded - create a local superuser after syncing with `python3 manage.py createsuperuser`.

**Collect static files (before deployment):**
```bash
python3 manage.py collectstatic
```

### Heroku Commands

**Important:** When running commands on Heroku, use `--` after `run` to separate Heroku flags from the command:

```bash
# Run Django shell with a command
heroku run -- python manage.py shell -c "from games.models import Game; print(Game.objects.count())"

# Run a management command
heroku run -- python manage.py migrate

# Open interactive shell
heroku run -- python manage.py shell
```

## Architecture

### Backend Structure

- **acclaimedgames/** - Django project settings and main URL configuration
- **core/** - Shared infrastructure for multi-media support:
  - **models.py** - User model, abstract base classes (MediaItemBase, CreatorBase, ExternalDataBase, UserTrackingBase)
  - **mixins.py** - Shared view mixins (RobustPaginationMixin, HTMXPartialMixin)
  - **templatetags/core_filters.py** - Shared template filters
  - **templates/core/** - Shared templates (_pagination.html, _base_media_row.html)
  - **static/core/js/** - Base JavaScript renderer classes
- **games/** - Main Django app containing:
  - **models.py** - Core data models (Game, Developer, Platform, List, etc.)
  - **api/** - REST API with views, serializers, and URL routing
  - **views.py** - Django class-based views for all routes
  - **middleware.py** - HTMXPushURLMiddleware for HTMX history support
  - **templatetags/** - Custom template filters (game_filters.py)
  - **management/commands/** - Custom Django commands (e.g., `get_igdb.py`)
  - **tests/** - Comprehensive test suite (API, models, IGDB, imports, views, admin, utils)
  - **templates/** - Server-side templates with HTMX and Alpine.js
  - **static/** - Static files served by Django
- **books/** - Books app for book rankings (feature-flagged with `BOOKS_ENABLED`):
  - **models.py** - Book, Author, BookGenre, BookSeries, ReadBook, WantToReadBook, etc.
  - **api/** - REST API with views, serializers, and URL routing
  - **views.py** - Book-related views (BookHomePageView, BookDetailView, AuthorListView, etc.)
  - **openlibrary.py** - Open Library API client for book metadata
  - **hardcover.py** - Hardcover GraphQL API client (optional)
  - **book_metadata.py** - Unified metadata service combining multiple sources
  - **templatetags/book_filters.py** - Book-specific template filters
  - **management/commands/** - Book metadata commands (fetch_book_metadata.py)
  - **templates/books/** - Book templates
  - **static/books/js/** - Book list renderer and client-side filtering

**Installed Apps:**
- `django.contrib.admin` - Admin interface
- `django.contrib.auth` - Authentication
- `django.contrib.contenttypes` - Content type framework
- `django.contrib.sessions` - Session management
- `django.contrib.messages` - Messaging framework
- `django.contrib.staticfiles` - Static file management
- `django.contrib.flatpages` - Flat pages framework for CMS content
- `django.contrib.sites` - Sites framework (used for multi-site support)
- `django.contrib.postgres` - PostgreSQL-specific features
- `rest_framework` - Django REST Framework
- `corsheaders` - CORS support
- `tailwind` - django-tailwind integration
- `theme` - Tailwind CSS theme app with DaisyUI
- `core` - Shared infrastructure (User model, abstract bases, mixins)
- `games` - Main game aggregation app with HTMX and Alpine.js
- `books` - Book rankings app (behind `BOOKS_ENABLED` feature flag)

**Middleware:**
- `django.middleware.security.SecurityMiddleware` - Security headers
- `whitenoise.middleware.WhiteNoiseMiddleware` - Static file serving in production
- `django.contrib.sessions.middleware.SessionMiddleware` - Session management
- `corsheaders.middleware.CorsMiddleware` - CORS headers
- `django.middleware.common.CommonMiddleware` - Common utilities
- `django.middleware.csrf.CsrfViewMiddleware` - CSRF protection
- `django.contrib.auth.middleware.AuthenticationMiddleware` - Authentication
- `django.contrib.messages.middleware.MessageMiddleware` - Messages
- `django.middleware.clickjacking.XFrameOptionsMiddleware` - Click-jacking protection
- `games.middleware.HTMXPushURLMiddleware` - HTMX history/URL push support
- `django.contrib.flatpages.middleware.FlatpageFallbackMiddleware` - Flat pages routing

### Data Models

Core Django models include:

- **Game** - Video games with ranking, IGDB integration, genres, platforms, and developers
- **Developer** - Game development entities with hierarchical parent-child relationships
  - Uses self-referential `parent` FK for ownership hierarchy
  - Root developers (parent=None) have slugs for URL routing (e.g., Nintendo, Valve)
  - Subsidiary developers (parent=Developer) are child entities (e.g., Nintendo EAD, Respawn)
  - Games link to developers via `Game.developers` M2M field
  - In IGDB's data model, all are "company" records - we add hierarchy on import
- **Platform** - Gaming platforms (PC, PS5, etc.)
- **Genre** - Game genres
- **Publication** - Magazines/websites that publish game lists
- **List/ListMembership** - Published rankings and game positions within them
- **Post** - Blog-style news posts with markdown support
- **Snippet** - Reusable text snippets

Books-specific models (behind `BOOKS_ENABLED` feature flag):

- **Book** - Book items with ranking, author, genre, and metadata integration
- **Author** - Book authors with hierarchical parent-child relationships (similar to Developer)
- **BookGenre** - Hierarchical book genres with path denormalization
- **BookSeries** - Book series with position tracking
- **BookListMembership** - Book positions within lists
- **ReadBook/WantToReadBook** - User tracking for books (like PlayedGame/WantToPlayGame)
- **WikipediaBookData** - Wikipedia metadata for books

### API Architecture

Django REST Framework powers the API at `/api/` with endpoints:
- `/api/games/` - List and search games
- `/api/games/search/` - Game search for navbar
- `/api/games/<slug>/` - Game details with lists appearances
- `/api/developers/` - List of all developers with games
- `/api/developers/<slug>/` - Developer details by slug
- `/api/developers/by-id/<igdb_id>/` - Developer details by IGDB ID
- `/api/lists/` - Source lists
- `/api/platforms/` - Gaming platforms
- `/api/genres/` - Game genres (also available at `/api/wikipedia-genres/` for backwards compatibility)
- `/api/meta/` - Metadata about the database
- `/api/unified-search/` - Unified search for games, developers, and series

Books API endpoints (behind `BOOKS_ENABLED` feature flag):
- `/api/books/` - List and search books
- `/api/books/search/` - Book search
- `/api/books/<slug>/` - Book details with lists appearances
- `/api/books/all/` - Bulk endpoint with gzip compression
- `/api/books/authors/` - List authors
- `/api/books/authors/<slug>/` - Author details with book list
- `/api/books/unified-search/` - Unified book search

### Template Architecture

The application uses Django templates with server-side rendering:
- **Production**: Uses Django's cached template loader for optimal performance
- **Development**: Uses non-cached loaders for hot-reloading during development
- Templates configured in `settings.py` based on `DEBUG` mode
- Game templates are in `games/templates/`
- Book templates are in `books/templates/` (feature-flagged)
- Shared templates are in `core/templates/`

## Application Structure (Django + HTMX + Alpine.js)

The application uses Django templates with HTMX for dynamic interactions and Alpine.js for client-side reactivity.

### Views and Templates

- **games/** - Main Django app containing:
  - **views.py** - View functions for all routes
  - **urls.py** - URL routing configuration (in main acclaimedgames/urls.py)
  - **templates/** - Django templates organized by feature:
    - **base.html** - Main template layout with navigation
    - **games/** - Game list, detail, and search templates
    - **developers/** - Developer list and detail templates
    - **lists/** - Lists and results templates
    - **posts/** - Post/news templates
    - **pages/** - Static page templates
  - **templatetags/** - Custom template filters (game_filters.py)
  - **middleware.py** - HTMXPushURLMiddleware for HTMX history support

### Application Features

**Styling:**
- Uses Tailwind CSS v4 with DaisyUI v5 component library
- Light theme (lofi) as default with forest dark theme available via theme switcher
- Responsive design using Tailwind's mobile-first breakpoints (md:, lg:, etc.)
- Custom components defined in `theme/static_src/src/styles.css` using Tailwind's `@layer components`

**Template Filters:**
- `from_now` - Converts datetime to relative time (e.g., "2 hours ago")
- Custom utilities for formatting and string manipulation

**Routes:**
- `/` - Home page (games)
- `/games/` - Game list with filtering and search
- `/games/<slug>/` - Game detail view
- `/games/search/` - Game search endpoint (HTMX)
- `/developers/` - Developer list with game counts and hierarchy
- `/developers/<slug>/` - Developer detail view with subsidiary hierarchy and games
- `/lists/` - Published rankings list (with media_type filter)
- `/posts/` - News and blog posts
- `/page/<slug>/` - Static pages

Book routes (behind `BOOKS_ENABLED` feature flag):
- `/books/` - Book list with filtering and search
- `/book/<slug>/` - Book detail view
- `/authors/` - Author list with book counts
- `/authors/<slug>/` - Author detail view with books

**HTMX Integration:**
- Dynamic filtering without full page reloads
- Pagination for lists with smooth navigation
- Real-time search results
- Smooth form submissions

**Alpine.js Interactivity:**
- Client-side state management for UI components
- Dropdown menus, modals, and toggles
- Form validation and user interactions

### Middleware

**HTMXPushURLMiddleware**: Provides HTMX support for browser history:
- Pushes URLs to browser history when HTMX requests complete
- Maintains browser back/forward functionality with HTMX
- Uses `HX-Push-Url` header for selective history updates

### Google Analytics Integration

The site uses Google Analytics 4 (GA4) with custom HTMX tracking for comprehensive page view analytics:

**Implementation Location:** `games/templates/base.html`

**Standard Page Views:**
- gtag.js loads on every page via base template
- Tracks initial page loads and full navigation
- Property ID: `G-0591405Q89`

**HTMX Navigation Tracking:**
- Custom event listener on `htmx:afterSwap` tracks partial page updates as page views
- Includes full URL path with query parameters for granular tracking
- Captures filter changes, pagination, and search navigation
- Provides more detailed tracking than typical SPAs (tracks query parameter changes as distinct page views)

**Code Example:**
```javascript
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Track HTMX navigation as page views
    if (window.gtag) {
        gtag('config', 'G-0591405Q89', {
            page_path: window.location.pathname + window.location.search
        });
    }
});
```

**Advantages over SPA Tracking:**
- Automatically tracks all filter state changes (e.g., `/games/search/?q=zelda` vs `/games/search/?q=mario`)
- No custom router configuration required
- Simpler implementation with more granular insights

### Development Notes

- Template reloading works in development via Django's non-cached template loaders
- In production, template caching is enabled for performance

### Home Page Client/Server Rendering Consistency

The home page game rankings use a **dual-rendering architecture** that requires careful coordination:

**How It Works:**
1. **Server-side rendering**: Django templates render game rows with actual data on initial page load
2. **Client-side rendering**: JavaScript clones `<template>` elements and fills them with data for filtered/paginated results
3. **Single source of truth**: The same Django templates (`_game_row_desktop.html`, `_game_row_mobile.html`) serve both purposes

**Template Structure:**
- When `game` context is provided → server renders with data
- When `game` is absent (inside `<template>` tags) → renders empty structure with `data-slot` attributes for JS

**Files That Must Stay In Sync:**

| Server-Side (Python/Django) | Client-Side (JavaScript) |
|----------------------------|--------------------------|
| `games/templates/games/includes/_game_row_desktop.html` | `games/static/games/js/game-list-renderer.js` |
| `games/templates/games/includes/_game_row_mobile.html` | (fallback string methods: `_renderDesktopRowString`, `_renderMobileRowString`) |
| `games/templatetags/game_filters.py` | `_platformFamilies`, `_familyInfo` objects |

**When Modifying Game Rows:**
1. Update the Django template for server-rendered output
2. Update the JavaScript renderer's DOM-cloning logic (uses `data-slot` attributes)
3. Update the JavaScript fallback string-rendering methods to match
4. Ensure `PLATFORM_FAMILIES` and `FAMILY_INFO` constants match between Python and JS

**Key Data Slots:** `rank`, `global-rank`, `thumbnail`, `name`, `year`, `title-link`, `thumb-link`, `year-link`, `meta-row`, `platforms`, `genres`, `list-count`, `primary-developer`, `played-button`

**Testing:** After changes, verify both:
- Fresh page load (server-rendered)
- Filtered results (client-rendered via JS template cloning)

## IGDB Integration

The `games/igdb.py` module handles IGDB API integration with multiple optimization strategies:

### Features

**Field Expansion**: Reduces API calls by 3-5x by expanding cover and genre data in the main game query instead of making separate requests.

**Concurrent Requests**: Process multiple games simultaneously (up to 8 concurrent requests) for 4-8x speedup.

**Multi-Query Batching**: Fetch multiple games per API request (10-50 for free tier, up to 500 for Pro tier) for additional 3-5x speedup.

**Pro Tier Support**: Access IGDB Pro tier with 750x faster rate limits (3,000 req/sec vs 4 req/sec).

**Thread-Safe**: All caching and rate limiting is thread-safe for concurrent processing.

IGDB provides cover art, descriptions, developer information, and genres.

For detailed command usage, run `/igdb`.

## Configuration

### Environment Variables

Environment variables are managed via django-environ (`.env` file):
- `DEBUG` - Enable Django debug mode
- `SECRET_KEY` - Django secret key
- `IGDB_CLIENT_ID` - IGDB API client ID
- `IGDB_CLIENT_SECRET` - IGDB API client secret
- `IGDB_USE_PRO_TIER` - Enable IGDB Pro tier (default: False)
- `WIKIDATA_ACCESS_TOKEN` - For faster Wikipedia processing (2.5x speedup)
- `BOOKS_ENABLED` - Enable books feature (default: False, enabled in DEBUG/TEST modes)
- `HARDCOVER_API_TOKEN` - Optional Hardcover API token for additional book metadata

### Configuration Files

- **`.python-version`** - Specifies Python 3.11 for Heroku deployment (can use different versions locally)
- **`.pre-commit-config.yaml`** - Pre-commit hook configuration for code quality enforcement (Black, Flake8, tests)
- **`.coveragerc`** - Coverage configuration excluding migrations and database vendor-specific code
- **`.flake8`** - Flake8 linter configuration (max line length 88, excludes venv)
- **`scripts/run_tests.sh`** - Alternative test runner using Django's test framework

## Database

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Heroku
- The `rank` field on Game determines primary ordering (lower is better)
- `year_rank` and `decade_rank` are calculated automatically on save

## Dependencies

The backend dependencies are listed in `requirements.txt` and include:
- **coverage** - Test coverage reporting tool
- **Django** and related packages - Web framework and extensions
- **django-tailwind** - Tailwind CSS integration for Django
- **djangorestframework** - REST API framework
- **psycopg2** - PostgreSQL database adapter
- And other supporting packages

**Note:** Tailwind CSS and DaisyUI are managed via npm in `theme/static_src/` (not Python packages).

Install all backend dependencies with:
```bash
pip install -r requirements.txt
```

## Static Files

- Django collectstatic copies static files from apps to `staticfiles/`
- WhiteNoise serves static files in production
- Static files are located in:
  - `games/static/` - Game app static files (icons, fonts, images)
  - `theme/static/` - Tailwind CSS compiled output
  - `games/templates/` - Template files

### CSS Workflow (Tailwind CSS)

The site uses django-tailwind with Tailwind CSS v4 and DaisyUI v5 for styling.

**Development:**
```bash
# Start Tailwind CSS watcher (rebuilds CSS on file changes)
python manage.py tailwind start

# Run Django dev server (in separate terminal)
python manage.py runserver
```

**Production Build:**
```bash
# Build minified CSS for production
python manage.py tailwind build

# Collect static files
python manage.py collectstatic --noinput
```

**File Locations:**
- `theme/static_src/src/styles.css` - Main Tailwind CSS source file with custom components
- `theme/static/css/dist/styles.css` - Compiled CSS output (auto-generated)
- `games/static/games/css/mdi-subset.css` - Material Design Icons (self-hosted subset)

**Adding Custom Styles:**
Edit `theme/static_src/src/styles.css` and use Tailwind's `@layer` directive:
```css
@layer components {
  .my-component {
    @apply flex items-center gap-2;
  }
}
```

**DaisyUI Components:**
Common components used: `btn`, `card`, `table`, `alert`, `badge`, `input`, `select`, `checkbox`, `dropdown`, `modal`, `link`

**Theme Configuration:**
Themes are defined in `theme/static_src/src/styles.css` using DaisyUI's `@plugin` directive:
```css
@plugin "daisyui" {
  themes: ["lofi", "forest"];
}
```
The theme switcher in the navigation allows users to change themes, with the selection persisted in localStorage.

### JavaScript Workflow

JavaScript files in `games/static/games/js/` follow a specific workflow:

**Source and Minified Files:**
- Source files (e.g., `game-list-renderer.js`) contain the readable code
- Minified files (e.g., `game-list-renderer.min.js`) are generated from source files
- **Always edit the source `.js` file, never the `.min.js` file directly**

**Bundle File:**
- `client-side-filtering.bundle.min.js` combines multiple minified files for the home page
- Bundle is created from: `game-cache.min.js`, `client-filter.min.js`, `game-list-renderer.min.js`, `client-filtering.min.js`

**After Editing JavaScript:**
Run `/minify` or `./scripts/minify_js.sh`

The minify skill/script:
1. Minifies any source `.js` files that are newer than their `.min.js` counterparts
2. Regenerates the bundle if any of its source files changed
3. Stages updated files for git

**Important:** When modifying client-side game rendering (e.g., `game-list-renderer.js`), changes must be reflected in both:
- The Django template (server-side rendering)
- The JavaScript file (client-side rendering on home page)

## Design Guidelines

### Quantitative Display Ruleset

When making any changes that affect **visual displays of quantitative information** (charts, graphs, tables with numbers, rankings, statistics, data visualizations), read and follow the principles in:

**`acclaimedgames/rulesets/Unified Quantitative Display Ruleset.md`**

This ruleset applies to:
- Game ranking displays and tables
- Statistics and metrics (play counts, list appearances, scores)
- Charts or graphs showing trends, distributions, or comparisons
- Any numerical data presentation to users

Key principles to prioritize:
- **Graphical integrity**: Represent quantities proportionally; what is shown must match the data
- **Data-ink ratio**: Maximize data-bearing elements, minimize decorative non-data elements
- **Comparison support**: Design to encourage meaningful comparisons
- **Context**: Always provide units, time frames, and context needed for interpretation
- **Avoid chartjunk**: No fake 3D, unnecessary decoration, or design that doesn't serve the data

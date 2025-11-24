# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Acclaimed Games is a video game ranking and aggregation website that combines data from multiple sources to create comprehensive rankings. The application uses Django with server-side rendering, HTMX for dynamic interactions, and Alpine.js for client-side reactivity. It integrates with the IGDB (Internet Game Database) API.

## Instructions for Claude

**When the user asks to deploy, commit and push, or mentions "production/heroku":**

Always follow the **Complete Deployment Workflow** documented in the Deployment section below. This includes:
1. Updating DEVLOG.md (if changes warrant documentation - see DEVLOG guidelines below)
2. Collecting static files
3. Committing all changes
4. Pushing to main
5. Deploying to Heroku

Do not skip any steps. The user should not have to remind you to collect static files.

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
python3 manage.py runserver
```

**Database migrations:**
```bash
python3 manage.py migrate
python3 manage.py makemigrations
```

**Create superuser:**
```bash
python3 manage.py createsuperuser
```

**Import IGDB data:**
```bash
# Default command uses maximum throughput (concurrency=8, tier-aware batching)
# Free tier: batch=50, Pro tier: batch=500
python3 manage.py get_igdb
```

**Import IGDB data with custom settings:**
```bash
# Conservative mode (slower but safer)
python3 manage.py get_igdb --concurrency 4 --batch-games 20

# Sequential mode (disable optimizations)
python3 manage.py get_igdb --concurrency 1 --batch-games 0

# Pro tier (requires subscription - 750x faster rate limit + 10x batch size)
python3 manage.py get_igdb --pro
```

**Performance Metrics:**
- Free tier defaults: ~100 games/sec (batch=50, concurrency=8)
- Pro tier defaults: ~1000+ games/sec (batch=500, concurrency=8)
- 1000 games: ~10 seconds (free) vs ~1 second (pro)

**Collect static files (before deployment):**
```bash
python3 manage.py collectstatic
```

**Run tests:**
```bash
python3 manage.py test games.tests
```

**Run tests with coverage:**
```bash
coverage run --source=games manage.py test games.tests
coverage report
```

### Deployment

**Production URL:** https://www.acclaimedvideogames.com/

The project is deployed to Heroku.

**Complete Deployment Workflow:**

When making changes that need to be deployed to production, follow this complete workflow:

```bash
# 0. Update DEVLOG.md if changes warrant documentation (see DEVLOG section)
#    Only if: bug fixes, features, optimizations, or breaking changes
#    Keep to 2-4 bullet points max per day

# 1. Collect static files
python3 manage.py collectstatic --noinput

# 2. Stage all changes
git add -A

# 3. Commit with descriptive message
git commit -m "Your commit message here"

# 4. Push to main branch
git push origin main

# 5. Deploy to Heroku
git push heroku main
```

**Important Notes:**
- Update DEVLOG.md for significant changes (see Development Log section below for guidelines)
- Pre-commit hooks will run tests and enforce code quality before allowing the commit
- **If pre-commit hooks fail**: Fix issues immediately, do NOT skip or work around them
  - Coverage failures: Add tests or proper exclusions (not workarounds)
  - Linting failures: Fix the code to comply with standards
  - Test failures: Fix the failing tests or broken code

## Testing and Code Quality

### Backend Testing

The Django backend has comprehensive test coverage in the `games/tests/` directory:

- **test_api.py** - API endpoint tests including filtering, serialization, and pagination
- **test_models.py** - Model behavior, IGDB integration, and ranking utilities
- **test_igdb.py** - IGDB API integration with extensive mocking
- **test_igdb_importer.py** - IGDB importer logic and batch processing tests
- **test_imports.py** - Data import functionality and file parsing tests
- **test_views.py** - Import view integration tests
- **test_main_views.py** - Main application views (game list, detail, search, developers, etc.)
- **test_admin.py** - Django admin functionality tests
- **test_management.py** - Custom management command tests (get_igdb, cleanup, etc.)
- **test_cleanup_command.py** - Database cleanup command tests
- **test_forms.py** - Form validation and processing tests
- **test_middleware.py** - HTMXPushURLMiddleware and other middleware tests
- **test_template_tags.py** - Custom template filter and tag tests
- **test_utils.py** - Utility function tests

**Coverage Requirements:**
- Minimum 95% test coverage enforced by pre-commit hooks (excludes migrations and database vendor-specific code)
- Run coverage check: `coverage run --source=games manage.py test games.tests && coverage report --fail-under=95`
- Configuration: `.coveragerc` excludes migrations and PostgreSQL-specific optimizations
- Current coverage: 100% (exceeds minimum requirement)

### Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`) to enforce code quality:

1. **Black Formatter** - Automatically formats Python code
2. **Flake8 Linter** - Lints Python code (configuration in `.flake8` - max line length 88)
3. **Django Coverage** - Enforces 95% test coverage threshold (excluding migrations)
4. **Django Test Suite** - Runs full test suite via `scripts/run_tests.sh`

**Note:** Commits will be blocked if any tests fail, coverage drops below 95%, or linting fails.

## Development Log (DEVLOG)

The `DEVLOG.md` file tracks significant changes and improvements to the project. Agents should update it when making changes worthy of documentation.

**When to Update:**
- Bug fixes that resolve user-reported issues or known problems
- Performance improvements or optimizations
- New features or functionality additions
- Significant refactoring or architectural changes
- API or database schema modifications
- Deployment issues or critical fixes

**When NOT to Update:**
- Minor style or formatting changes
- Documentation-only updates (unless substantive)
- Test-only commits with no production changes
- Dependency version bumps without notable behavior changes

**Format Guidelines:**
- Keep entries very concise - just 2-4 bullet points per day maximum
- Use brief, imperative language (e.g., "Fix double-load on first search character")
- Group changes by date (one date header per day of work)
- Include affected components/features for context
- Link to related files if relevant (e.g., `games/templates/developers/developer_list.html`)
- Example:
  ```
  ## 2025-11-22
  - Fixed double-load on first search character in developer list (debounce trailing edge)
  ```

## Architecture

### Backend Structure

- **acclaimedgames/** - Django project settings and main URL configuration
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
- `games` - Main game aggregation app with HTMX and Alpine.js

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
- **Developer/DeveloperAlias** - Game developers and their alternate names
- **Platform** - Gaming platforms (PC, PS5, etc.)
- **Genre** - Game genres
- **Publication** - Magazines/websites that publish game lists
- **List/ListMembership** - Published rankings and game positions within them
- **Post** - Blog-style news posts with markdown support
- **Snippet** - Reusable text snippets

### API Architecture

Django REST Framework powers the API at `/api/` with endpoints:
- `/api/games/` - List and search games
- `/api/games/<slug>/` - Game details with lists appearances
- `/api/developers/<slug>/` - Developer details with games
- `/api/lists/` - Source lists
- `/api/platforms/` - Gaming platforms
- `/api/genres/` - Game genres
- `/api/posts/` - News posts
- `/api/meta/` - Metadata about the database

### Template Architecture

The application uses Django templates with server-side rendering:
- **Production**: Uses Django's cached template loader for optimal performance
- **Development**: Uses non-cached loaders for hot-reloading during development
- Templates configured in `settings.py` based on `DEBUG` mode
- All templates are in the `games/templates/` directory

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
- Uses Bulma CSS framework with Bulmaswatch Cyborg theme for modern dark UI
- Responsive design compatible with all screen sizes

**Template Filters:**
- `from_now` - Converts datetime to relative time (e.g., "2 hours ago")
- Custom utilities for formatting and string manipulation

**Routes:**
- `/` - Home page
- `/games/` - Game list with filtering and search
- `/games/<slug>/` - Game detail view
- `/games/search/` - Game search endpoint (HTMX)
- `/developers/` - Developer list
- `/developers/<slug>/` - Developer detail view
- `/lists/` - Published rankings list
- `/posts/` - News and blog posts
- `/page/<slug>/` - Static pages

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

## IGDB Integration

The `games/igdb.py` module handles IGDB API integration with multiple optimization strategies:

### Features

**Field Expansion**: Reduces API calls by 3-5x by expanding cover and genre data in the main game query instead of making separate requests.

**Concurrent Requests**: Process multiple games simultaneously (up to 8 concurrent requests) for 4-8x speedup.

**Multi-Query Batching**: Fetch multiple games per API request (10-50 for free tier, up to 500 for Pro tier) for additional 3-5x speedup.

**Pro Tier Support**: Access IGDB Pro tier with 750x faster rate limits (3,000 req/sec vs 4 req/sec).

**Thread-Safe**: All caching and rate limiting is thread-safe for concurrent processing.

### Usage

- `Game.get_igdb_data()` - Fetches and saves IGDB data for a single game
- `python3 manage.py get_igdb` - Batch import IGDB data for all games
- `python3 manage.py get_igdb --concurrency 4` - Use concurrent processing
- `python3 manage.py get_igdb --batch-games 20` - Use multi-query batching
- `python3 manage.py get_igdb --pro` - Enable Pro tier (requires subscription)

### Command Options

- `--concurrency N` - Number of concurrent requests (1-8, default: 4)
- `--batch-games N` - Batch size for multi-query (0-500, default: 10)
- `--delay SECONDS` - Additional delay between games (default: 0.0)
- `--batch-size N` - Progress checkpoint interval (default: 50)
- `--pro` - Use IGDB Pro tier (or set IGDB_USE_PRO_TIER=True in .env)
- `--force` - Force refresh even if game already has IGDB data
- `--game NAME` - Update specific game by name
- `--slug SLUG` - Update specific game by slug
- `--id ID` - Update specific game by database ID

### Performance

Default settings (concurrency=4, batch-games=10): ~8-10 games/sec (480-600 games/min)
Sequential mode (--concurrency 1 --batch-games 0): ~2 games/sec (120 games/min)
Aggressive settings (concurrency=6, batch-games=20): ~15-20 games/sec (900-1200 games/min)
With Pro tier (--pro): ~100-500 games/sec (6,000-30,000 games/min)

IGDB provides cover art, descriptions, developer information, and genres.

## Configuration

### Environment Variables

Environment variables are managed via django-environ (`.env` file):
- `DEBUG` - Enable Django debug mode
- `SECRET_KEY` - Django secret key
- `IGDB_CLIENT_ID` - IGDB API client ID
- `IGDB_CLIENT_SECRET` - IGDB API client secret
- `IGDB_USE_PRO_TIER` - Enable IGDB Pro tier (default: False)

### Configuration Files

- **`.python-version`** - Specifies Python 3.11 for Heroku deployment (can use different versions locally)
- **`.pre-commit-config.yaml`** - Pre-commit hook configuration for code quality enforcement (Black, Flake8, tests)
- **`.coveragerc`** - Coverage configuration excluding migrations and database vendor-specific code
- **`.flake8`** - Flake8 linter configuration (max line length 88, excludes venv)
- **`scripts/run_tests.sh`** - Test execution script used by pre-commit hooks

## Database

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Heroku
- The `rank` field on Game determines primary ordering (lower is better)
- `year_rank` and `decade_rank` are calculated automatically on save

## Dependencies

The backend dependencies are listed in `requirements.txt` and include:
- **coverage** - Test coverage reporting tool (required for pre-commit hooks)
- **Django** and related packages - Web framework and extensions
- **djangorestframework** - REST API framework
- **psycopg2** - PostgreSQL database adapter
- And other supporting packages

Install all backend dependencies with:
```bash
pip install -r requirements.txt
```

## Static Files

- Django collectstatic copies static files from apps to `staticfiles/`
- WhiteNoise serves static files in production
- Static files are located in:
  - `games/static/` - Game app static files
  - `games/templates/` - Template files with inline styles

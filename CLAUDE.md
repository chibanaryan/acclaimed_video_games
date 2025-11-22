# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Acclaimed Games is a video game ranking and aggregation website that combines data from multiple sources to create comprehensive rankings. The application uses Django backend with a Vue.js 3 frontend and integrates with the IGDB (Internet Game Database) API.

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
python manage.py runserver
```

**Database migrations:**
```bash
python manage.py migrate
python manage.py makemigrations
```

**Create superuser:**
```bash
python manage.py createsuperuser
```

**Import IGDB data:**
```bash
python manage.py get_igdb
```

**Collect static files (before deployment):**
```bash
python manage.py collectstatic
```

**Run tests:**
```bash
python manage.py test games.tests
```

**Run tests with coverage:**
```bash
coverage run --source=games manage.py test games.tests
coverage report
```

### Frontend (Vue.js)

**Install dependencies:**
```bash
cd frontend
npm install
```

**Run development server:**
```bash
npm run dev
```

**Build for production (SSG):**
```bash
npm run build
```

**Note:** The build process uses vite-ssg for server-side static generation. The Django development server must be running during the build so that vite-ssg can fetch data from the API to pre-render routes. The number of routes pre-rendered is controlled in `vite.config.js` (currently limited to 10 games and 5 developers for testing; increase to 9999 for full production builds).

**Lint code:**
```bash
npx eslint src/
```

**Run tests:**
```bash
npm run test
```

**Run tests in watch mode:**
```bash
npm run test:watch
```

**Run tests with coverage:**
```bash
npm run test:coverage
```

### Deployment

**Production URL:** https://www.acclaimedvideogames.com/

The project is deployed to Heroku. To deploy:

1. Build frontend: `cd frontend && npm run build`
2. Collect static files: `python manage.py collectstatic`
3. Add dist folder: `git add dist`
4. Commit and push: `git commit -av -m "message" && git push heroku main`

## Testing and Code Quality

### Backend Testing

The Django backend has comprehensive test coverage in the `games/tests/` directory:

- **test_api.py** - API endpoint tests including filtering, serialization, and pagination
- **test_models.py** - Model behavior, IGDB integration, and ranking utilities
- **test_igdb.py** - IGDB API integration with extensive mocking
- **test_imports.py** - Data import functionality tests
- **test_views.py** - ImportView integration tests
- **test_admin.py** - Django admin functionality tests
- **test_management.py** - Custom management command tests
- **test_utils.py** - Utility function tests

**Coverage Requirements:**
- Minimum 95% test coverage enforced by pre-commit hooks (excludes migrations and database vendor-specific code)
- Run coverage check: `coverage run --source=games manage.py test games.tests && coverage report --fail-under=95`
- Configuration: `.coveragerc` excludes migrations and PostgreSQL-specific optimizations
- Current coverage: 100% (exceeds minimum requirement)

### Frontend Testing

The Vue.js frontend uses Vitest for testing with the following structure:

**Unit Tests:**
- `frontend/src/__tests__/store.spec.js` - Vuex store tests
- `frontend/src/__tests__/models.spec.js` - Frontend model class tests
- `frontend/src/__tests__/utils.spec.js` - Utility function tests (scroll position, slug parsing)
- `frontend/src/__tests__/objectStore.spec.js` - PersistentObjectStore tests
- `frontend/src/__tests__/config.spec.js` - API URL configuration tests (SSR vs client-side)

**Component Tests:**
- `frontend/src/components/__tests__/NavComponent.spec.js` - Navigation component behavior

**Test Configuration:**
- Vitest configured in `vite.config.js` with jsdom environment
- Test setup file: `frontend/src/test/setup.js` (localStorage mock)

**Test Dependencies:**
- vitest (^4.0.9) - Test runner
- @vitest/coverage-v8 (^4.0.9) - Coverage reporting
- @vue/test-utils (^2.4.0-alpha.2) - Vue component testing utilities
- jsdom (^27.2.0) - DOM implementation for testing

**Coverage Requirements:**
- Minimum 95% test coverage enforced by pre-commit hooks and Vitest configuration
- Thresholds configured in `vite.config.js` for statements, branches, functions, and lines
- Current coverage: 100% (exceeds minimum requirement)

### Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`) to enforce code quality:

1. **Black Formatter** - Automatically formats Python code
2. **Flake8 Linter** - Lints Python code (configuration in `.flake8` - max line length 88)
3. **Frontend Tests with Coverage** - Runs `npm run test:coverage` and enforces 95% coverage minimum
4. **Django Coverage** - Enforces 95% test coverage threshold (excluding migrations)
5. **Django Test Suite** - Runs full test suite via `scripts/run_tests.sh`

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
- Link to related files if relevant (e.g., `frontend/src/components/DeveloperList.vue`)
- Example:
  ```
  ## 2025-11-22
  - Fixed double-load on first search character in developer list (debounce trailing edge)
  - Added SSR pre-fetching for developer list (fixed page flash on navigation)
  ```

## Architecture

### Backend Structure

- **acclaimedgames/** - Django project settings and main URL configuration
- **games/** - Main Django app containing:
  - **models.py** - Core data models (Game, Developer, Platform, List, etc.)
  - **api/** - REST API with views, serializers, and URL routing
  - **management/commands/** - Custom Django commands (e.g., `get_igdb.py`)
  - **tests/** - Comprehensive test suite (API, models, IGDB, imports, views, admin, utils)
  - **templates/** - Server-side templates (mostly just index.html for SPA)
  - **static/** - Static files served by Django
- **beta/** - Alternative Django + HTMX + Alpine.js implementation (see Beta App section)

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
- `games` - Main game aggregation app
- `beta` - Beta implementation with HTMX and Alpine.js

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
- `beta.middleware.HTMXPushURLMiddleware` - HTMX history/URL push support for beta app
- `django.contrib.flatpages.middleware.FlatpageFallbackMiddleware` - Flat pages routing

### Frontend Structure

- **frontend/src/**
  - **components/** - Vue components (GameList, GameDetail, DeveloperDetail, etc.)
    - **__tests__/** - Component tests
  - **models/** - Frontend model classes that mirror Django models
  - **router.js** - Vue Router configuration (exports routes array for vite-ssg)
  - **store.js** - Vuex global state management
  - **objectStore.js** - Persistent localStorage wrapper (SSR-safe)
  - **config.js** - API URL configuration (handles SSR vs client-side differences)
  - **constants.js** - Application-wide constants
  - **utils.js** - Utility functions (SSR-safe with window guards)
  - **__tests__/** - Unit tests for models, store, utils, and objectStore
  - **test/** - Test configuration and setup files

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

All non-API routes are handled by the Vue.js SPA.

### Frontend Patterns

**BaseModel Pattern**: All frontend models extend `BaseData` which automatically converts snake_case API responses to camelCase properties and parses datetime strings to moment objects.

**PersistentObjectStore**: A localStorage wrapper used for persisting state (e.g., scroll position for game list navigation). SSR-safe with guards for `window` and `localStorage` access.

**Vuex Store**: Manages global state for genres, platforms, and metadata. Data is lazy-loaded and cached in the store.

**Router Scroll Behavior**: Custom scroll position preservation for game list pages - when navigating from a game list to game detail and back, the scroll position is restored.

**SSR-Safe Architecture**: The application uses vite-ssg for server-side static generation (SSG), making it compatible with web crawlers and the Wayback Machine. All browser-specific APIs (localStorage, window, document) are guarded with `typeof window !== 'undefined'` checks. The `getApiUrl()` helper in `config.js` provides absolute URLs during SSG builds and relative URLs in the browser.

**SPAWithPrerenderedView**: A custom Django view that intelligently serves pre-rendered HTML files from vite-ssg builds. It:
- Serves pre-rendered HTML files for SSG routes when they exist
- Falls back to `index.html` for client-side Vue Router handling
- Makes the SPA compatible with web crawlers and archive.org (Wayback Machine)
- Is used as the catch-all view after API routes

**Template System**: Templates are configured with intelligent caching:
- **Production**: Uses Django's cached template loader for optimal performance
- **Development**: Uses non-cached loaders for hot-reloading during development
- Frontend `dist/` folder is served as a Django template directory
- Template caching settings are in `settings.py` based on `DEBUG` mode

## Beta App (Django + HTMX + Alpine.js)

The project includes a parallel implementation of the game ranking site using traditional server-side rendering with Django templates, HTMX for dynamic interactions, and Alpine.js for client-side reactivity. This serves as an alternative to the Vue.js SPA.

### Beta App Structure

- **beta/** - Django app containing:
  - **views.py** - View functions for all beta routes
  - **urls.py** - URL routing for `/beta/` routes
  - **templates/** - Jinja2 templates organized by feature:
    - **base.html** - Main template layout with navigation
    - **games/** - Game list, detail, and search templates
    - **developers/** - Developer list and detail templates
    - **lists/** - Lists and results templates
    - **posts/** - Post/news templates
    - **pages/** - Static page templates
  - **template_tags/** - Custom template filters (beta_filters.py)
  - **middleware.py** - HTMXPushURLMiddleware for HTMX history support

### Beta App Features

**Styling:**
- Uses Bulma CSS framework with Bulmaswatch Cyborg theme for modern dark UI
- Responsive design compatible with all screen sizes

**Template Filters:**
- `from_now` - Converts datetime to relative time (e.g., "2 hours ago")
- Custom utilities for formatting and string manipulation

**Routes:**
- `/beta/` - Home page
- `/beta/games/` - Game list with filtering and search
- `/beta/games/<slug>/` - Game detail view
- `/beta/games/search/` - Game search endpoint (HTMX)
- `/beta/developers/` - Developer list
- `/beta/developers/<slug>/` - Developer detail view
- `/beta/lists/` - Published rankings list
- `/beta/posts/` - News and blog posts
- `/beta/pages/<slug>/` - Static pages

**HTMX Integration:**
- Dynamic filtering without full page reloads
- Infinite scroll or pagination for lists
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

### Migration Status

The beta app is an ongoing migration from the Vue SPA to a Django + HTMX approach. Migration documentation is available in `docs/migration/` directory with guides on:
- What has been migrated to beta
- What still needs work
- Testing procedures
- Known limitations

### Development Notes

- Both the Vue SPA (at `/`) and beta app (at `/beta/`) run in parallel
- The beta app uses the same Django backend and database as the SPA
- Template reloading works in development via Django's non-cached template loaders
- In production, template caching is enabled for performance

## IGDB Integration

The `games/igdb.py` module handles IGDB API integration. Games can be enriched with IGDB data using:
- `Game.get_igdb_data()` - Fetches and saves IGDB data for a single game
- `python manage.py get_igdb` - Batch import IGDB data for all games

IGDB provides cover art, descriptions, developer information, and genres.

## Configuration

### Environment Variables

Environment variables are managed via django-environ (`.env` file):
- `DEBUG` - Enable Django debug mode
- `SECRET_KEY` - Django secret key
- IGDB API credentials (check `games/igdb.py` for specific variable names)

Frontend environment variables (`.env` in frontend/):
- `VITE_API_URL` - API base URL for client-side (defaults to `/api/` in production)
- `VITE_SSG_API_URL` - API base URL for SSG builds (defaults to `http://127.0.0.1:8000/api/` for local development, production URL for builds)
- `VITE_GOOGLE_ANALYTICS_PROPERTY_ID` - Google Analytics property ID for tracking (optional, only if using GA)

### Configuration Files

Backend:
- **`.python-version`** - Specifies Python 3.11 for Heroku deployment (can use different versions locally)
- **`.pre-commit-config.yaml`** - Pre-commit hook configuration for code quality enforcement (Black, Flake8, tests)
- **`.coveragerc`** - Coverage configuration excluding migrations and database vendor-specific code
- **`.flake8`** - Flake8 linter configuration (max line length 88, excludes venv and node_modules)
- **`scripts/run_tests.sh`** - Test execution script used by pre-commit hooks

Frontend:
- **`frontend/vite.config.js`** - Vite configuration including:
  - SSG configuration with `includedRoutes()` function for pre-rendering
  - Test setup with Vitest and 95% coverage thresholds
  - Route limits for SSG builds (currently 10 games/5 developers for testing)
- **`frontend/src/test/setup.js`** - Test environment setup (localStorage mocking)
- **`frontend/.gitignore`** - Includes `.vite-ssg-temp/` to ignore temporary SSG build files
- **`frontend/jsconfig.json`** - JavaScript path configuration

## Database

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Heroku
- The `rank` field on Game determines primary ordering (lower is better)
- `year_rank` and `decade_rank` are calculated automatically on save

## Dependencies

### Backend Dependencies

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

### Frontend Dependencies

**Key Tools:**
- **sass-embedded** - SASS preprocessor for Vite (handles SCSS compilation to CSS)
- **vitest** - Vue component and unit testing framework
- **@vue/test-utils** - Vue component testing utilities
- **jsdom** - DOM implementation for testing

These dependencies are defined in `frontend/package.json` and installed via `npm install`.

## Static Files

- Vite builds frontend to `frontend/dist/`
- Django collectstatic copies to `staticfiles/`
- WhiteNoise serves static files in production
- The `dist` folder is committed to git for Heroku deployment

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Acclaimed Games is a video game ranking and aggregation website that combines data from multiple sources to create comprehensive rankings. The application uses Django backend with a Vue.js 3 frontend and integrates with the IGDB (Internet Game Database) API.

## Development Commands

### Backend (Django)

**Activate virtual environment:**
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

**Build for production:**
```bash
npm run build
```

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

The project is deployed to Heroku. To deploy:

1. Build frontend: `cd frontend && npm run build`
2. Collect static files: `python manage.py collectstatic`
3. Add dist folder: `git add dist`
4. Commit and push: `git commit -av -m "message" && git push heroku master`

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
- 100% test coverage enforced by pre-commit hooks (excludes migrations and database vendor-specific code)
- Run coverage check: `coverage run --source=games manage.py test games.tests && coverage report --fail-under=100`
- Configuration: `.coveragerc` excludes migrations and PostgreSQL-specific optimizations

### Frontend Testing

The Vue.js frontend uses Vitest for testing with the following structure:

**Unit Tests:**
- `frontend/src/__tests__/store.spec.js` - Vuex store tests
- `frontend/src/__tests__/models.spec.js` - Frontend model class tests
- `frontend/src/__tests__/utils.spec.js` - Utility function tests (scroll position, slug parsing)
- `frontend/src/__tests__/objectStore.spec.js` - PersistentObjectStore tests

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
- 100% test coverage enforced by pre-commit hooks and Vitest configuration
- Thresholds configured in `vite.config.js` for statements, branches, functions, and lines

### Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`) to enforce code quality:

1. **Black Formatter** - Automatically formats Python code
2. **Frontend Tests with Coverage** - Runs `npm run test:coverage` and enforces 100% coverage
3. **Django Coverage** - Enforces 100% test coverage threshold (excluding migrations)
4. **Django Test Suite** - Runs full test suite via `scripts/run_tests.sh`

**Note:** Commits will be blocked if any tests fail or coverage drops below 100%.

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

### Frontend Structure

- **frontend/src/**
  - **components/** - Vue components (GameList, GameDetail, DeveloperDetail, etc.)
    - **__tests__/** - Component tests
  - **models/** - Frontend model classes that mirror Django models
  - **router.js** - Vue Router configuration
  - **store.js** - Vuex global state management
  - **objectStore.js** - Persistent localStorage wrapper
  - **constants.js** - Application-wide constants
  - **utils.js** - Utility functions
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

**PersistentObjectStore**: A localStorage wrapper used for persisting state (e.g., scroll position for game list navigation).

**Vuex Store**: Manages global state for genres, platforms, and metadata. Data is lazy-loaded and cached in the store.

**Router Scroll Behavior**: Custom scroll position preservation for game list pages - when navigating from a game list to game detail and back, the scroll position is restored.

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
- `VITE_API_URL` - API base URL (defaults to `/api/` in production)

### Configuration Files

- **`.python-version`** - Specifies Python 3.11 for Heroku deployment
- **`.pre-commit-config.yaml`** - Pre-commit hook configuration for code quality enforcement
- **`.coveragerc`** - Coverage configuration excluding migrations and database vendor-specific code
- **`frontend/vite.config.js`** - Vite configuration including test setup with Vitest and 100% coverage thresholds
- **`frontend/src/test/setup.js`** - Test environment setup (localStorage mocking)

## Database

- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL on Heroku
- The `rank` field on Game determines primary ordering (lower is better)
- `year_rank` and `decade_rank` are calculated automatically on save

## Static Files

- Vite builds frontend to `frontend/dist/`
- Django collectstatic copies to `staticfiles/`
- WhiteNoise serves static files in production
- The `dist` folder is committed to git for Heroku deployment

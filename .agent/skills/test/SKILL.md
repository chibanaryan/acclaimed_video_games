---
name: test
description: Run Django tests with coverage reporting. Use when asked to test, run tests, or check coverage.
---

# Django Tests with Coverage

Run the Django test suite with coverage reporting.

## IMPORTANT: No Parallel Coverage Runs

**Never run coverage or pytest with coverage in parallel with other agents.** Coverage writes to a shared `.coverage` file, so concurrent runs will corrupt data and cause failures. Wait for any running test/coverage process to complete before starting another.

## Basic Commands

```bash
# Run all tests with pytest (same as pre-commit hook)
DATABASE_URL=sqlite:///db.sqlite3 CACHE_URL=locmemcache:// CORS_ALLOWED_ORIGINS=http://localhost pytest

# Run tests with coverage
DATABASE_URL=sqlite:///db.sqlite3 CACHE_URL=locmemcache:// CORS_ALLOWED_ORIGINS=http://localhost coverage run -m pytest
coverage report

# Run specific test file
DATABASE_URL=sqlite:///db.sqlite3 CACHE_URL=locmemcache:// CORS_ALLOWED_ORIGINS=http://localhost pytest games/tests/test_models.py

# Run tests matching a pattern
DATABASE_URL=sqlite:///db.sqlite3 CACHE_URL=locmemcache:// CORS_ALLOWED_ORIGINS=http://localhost pytest -k "test_game"
```

## Coverage Configuration

- **Configuration:** `.coveragerc` excludes migrations and PostgreSQL-specific optimizations

## Test File Locations

All tests are in `games/tests/`:

| File | Description |
|------|-------------|
| `test_admin.py` | Django admin functionality |
| `test_api.py` | API endpoint tests (filtering, serialization, pagination) |
| `test_auth_views.py` | Authentication view tests |
| `test_constants.py` | Constants and configuration tests |
| `test_csp_middleware.py` | Content Security Policy middleware |
| `test_fetch_wikipedia_metadata_command.py` | Wikipedia metadata command tests |
| `test_forms.py` | Form validation and processing |
| `test_game_filter_service.py` | Game filtering service tests |
| `test_genre_hierarchy.py` | Genre hierarchy and relationships |
| `test_get_quotes_command.py` | Quote fetching command tests |
| `test_igdb.py` | IGDB API integration with extensive mocking |
| `test_igdb_importer.py` | IGDB importer logic and batch processing |
| `test_imports.py` | Data import functionality and file parsing |
| `test_main_views.py` | Main application views (game list, detail, search, developers) |
| `test_management.py` | Custom management command tests |
| `test_middleware.py` | HTMXPushURLMiddleware and other middleware |
| `test_mixins.py` | View mixin tests |
| `test_models.py` | Model behavior, IGDB integration, ranking utilities |
| `test_played_games.py` | Played games tracking tests |
| `test_quote_service.py` | Quote service tests |
| `test_template_tags.py` | Custom template filter and tag tests |
| `test_utils.py` | Utility function tests |
| `test_views.py` | Import view integration tests |
| `test_wiki_genre_command.py` | Wikipedia genre command tests |
| `test_wiki_genre_service.py` | Wikipedia genre service tests |

## Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`) to enforce code quality:

1. **Black Formatter** - Automatically formats Python code
2. **Flake8 Linter** - Lints Python code (max line length 88)
3. **Pytest** - Runs test suite via pytest

**Note:** Commits will be blocked if any tests fail or linting fails.

---
name: test
description: Run Django tests with coverage reporting. Use when asked to test, run tests, or check coverage.
---

# Django Tests with Coverage

Run the Django test suite with coverage reporting.

## Basic Commands

```bash
# Run all tests
python3 manage.py test games.tests

# Run tests with coverage
coverage run --source=games manage.py test games.tests
coverage report

# Run with coverage and fail if below threshold
coverage run --source=games manage.py test games.tests && coverage report --fail-under=95
```

## Coverage Requirements

- **Minimum:** 95% test coverage enforced by pre-commit hooks
- **Current:** 100% (exceeds minimum requirement)
- **Configuration:** `.coveragerc` excludes migrations and PostgreSQL-specific optimizations

## Test File Locations

All tests are in `games/tests/`:

| File | Coverage |
|------|----------|
| `test_api.py` | API endpoint tests (filtering, serialization, pagination) |
| `test_models.py` | Model behavior, IGDB integration, ranking utilities |
| `test_igdb.py` | IGDB API integration with extensive mocking |
| `test_igdb_importer.py` | IGDB importer logic and batch processing |
| `test_imports.py` | Data import functionality and file parsing |
| `test_views.py` | Import view integration tests |
| `test_main_views.py` | Main application views (game list, detail, search, developers) |
| `test_admin.py` | Django admin functionality |
| `test_management.py` | Custom management command tests (get_igdb, cleanup, etc.) |
| `test_cleanup_command.py` | Database cleanup command |
| `test_forms.py` | Form validation and processing |
| `test_middleware.py` | HTMXPushURLMiddleware and other middleware |
| `test_template_tags.py` | Custom template filter and tag tests |
| `test_utils.py` | Utility function tests |

## Pre-commit Hooks

The project uses pre-commit hooks (`.pre-commit-config.yaml`) to enforce code quality:

1. **Black Formatter** - Automatically formats Python code
2. **Flake8 Linter** - Lints Python code (max line length 88)
3. **Django Coverage** - Enforces 95% test coverage threshold
4. **Django Test Suite** - Runs full test suite via `scripts/run_tests.sh`

**Note:** Commits will be blocked if any tests fail, coverage drops below 95%, or linting fails.

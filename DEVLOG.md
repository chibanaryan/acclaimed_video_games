# Developer Log

## 2025-11-17

### Client-Side Pagination & Performance
- Implemented client-side pagination for games list using cached data (no API calls between pages)
- Fixed filter removal bugs: year/decade dropdowns and platform/genre tag removal now properly trigger updates
- Optimized page navigation by removing async overhead and using instant `window.scrollTo(0, 0)` instead of smooth scroll
- Added scroll-to-top behavior when navigating between pages

### Pre-rendered HTML Routing (In Progress)
- Created `SPAWithPrerenderedView` to serve pre-rendered HTML files from `dist/` folder
- Updated Django URL routing to check for pre-rendered files first before falling back to SPA
- **Note:** Wayback Machine fix is partial - Django routing now supports serving pre-rendered files, but full compatibility still needs testing
- Rebuilt frontend with updated routing configuration

## 2025-11-16

### Performance & API Work
- Added targeted indexes (including new composite ones) plus migration 0026 to speed up developer/game/list/list membership/post filters without touching data.
- Prefetched developer/list relations in key API views and cached Meta/genre/platform endpoints to eliminate N+1s and reduce load.
- Softened noisy IGDB init logging in DEBUG/tests and documented the backend test command.

### Testing & Code Quality
- Reorganized Django tests into modular structure (`games/tests/`) with 8 test modules (1,299 lines total)
- Added Vue.js test suite using Vitest (5 test files, 263 lines)
- Achieved 100% test coverage for both backend and frontend, enforced 95% threshold
- Set up pre-commit hooks for Black formatting, Flake8 linting, and automated test runs with coverage enforcement
- Applied Black formatter to entire Python codebase (78 files)

### Bug Fixes
- Fixed critical static file serving issue (catch-all route blocking assets)
- Improved IGDB error handling and refactored data fetching
- Enhanced frontend resilience for API failures (store, game list, developer/game detail components)
- Fixed `VITE_API_URL` configuration issues
- Wrapped database delete operations in transactions
- Fixed Google Analytics integration (changed from `import.meta.env.NODE_ENV` to `import.meta.env.PROD` for Vite compatibility)

### Configuration & Documentation
- Created comprehensive `CLAUDE.md` project documentation
- Moved `SENTRY_DSN` to environment variable
- Added `.python-version` (Python 3.11), `.coveragerc`, `.flake8` configuration files
- Updated readme with testing and coverage documentation

### Statistics
**78 files changed: +4,466 additions, -822 deletions** across ~30 commits

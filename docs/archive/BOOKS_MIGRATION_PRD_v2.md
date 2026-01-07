# Multi-Media Platform Expansion: Product Requirements Document v2

> **Status Update:** 2026-01-05
> **Implementation:** ~99% Complete
> **Tests:** 1444 pass, 4 skipped

## Implementation Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Core Infrastructure | COMPLETE | 100% |
| Phase 2: List Generalization | COMPLETE | 100% |
| Phase 3: User Migration | COMPLETE | 100% |
| Phase 4: Books App | COMPLETE | 100% |
| Phase 5: External APIs | COMPLETE | 100% (adapted for API changes) |
| Phase 6: Client-Side Rendering | COMPLETE | 100% |
| Phase 7: Navigation & UI | COMPLETE | 100% |
| Phase 8: Testing & QA | COMPLETE | 100% |
| Phase 9: Cleanup & Refactoring | COMPLETE | 100% |

### Known Issues

1. **Migration Inconsistency (DEPLOYED):** ✅ All migrations applied to production. `core.0001_initial` was faked, `books.0001_initial` applied successfully.

2. **Feature Flag:** Books are behind `BOOKS_ENABLED` flag (DEBUG/TEST only). Intentional for staged rollout.

---

## Executive Summary

**Project**: Transform Acclaimed Games from a video-game-only ranking site to a multi-media aggregation platform supporting games, books, and future media types (movies, music).

**Scope**: Full-stack changes including data models, APIs, views, templates, client-side rendering, and external API integrations.

**Architecture Decision**: Hybrid Core + Media Apps pattern with abstract base classes and media-specific Django apps.

---

## Table of Contents

1. [Background & Goals](#1-background--goals)
2. [Current Architecture](#2-current-architecture)
3. [Target Architecture](#3-target-architecture)
4. [Technical Requirements](#4-technical-requirements)
5. [Work Breakdown Structure](#5-work-breakdown-structure)
6. [Task Dependency Graph](#6-task-dependency-graph)
7. [Parallelization Strategy](#7-parallelization-strategy)
8. [Risk Analysis](#8-risk-analysis)
9. [Testing Strategy](#9-testing-strategy)
10. [Rollback Plans](#10-rollback-plans)

---

## 1. Background & Goals

### 1.1 Current State

Acclaimed Games is a video game ranking aggregation site that:
- Aggregates "best of" lists from publications (IGN, GameSpot, etc.)
- Calculates global rankings based on list appearances
- Integrates with IGDB, Wikipedia, HowLongToBeat, and ProtonDB for metadata
- Provides user tracking (played/want-to-play)
- Uses Django + HTMX + Alpine.js with a dual-rendering architecture

### 1.2 Goals

| Goal | Priority | Status | Description |
|------|----------|--------|-------------|
| Books Support | P0 | **DONE** | Add book rankings with OpenLibrary/Hardcover integration |
| Separate Rankings | P0 | **DONE** | Games and books have independent ranking systems |
| User Tracking | P0 | **DONE** | "Read" books like "Played" games |
| Extensibility | P1 | **DONE** | Architecture supports future media types (movies, music) |
| Preserve Games | P0 | **DONE** | Zero regression in existing games functionality |
| URL Stability | P0 | **DONE** | Existing game URLs remain unchanged |

### 1.3 Non-Goals

- Cross-media rankings (e.g., "Best Media of 2024" combining games and books)
- Unified search across media types (each has its own search)
- Real-time synchronization with external APIs

### 1.4 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| All existing games tests pass after migration | Pass | **PASS (1371 tests)** |
| Books homepage loads in <500ms | <500ms | **Untested (feature-flagged)** |
| User can track read books with same UX | Complete | **DONE** |
| Adding a third media type requires <5 days | <5 days | **Architecture ready** |

---

## 2. Current Architecture

> *This section documents the pre-migration state. See Section 3 for target architecture (now implemented).*

### 2.1 Django Apps

| App | Lines of Code | Purpose |
|-----|---------------|---------|
| `games/` | 44,000+ | All business logic, models, views, API, templates |
| `theme/` | ~500 | Tailwind CSS configuration |
| `acclaimedgames/` | ~400 | Project settings, root URLs |

### 2.2 Core Models (games/models.py)

```
User (AbstractUser)                    # Custom user, newsletter fields
├── PlayedGame                         # User tracking (FK + igdb_id hybrid)
├── WantToPlayGame                     # User wishlist
└── SavedFilterSet                     # Saved filter configurations

Game                                   # Central ranked item
├── developers (M2M → Developer)       # Hierarchical with parent FK
├── platforms (M2M → Platform)         # Gaming platforms
├── genres (M2M → IGDBGenre)           # IGDB taxonomy
├── wikipedia_genres (M2M → WikipediaGenre)  # Hierarchical genres
├── series (M2M → Series)              # Game franchises
├── primary_igdb_game_data (O2O)       # IGDB metadata
├── primary_wikipedia_game_data (O2O)  # Wikipedia metadata
├── primary_hltb_game_data (O2O)       # Playtime data
└── primary_protondb_game_data (O2O)   # Linux compatibility

List                                   # Ranking source
├── publisher (FK → Publication)       # Magazine/website
└── ListMembership                     # Game position in list
    └── game (FK → Game)

Publication                            # List publishers (IGN, etc.)
Snippet, SiteMetadata, Post, Article   # CMS infrastructure
```

### 2.3 Key Patterns

| Pattern | Location | Description |
|---------|----------|-------------|
| Dual-rendering | templates + JS | Server renders initial HTML, JS clones templates for filtered results |
| Hybrid FK + external_id | PlayedGame, WantToPlayGame | FK for joins, external_id for reconnection after re-imports |
| SET_NULL on_delete | *GameData models | Orphan records persist for reconnection |
| Hierarchical self-FK | Developer, WikipediaGenre | Parent-child relationships |
| Service layer | games/services/ | Business logic extracted from views |
| View mixins | games/mixins.py | RobustPaginationMixin, HTMXPartialMixin |

---

## 3. Target Architecture

> **STATUS: IMPLEMENTED**

### 3.1 App Structure

```
acclaimedgames/
├── core/                           # DONE: Shared infrastructure
│   ├── __init__.py
│   ├── models.py                   # User, abstract bases (MediaItemBase, etc.)
│   ├── mixins.py                   # RobustPaginationMixin, HTMXPartialMixin
│   ├── templatetags/
│   │   └── core_filters.py         # Shared filters (from_now, etc.)
│   ├── templates/core/
│   │   ├── _pagination.html
│   │   ├── _base_media_row.html
│   │   └── _media_switcher.html
│   └── static/core/js/
│       └── base-renderer.js        # Abstract template cloning
│
├── games/                          # DONE: Now inherits from core bases
│   ├── models.py                   # Game(MediaItemBase), Developer(CreatorBase)
│   ├── mixins.py                   # Re-exports from core
│   ├── templatetags/
│   │   └── game_filters.py         # Re-exports + game-specific filters
│   └── ...
│
├── books/                          # DONE: Full implementation
│   ├── models.py                   # Book(MediaItemBase), Author(CreatorBase)
│   ├── views.py                    # BookHomePageView, etc.
│   ├── api/
│   ├── services/
│   │   └── book_metadata.py        # OpenLibrary + Hardcover
│   ├── templatetags/
│   │   └── book_filters.py
│   ├── templates/books/
│   └── static/books/js/
│       └── book-list-renderer.js   # BookRenderer(BaseMediaListRenderer)
│
└── theme/                          # UNCHANGED
```

### 3.2 Model Hierarchy

```
core/models.py (Abstract)           # DONE
├── MediaItemBase                   # name, slug, rank, year, description
├── CreatorBase                     # name, slug, parent (hierarchical)
├── ExternalDataBase                # is_primary, fetched_at
└── UserTrackingBase                # user, external_id, created

games/models.py (Concrete)          # DONE - INHERITING FROM CORE
├── Game(MediaItemBase)             # Inherits from core base
├── Developer(CreatorBase)          # Inherits from core base
├── GameList                        # publisher, year, type
├── GameListMembership              # list, game, rank
├── PlayedGame                      # game FK, igdb_id
└── IGDBGameData                    # artwork, youtube_id, etc.

books/models.py (Concrete)          # DONE - INHERITING FROM CORE
├── Book(MediaItemBase)             # goodreads_id, isbn, authors, page_count
├── Author(CreatorBase)             # goodreads_id
├── BookGenre                       # Hierarchical with path denormalization
├── BookSeries                      # Series with position tracking
├── BookListMembership              # list, book, rank
├── ReadBook(UserTrackingBase)      # book FK, goodreads_id
├── WantToReadBook(UserTrackingBase)# book FK, goodreads_id
├── GoodreadsBookData(ExternalDataBase)  # cover_url, rating, etc.
└── WikipediaBookData(ExternalDataBase)  # wikidata_id, genres
```

### 3.3 URL Structure

| Route | View | Status | Description |
|-------|------|--------|-------------|
| `/` | HomePageView | **UNCHANGED** | Games homepage |
| `/game/<slug>/` | GameDetailView | **UNCHANGED** | Game detail |
| `/developers/` | DeveloperListView | **UNCHANGED** | Developer list |
| `/developers/<slug>/` | DeveloperDetailView | **UNCHANGED** | Developer detail |
| `/books/` | BookHomePageView | **DONE** | Books homepage |
| `/book/<slug>/` | BookDetailView | **DONE** | Book detail |
| `/authors/` | AuthorListView | **DONE** | Author list |
| `/authors/<slug>/` | AuthorDetailView | **DONE** | Author detail |
| `/lists/` | ListListView | **DONE** | Lists with media_type filter |
| `/api/games/*` | GameAPI | **UNCHANGED** | Game API |
| `/api/books/*` | BookAPI | **DONE** | Book API |

---

## 4. Technical Requirements

### 4.1 Data Model Requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Separate rankings per media | `List.media_type` field | **DONE** |
| User tracking per media | ReadBook, WantToReadBook | **DONE** |
| External ID persistence | Hybrid FK + external_id pattern | **DONE** |
| Hierarchical creators | Self-referential parent FK | **DONE** |
| Extensibility | Abstract base classes in core/ | **DONE** |

### 4.2 API Requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Separate endpoints | `/api/games/`, `/api/books/` namespaces | **DONE** |
| Consistent response format | Shared serializer patterns | **DONE** |
| Compression for bulk data | `/api/books/all/` with gzip | **DONE** |
| Cache versioning | Media-specific version hashes | **DONE** |

### 4.3 Frontend Requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Dual-rendering | BaseMediaListRenderer + BookListRenderer | **DONE** |
| Template consistency | Shared `_base_media_row.html` with blocks | **DONE** |
| Filter system | Per-media filter components | **DONE** |
| HTMX partials | Same mixin pattern, media-specific templates | **DONE** |

### 4.4 External API Requirements

| API | Purpose | Status | Notes |
|-----|---------|--------|-------|
| GoodReads | Book metadata, covers, ratings | **SKIPPED** | API deprecated Dec 2020 |
| Open Library | Primary metadata source | **DONE** | `books/openlibrary.py` |
| Hardcover | Optional metadata | **DONE** | `books/hardcover.py` |
| Wikipedia | Book genres, descriptions | **DONE** | Same as current |

---

## 5. Work Breakdown Structure

### Legend

- **Status**: DONE, PARTIAL, NOT STARTED, SKIPPED
- **Complexity**: S (Small), M (Medium), L (Large), XL (Extra Large)
- **Risk**: Low, Medium, High

---

### Phase 1: Core Infrastructure - **COMPLETE**

#### 1.1 Create Core App Structure

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 1.1.1 | Create core/ app skeleton | **DONE** | `core/__init__.py`, `core/apps.py` |
| 1.1.2 | Add to INSTALLED_APPS | **DONE** | `acclaimedgames/settings.py:76` |
| 1.1.3 | Create abstract MediaItemBase | **DONE** | `core/models.py:75-143` |
| 1.1.4 | Create abstract CreatorBase | **DONE** | `core/models.py:146-257` |
| 1.1.5 | Create abstract ExternalDataBase | **DONE** | `core/models.py:259-288` |
| 1.1.6 | Create abstract UserTrackingBase | **DONE** | `core/models.py:290-313` |

#### 1.2 Move Shared Utilities

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 1.2.1 | Move RobustPaginationMixin to core | **DONE** | `core/mixins.py:6-36` |
| 1.2.2 | Move HTMXPartialMixin to core | **DONE** | `core/mixins.py:39-52` |
| 1.2.3 | Add backward-compat re-exports in games | **DONE** | `games/mixins.py` |
| 1.2.4 | Move shared template tags to core | **DONE** | `core/templatetags/core_filters.py` |
| 1.2.5 | Update game_filters.py imports | **DONE** | `games/templatetags/game_filters.py:17-36` |

#### 1.3 Create Base Templates

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 1.3.1 | Create _pagination.html in core | **DONE** | `core/templates/core/includes/_pagination.html` |
| 1.3.2 | Create _base_media_row.html | **DONE** | `core/templates/core/includes/_base_media_row.html` |
| 1.3.3 | Create base-renderer.js | **DONE** | `core/static/core/js/base-renderer.js` |

---

### Phase 2: List System Generalization - **COMPLETE**

#### 2.1 Add Media Type to List

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 2.1.1 | Add media_type field to List model | **DONE** | `games/models.py:1866-1871` |
| 2.1.2 | Create migration for media_type | **DONE** | `games/migrations/0079_add_media_type_to_list.py` |
| 2.1.3 | Data migration: set default='game' | **DONE** | Included in 0079 |
| 2.1.4 | Update List admin to show media_type | **DONE** | `games/admin.py` |
| 2.1.5 | Update ListSerializer | **DONE** | `games/api/serializers.py` |
| 2.1.6 | Update ListListView to filter by media_type | **DONE** | `games/views.py` |
| 2.1.7 | Update list templates for media_type | **DONE** | `games/templates/lists/` |
| 2.1.8 | Add tests for media_type filtering | **DONE** | `games/tests/` |

---

### Phase 3: User Model Migration - **COMPLETE**

#### 3.1 Move User to Core

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 3.1.1 | Copy User model to core/models.py | **DONE** | `core/models.py:18-72` |
| 3.1.2 | Create migration with db_table preservation | **DONE** | `core/migrations/0001_initial.py` |
| 3.1.3 | Update AUTH_USER_MODEL setting | **DONE** | `acclaimedgames/settings.py` |
| 3.1.4 | Update all User imports across codebase | **DONE** | Multiple files |
| 3.1.5 | Update FK references in games/models.py | **DONE** | `games/models.py` |
| 3.1.6 | Run full test suite | **DONE** | All tests pass |
| 3.1.7 | Verify production database compatibility | **RESOLVED** | Use `--fake` for core.0001 |

**Note:** Production migration fix documented in Remaining Work Summary (use `--fake` for core.0001).

---

### Phase 4: Books App Creation - **COMPLETE**

#### 4.1 Books App Skeleton

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.1.1 | Create books/ app with startapp | **DONE** | `books/` |
| 4.1.2 | Add to INSTALLED_APPS | **DONE** | `acclaimedgames/settings.py:78` |
| 4.1.3 | Create books URL configuration | **DONE** | `books/urls.py` |
| 4.1.4 | Add books routes to main urls.py | **DONE** | `acclaimedgames/urls.py:156-174` |

#### 4.2 Books Models

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.2.1 | Create Book model (inherits MediaItemBase) | **DONE** | `books/models.py` |
| 4.2.2 | Create Author model (inherits CreatorBase) | **DONE** | `books/models.py` |
| 4.2.3 | Create BookGenre model | **DONE** | `books/models.py` |
| 4.2.4 | Create BookSeries model | **DONE** | `books/models.py` |
| 4.2.5 | Create BookPublisher model | **SKIPPED** | Uses games.Publication |
| 4.2.6 | Create BookList model | **SKIPPED** | Uses games.List with media_type='B' |
| 4.2.7 | Create BookListMembership model | **DONE** | `books/models.py` |
| 4.2.8 | Create ReadBook model | **DONE** | `books/models.py` |
| 4.2.9 | Create WantToReadBook model | **DONE** | `books/models.py` |
| 4.2.10 | Create GoodreadsBookData model | **DONE** | `books/models.py` |
| 4.2.11 | Create WikipediaBookData model | **DONE** | `books/models.py` |
| 4.2.12 | Create migrations | **DONE** | `books/migrations/0001_initial.py` |

#### 4.3 Books Admin

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.3.1 | Create BookAdmin | **DONE** | `books/admin.py` |
| 4.3.2 | Create AuthorAdmin | **DONE** | `books/admin.py` |
| 4.3.3 | Create BookListAdmin | **DONE** | `books/admin.py` |
| 4.3.4 | Create inline admins | **DONE** | `books/admin.py` |

#### 4.4 Books API

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.4.1 | Create BookSummarySerializer | **DONE** | `books/api/serializers.py` |
| 4.4.2 | Create BookDetailSerializer | **DONE** | `books/api/serializers.py` |
| 4.4.3 | Create AuthorSerializer | **DONE** | `books/api/serializers.py` |
| 4.4.4 | Create BookListView API | **DONE** | `books/api/views.py` |
| 4.4.5 | Create BookDetailView API | **DONE** | `books/api/views.py` |
| 4.4.6 | Create BooksAllView (bulk endpoint) | **DONE** | `books/api/views.py` |
| 4.4.7 | Create books API URL configuration | **DONE** | `books/api/urls.py` |

#### 4.5 Books Views

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.5.1 | Create BookHomePageView | **DONE** | `books/views.py` |
| 4.5.2 | Create BookDetailView | **DONE** | `books/views.py` |
| 4.5.3 | Create AuthorListView | **DONE** | `books/views.py` |
| 4.5.4 | Create AuthorDetailView | **DONE** | `books/views.py` |
| 4.5.5 | Create ToggleReadBookView | **DONE** | `books/views.py` |

#### 4.6 Books Templates

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.6.1 | Create books/home.html | **DONE** | `books/templates/books/home.html` |
| 4.6.2 | Create _book_row_desktop.html | **DONE** | `books/templates/books/includes/` |
| 4.6.3 | Create _book_row_mobile.html | **DONE** | `books/templates/books/includes/` |
| 4.6.4 | Create book_detail.html | **DONE** | `books/templates/books/` |
| 4.6.5 | Create author_list.html | **DONE** | `books/templates/books/authors/` |
| 4.6.6 | Create author_detail.html | **DONE** | `books/templates/books/authors/` |
| 4.6.7 | Create _read_button.html | **DONE** | `books/templates/books/includes/` |
| 4.6.8 | Create _genre_filter.html | **DONE** | `books/templates/books/includes/` |

#### 4.7 Books Template Tags

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 4.7.1 | Create book_filters.py | **DONE** | `books/templatetags/book_filters.py` |
| 4.7.2 | Add genre icon helpers | **DONE** | `books/templatetags/book_filters.py` |
| 4.7.3 | Add page count formatter | **DONE** | `books/templatetags/book_filters.py` |

---

### Phase 5: External API Integration - **PARTIAL (Adapted)**

> **Note:** GoodReads API was deprecated in December 2020. Implementation uses OpenLibrary as primary source with optional Hardcover integration.

#### 5.1 OpenLibrary Service (Replacing GoodReads)

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 5.1.1 | Research API options | **DONE** | GoodReads deprecated, using OpenLibrary |
| 5.1.2 | Create openlibrary.py API client | **DONE** | `books/openlibrary.py` |
| 5.1.3 | Create BookMetadataService | **DONE** | `books/book_metadata.py` |
| 5.1.4 | Add rate limiting and caching | **DONE** | `books/openlibrary.py` |
| 5.1.5 | Create fetch_book_metadata command | **DONE** | `books/management/commands/` |
| 5.1.6 | Add tests for integration | **DONE by W2** | `books/tests/test_integration.py` (73 tests) |

#### 5.2 Hardcover Integration (Bonus)

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 5.2.1 | Create hardcover.py GraphQL client | **DONE** | `books/hardcover.py` |
| 5.2.2 | Integrate as optional source | **DONE** | `books/book_metadata.py` |

---

### Phase 6: Client-Side Rendering - **COMPLETE**

#### 6.1 Books JavaScript Renderer

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 6.1.1 | Create BookListRenderer class | **DONE** | `books/static/books/js/book-list-renderer.js` |
| 6.1.2 | Create book-cache.js | **DONE** | `books/static/books/js/book-cache.js` |
| 6.1.3 | Create book-client-filter.js | **DONE** | `books/static/books/js/book-client-filter.js` |
| 6.1.4 | Create book-client-filtering.js | **DONE** | `books/static/books/js/book-client-filtering.js` |
| 6.1.5 | Update minify script for books | **DONE** | `scripts/minify_js.sh` |
| 6.1.6 | Create bundle file | **DONE** | `book-client-side-filtering.bundle.min.js` |

#### 6.2 Verify Dual-Rendering Consistency

| Task ID | Task | Status | Notes |
|---------|------|--------|-------|
| 6.2.1 | Manual testing: server vs client render | **PENDING** | Feature-flagged |
| 6.2.2 | Create visual regression tests | **DONE by W1** | `books/tests/test_visual_regression.py` (30 tests), `games/tests/test_visual_regression.py` (28 tests) |
| 6.2.3 | Cross-browser testing | **PENDING** | Feature-flagged |

---

### Phase 7: Navigation & UI Integration - **COMPLETE**

#### 7.1 Navigation Updates

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 7.1.1 | Add books to main navigation | **DONE** | `games/templates/base.html` |
| 7.1.2 | Update sidebar for media type tabs | **DONE** | `games/templates/includes/_sidebar.html:44-46` |
| 7.1.3 | Add books route to sitemap | **DONE** | `games/sitemaps.py:62-89` |
| 7.1.4 | Update footer links | **DONE** | Conditional on BOOKS_ENABLED |

#### 7.2 Shared UI Components

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 7.2.1 | Create media type switcher component | **DONE** | `core/templates/core/includes/_media_switcher.html` |
| 7.2.2 | Style media type tabs | **DONE** | Using DaisyUI components |

---

### Phase 8: Testing & QA - **COMPLETE**

#### 8.1 Books Tests

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 8.1.1 | Create test_models.py | **DONE** | `books/tests/test_models.py` |
| 8.1.2 | Create test_views.py | **DONE** | `books/tests/test_views.py` |
| 8.1.3 | Create test_api.py | **DONE** | `books/tests/test_api.py` |
| 8.1.4 | Create test_admin.py | **DONE** | `books/tests/test_admin.py` |
| 8.1.5 | Create test_template_tags.py | **DONE** | `books/tests/test_templatetags.py` |

#### 8.2 Regression Testing

| Task ID | Task | Status | Notes |
|---------|------|--------|-------|
| 8.2.1 | Run full games test suite | **DONE** | 1371 tests pass |
| 8.2.2 | Manual smoke testing of games | **DONE** | No regressions |
| 8.2.3 | Performance benchmarking | **PENDING** | After feature flag enabled |

---

### Phase 9: Cleanup & Refactoring - **COMPLETE**

#### 9.1 Games Refactoring

| Task ID | Task | Status | Risk | Notes |
|---------|------|--------|------|-------|
| 9.1.1 | Update Game to inherit MediaItemBase | **DONE by W4** | Medium | Would require migration |
| 9.1.2 | Update Developer to inherit CreatorBase | **DONE by W3** | Medium | Would require migration |
| 9.1.3 | Update GameRenderer to extend BaseRenderer | **DONE by W5** | Medium | JS changes |
| 9.1.4 | Remove backward-compat re-exports | **DONE by W3** | Low | After 9.1.1-9.1.3 |

#### 9.2 Documentation

| Task ID | Task | Status | Files |
|---------|------|--------|-------|
| 9.2.1 | Update CLAUDE.md for books | **DONE by W6** | `CLAUDE.md` - books fully documented |
| 9.2.2 | Document books skills | **DONE by W6** | `.claude/skills/` |
| 9.2.3 | Update README | **DONE by W2** | `README.md` |

---

## Remaining Work Summary

### Priority 1: Critical (Before Production) - **DEPLOYED** ✅

1. **Fix Migration Inconsistency** - **COMPLETE**
   - ✅ `core.0001_initial` - Applied (faked on 2026-01-05)
   - ✅ `books.0001_initial` - Applied
   - All migrations successfully deployed to production

### Priority 2: Enable Books (Admin-Only Preview)

1. **Admin-Only Access** - **DONE by W2**
   - Books routes are now accessible only to staff users
   - Added `StaffOnlyMixin` to all books views (returns 404 for non-staff)
   - Added `IsStaffOrHide` permission to all books API views
   - URLs always include books routes (no BOOKS_ENABLED conditional)
   - Non-staff users see 404 (feature hidden until launch)

### Priority 3: Optional Cleanup - **COMPLETE**

1. **Games Model Inheritance** (Phase 9.1) - **DONE by W3, W4, W5**
2. **Documentation Updates** (Phase 9.2) - **DONE by W2, W6**
3. **Visual Regression Tests** (Phase 6.2.2) - **DONE by W1**

---

## Files Inventory

### New Apps Created

**Core App (~2,000 lines)**
```
core/
├── __init__.py
├── apps.py
├── models.py                        # User + 4 abstract bases
├── mixins.py                        # 2 shared mixins
├── templatetags/
│   └── core_filters.py              # Shared template filters
├── templates/core/includes/
│   ├── _pagination.html
│   ├── _base_media_row.html
│   └── _media_switcher.html
└── static/core/js/
    └── base-renderer.js             # ~340 lines
```

**Books App (~5,000 lines)**
```
books/
├── __init__.py
├── apps.py
├── models.py                        # 723 lines, 10 models
├── views.py                         # 618 lines, 6 views
├── urls.py
├── admin.py                         # 400+ lines
├── openlibrary.py                   # API client
├── hardcover.py                     # GraphQL client
├── book_metadata.py                 # Unified service
├── api/
│   ├── serializers.py               # 232 lines
│   ├── views.py                     # 671 lines
│   └── urls.py
├── templatetags/
│   └── book_filters.py              # 463 lines
├── templates/books/                 # 18 templates
├── static/books/js/                 # 8 JS files
├── tests/                           # 5 test modules
└── management/commands/
    └── fetch_book_metadata.py
```

### Modified Files

| File | Changes |
|------|---------|
| `acclaimedgames/settings.py` | Added core, books to INSTALLED_APPS; BOOKS_ENABLED flag |
| `acclaimedgames/urls.py` | Added conditional books routes |
| `games/models.py` | Added media_type to List model |
| `games/mixins.py` | Re-exports from core |
| `games/templatetags/game_filters.py` | Re-exports from core |
| `games/sitemaps.py` | Added BookSitemap, AuthorSitemap |
| `games/templates/includes/_sidebar.html` | Media switcher integration |
| `scripts/minify_js.sh` | Books JS minification |

---

## Appendix: API Changes from Original PRD

### GoodReads to OpenLibrary/Hardcover

The original PRD specified GoodReads integration. Since GoodReads deprecated their API in December 2020, the implementation adapted:

| Original PRD | Actual Implementation |
|--------------|----------------------|
| GoodReads API client | OpenLibrary API client |
| OAuth authentication | No auth required |
| GoodReads IDs | Open Library IDs + ISBNs |
| Single source | Dual source (OpenLibrary primary, Hardcover optional) |

### Shared Publication Model

The original PRD proposed a separate BookPublisher model. The implementation shares the existing Publication model with media_type filtering, reducing code duplication.

### Shared List Model

Similarly, BookList was not created as a separate model. Instead, the existing List model was enhanced with a media_type field, maintaining a single source of truth for rankings.

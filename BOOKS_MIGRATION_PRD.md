# Multi-Media Platform Expansion: Product Requirements Document

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

| Goal | Priority | Description |
|------|----------|-------------|
| Books Support | P0 | Add book rankings with GoodReads/Wikipedia integration |
| Separate Rankings | P0 | Games and books have independent ranking systems |
| User Tracking | P0 | "Read" books like "Played" games |
| Extensibility | P1 | Architecture supports future media types (movies, music) |
| Preserve Games | P0 | Zero regression in existing games functionality |
| URL Stability | P0 | Existing game URLs remain unchanged |

### 1.3 Non-Goals

- Cross-media rankings (e.g., "Best Media of 2024" combining games and books)
- Unified search across media types (each has its own search)
- Real-time synchronization with external APIs

### 1.4 Success Metrics

- All existing games tests pass after migration
- Books homepage loads in <500ms (comparable to games)
- User can track read books with same UX as played games
- Adding a third media type requires <5 days of work

---

## 2. Current Architecture

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

### 2.4 File Statistics

| Directory | Files | Purpose |
|-----------|-------|---------|
| `games/models.py` | 2,079 lines | 25 models |
| `games/views.py` | 3,226 lines | 25+ class-based views |
| `games/api/` | 1,200 lines | REST API (serializers, views) |
| `games/services/` | 2,000 lines | 13 service modules |
| `games/templates/` | 80 files | HTMX-enabled templates |
| `games/static/games/js/` | 3,000 lines | Client-side filtering, rendering |
| `games/tests/` | 12,000 lines | 36 test files |

---

## 3. Target Architecture

### 3.1 App Structure

```
acclaimedgames/
├── core/                           # NEW: Shared infrastructure
│   ├── __init__.py
│   ├── models.py                   # User, Publication, abstract bases
│   ├── mixins.py                   # RobustPaginationMixin, HTMXPartialMixin
│   ├── views.py                    # BaseMediaListView, BaseMediaDetailView
│   ├── services/
│   │   └── ranking_service.py      # Shared ranking calculations
│   ├── templatetags/
│   │   └── core_filters.py         # Shared filters (from_now, etc.)
│   ├── templates/core/
│   │   ├── _pagination.html
│   │   └── _base_media_row.html
│   └── static/core/js/
│       └── base-renderer.js        # Abstract template cloning
│
├── games/                          # REFACTORED: Inherits from core
│   ├── models.py                   # Game(MediaItemBase), Developer(CreatorBase), etc.
│   ├── views.py                    # GameListView(BaseMediaListView)
│   ├── api/
│   ├── services/
│   │   ├── igdb_importer.py
│   │   └── wiki_genre_service.py
│   ├── templatetags/
│   │   └── game_filters.py         # platform_families (game-specific)
│   ├── templates/games/
│   └── static/games/js/
│       └── game-list-renderer.js   # GameRenderer(BaseRenderer)
│
├── books/                          # NEW: Follows same patterns
│   ├── models.py                   # Book(MediaItemBase), Author(CreatorBase)
│   ├── views.py                    # BookListView(BaseMediaListView)
│   ├── api/
│   ├── services/
│   │   └── goodreads_service.py
│   ├── templatetags/
│   │   └── book_filters.py
│   ├── templates/books/
│   └── static/books/js/
│       └── book-list-renderer.js
│
└── theme/                          # UNCHANGED
```

### 3.2 Model Hierarchy

```
core/models.py (Abstract)
├── MediaItemBase                   # name, slug, rank, year, description
├── CreatorBase                     # name, slug, parent (hierarchical)
├── ExternalDataBase                # is_primary, fetched_at
└── UserTrackingBase                # user, external_id, created

games/models.py (Concrete)
├── Game(MediaItemBase)             # igdb_id, developers, platforms, genres
├── Developer(CreatorBase)          # igdb_id
├── GameList                        # publisher, year, type
├── GameListMembership              # list, game, rank
├── PlayedGame(UserTrackingBase)    # game FK, igdb_id
└── IGDBGameData(ExternalDataBase)  # artwork, youtube_id, etc.

books/models.py (Concrete)
├── Book(MediaItemBase)             # goodreads_id, isbn, authors, page_count
├── Author(CreatorBase)             # goodreads_id
├── BookList                        # publisher, year, type
├── BookListMembership              # list, book, rank
├── ReadBook(UserTrackingBase)      # book FK, goodreads_id
└── GoodreadsBookData(ExternalDataBase)  # cover_url, rating, etc.
```

### 3.3 URL Structure

| Route | View | Description |
|-------|------|-------------|
| `/` | HomePageView | Games homepage (unchanged) |
| `/game/<slug>/` | GameDetailView | Game detail (unchanged) |
| `/developers/` | DeveloperListView | Developer list (unchanged) |
| `/developers/<slug>/` | DeveloperDetailView | Developer detail (unchanged) |
| `/books/` | BookHomePageView | Books homepage (NEW) |
| `/book/<slug>/` | BookDetailView | Book detail (NEW) |
| `/authors/` | AuthorListView | Author list (NEW) |
| `/authors/<slug>/` | AuthorDetailView | Author detail (NEW) |
| `/lists/` | ListListView | Lists with media_type filter |
| `/api/games/*` | GameAPI | Game API (unchanged) |
| `/api/books/*` | BookAPI | Book API (NEW) |

---

## 4. Technical Requirements

### 4.1 Data Model Requirements

| Requirement | Implementation |
|-------------|----------------|
| Separate rankings per media | `List.media_type` field, separate ListMembership FKs |
| User tracking per media | Separate models: PlayedGame, ReadBook (pattern reuse) |
| External ID persistence | Hybrid FK + external_id pattern |
| Hierarchical creators | Self-referential parent FK (Developer, Author) |
| Extensibility | Abstract base classes in core/ |

### 4.2 API Requirements

| Requirement | Implementation |
|-------------|----------------|
| Separate endpoints | `/api/games/`, `/api/books/` namespaces |
| Consistent response format | Shared serializer patterns from core |
| Compression for bulk data | Same `/api/books/all/` pattern as games |
| Cache versioning | Media-specific version hashes |

### 4.3 Frontend Requirements

| Requirement | Implementation |
|-------------|----------------|
| Dual-rendering | BaseRenderer class + media-specific subclasses |
| Template consistency | Shared `_base_media_row.html` with blocks |
| Filter system | Per-media filter components |
| HTMX partials | Same mixin pattern, media-specific templates |

### 4.4 External API Requirements

| API | Purpose | Rate Limits |
|-----|---------|-------------|
| GoodReads | Book metadata, covers, ratings | TBD (requires OAuth) |
| Open Library | Fallback metadata, ISBNs | 100 req/IP/5min |
| Wikipedia | Book genres, descriptions | Same as current |

---

## 5. Work Breakdown Structure

### Legend

- **Complexity**: S (Small, <1 day), M (Medium, 1-3 days), L (Large, 3-5 days), XL (Extra Large, 5+ days)
- **Risk**: Low, Medium, High
- **Parallelizable**: Yes (can run with other tasks), No (must run alone), Partial (some parts parallel)

---

### Phase 1: Core Infrastructure

#### 1.1 Create Core App Structure

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 1.1.1 | Create core/ app skeleton | `core/__init__.py`, `core/apps.py` | S | Low | None |
| 1.1.2 | Add to INSTALLED_APPS | `acclaimedgames/settings.py` | S | Low | 1.1.1 |
| 1.1.3 | Create abstract MediaItemBase | `core/models.py` | M | Low | 1.1.1 |
| 1.1.4 | Create abstract CreatorBase | `core/models.py` | S | Low | 1.1.1 |
| 1.1.5 | Create abstract ExternalDataBase | `core/models.py` | S | Low | 1.1.1 |
| 1.1.6 | Create abstract UserTrackingBase | `core/models.py` | S | Low | 1.1.1 |

**Parallelization**: 1.1.3-1.1.6 can be done in parallel after 1.1.1-1.1.2

#### 1.2 Move Shared Utilities

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 1.2.1 | Move RobustPaginationMixin to core | `core/mixins.py`, `games/mixins.py` | S | Low | 1.1.2 |
| 1.2.2 | Move HTMXPartialMixin to core | `core/mixins.py`, `games/mixins.py` | S | Low | 1.1.2 |
| 1.2.3 | Add backward-compat re-exports in games | `games/mixins.py` | S | Low | 1.2.1, 1.2.2 |
| 1.2.4 | Move shared template tags to core | `core/templatetags/core_filters.py` | M | Low | 1.1.2 |
| 1.2.5 | Update game_filters.py imports | `games/templatetags/game_filters.py` | S | Low | 1.2.4 |

**Parallelization**: 1.2.1-1.2.2 parallel, 1.2.4 parallel with 1.2.1-1.2.2

#### 1.3 Create Base Templates

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 1.3.1 | Create _pagination.html in core | `core/templates/core/_pagination.html` | S | Low | 1.1.2 |
| 1.3.2 | Create _base_media_row.html | `core/templates/core/_base_media_row.html` | M | Medium | 1.1.2 |
| 1.3.3 | Create base-renderer.js | `core/static/core/js/base-renderer.js` | L | Medium | 1.1.2 |

**Parallelization**: All can run in parallel

---

### Phase 2: List System Generalization

#### 2.1 Add Media Type to List

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 2.1.1 | Add media_type field to List model | `games/models.py` | S | Low | None |
| 2.1.2 | Create migration for media_type | `games/migrations/` | S | Low | 2.1.1 |
| 2.1.3 | Data migration: set default='game' | `games/migrations/` | S | Low | 2.1.2 |
| 2.1.4 | Update List admin to show media_type | `games/admin.py` | S | Low | 2.1.1 |
| 2.1.5 | Update ListSerializer | `games/api/serializers.py` | S | Low | 2.1.1 |
| 2.1.6 | Update ListListView to filter by media_type | `games/views.py` | M | Low | 2.1.1 |
| 2.1.7 | Update list templates for media_type | `games/templates/lists/` | S | Low | 2.1.1 |
| 2.1.8 | Add tests for media_type filtering | `games/tests/test_list_views.py` | M | Low | 2.1.6 |

**Parallelization**: 2.1.4-2.1.7 can run in parallel after 2.1.1

---

### Phase 3: User Model Migration (OPTIONAL - Higher Risk)

#### 3.1 Move User to Core

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 3.1.1 | Copy User model to core/models.py | `core/models.py` | S | Low | Phase 1 |
| 3.1.2 | Create migration with db_table preservation | `core/migrations/` | M | High | 3.1.1 |
| 3.1.3 | Update AUTH_USER_MODEL setting | `acclaimedgames/settings.py` | S | Medium | 3.1.2 |
| 3.1.4 | Update all User imports across codebase | Multiple files (~30) | M | Medium | 3.1.3 |
| 3.1.5 | Update FK references in games/models.py | `games/models.py` | M | Medium | 3.1.3 |
| 3.1.6 | Run full test suite | All tests | L | High | 3.1.5 |
| 3.1.7 | Verify production database compatibility | Manual testing | M | High | 3.1.6 |

**Parallelization**: None - must be sequential due to high risk

**Alternative**: Skip Phase 3 entirely. Keep User in games/. Books can still reference it via settings.AUTH_USER_MODEL.

---

### Phase 4: Books App Creation

#### 4.1 Books App Skeleton

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.1.1 | Create books/ app with startapp | `books/` | S | Low | Phase 1 |
| 4.1.2 | Add to INSTALLED_APPS | `acclaimedgames/settings.py` | S | Low | 4.1.1 |
| 4.1.3 | Create books URL configuration | `books/urls.py` | S | Low | 4.1.1 |
| 4.1.4 | Add books routes to main urls.py | `acclaimedgames/urls.py` | S | Low | 4.1.3 |

**Parallelization**: Sequential, but quick

#### 4.2 Books Models

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.2.1 | Create Book model (inherits MediaItemBase) | `books/models.py` | M | Low | 4.1.1, Phase 1 |
| 4.2.2 | Create Author model (inherits CreatorBase) | `books/models.py` | M | Low | 4.1.1 |
| 4.2.3 | Create BookGenre model | `books/models.py` | S | Low | 4.1.1 |
| 4.2.4 | Create BookSeries model | `books/models.py` | S | Low | 4.1.1 |
| 4.2.5 | Create BookPublisher model | `books/models.py` | S | Low | 4.1.1 |
| 4.2.6 | Create BookList model | `books/models.py` | S | Low | 4.1.1 |
| 4.2.7 | Create BookListMembership model | `books/models.py` | S | Low | 4.2.1, 4.2.6 |
| 4.2.8 | Create ReadBook model | `books/models.py` | S | Low | 4.2.1 |
| 4.2.9 | Create WantToReadBook model | `books/models.py` | S | Low | 4.2.1 |
| 4.2.10 | Create GoodreadsBookData model | `books/models.py` | M | Low | 4.2.1 |
| 4.2.11 | Create WikipediaBookData model | `books/models.py` | M | Low | 4.2.1 |
| 4.2.12 | Create migrations | `books/migrations/` | S | Low | 4.2.1-4.2.11 |

**Parallelization**: 4.2.1-4.2.11 can all be done in parallel (same file, different sections)

#### 4.3 Books Admin

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.3.1 | Create BookAdmin | `books/admin.py` | M | Low | 4.2.1 |
| 4.3.2 | Create AuthorAdmin | `books/admin.py` | S | Low | 4.2.2 |
| 4.3.3 | Create BookListAdmin | `books/admin.py` | S | Low | 4.2.6 |
| 4.3.4 | Create inline admins | `books/admin.py` | M | Low | 4.3.1-4.3.3 |

**Parallelization**: 4.3.1-4.3.3 parallel

#### 4.4 Books API

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.4.1 | Create BookSummarySerializer | `books/api/serializers.py` | M | Low | 4.2.1 |
| 4.4.2 | Create BookDetailSerializer | `books/api/serializers.py` | M | Low | 4.2.1 |
| 4.4.3 | Create AuthorSerializer | `books/api/serializers.py` | S | Low | 4.2.2 |
| 4.4.4 | Create BookListView API | `books/api/views.py` | M | Low | 4.4.1 |
| 4.4.5 | Create BookDetailView API | `books/api/views.py` | M | Low | 4.4.2 |
| 4.4.6 | Create BooksAllView (bulk endpoint) | `books/api/views.py` | L | Medium | 4.4.1 |
| 4.4.7 | Create books API URL configuration | `books/api/urls.py` | S | Low | 4.4.4-4.4.6 |

**Parallelization**: 4.4.1-4.4.3 parallel, then 4.4.4-4.4.6 parallel

#### 4.5 Books Views

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.5.1 | Create BookHomePageView | `books/views.py` | L | Medium | 4.2.1, Phase 1 |
| 4.5.2 | Create BookDetailView | `books/views.py` | M | Low | 4.2.1 |
| 4.5.3 | Create AuthorListView | `books/views.py` | M | Low | 4.2.2 |
| 4.5.4 | Create AuthorDetailView | `books/views.py` | M | Low | 4.2.2 |
| 4.5.5 | Create ToggleReadBookView | `books/views.py` | M | Low | 4.2.8 |

**Parallelization**: All can run in parallel

#### 4.6 Books Templates

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.6.1 | Create books/home.html | `books/templates/books/home.html` | L | Medium | 4.5.1 |
| 4.6.2 | Create _book_row_desktop.html | `books/templates/books/includes/` | M | Medium | 4.6.1 |
| 4.6.3 | Create _book_row_mobile.html | `books/templates/books/includes/` | M | Medium | 4.6.1 |
| 4.6.4 | Create book_detail.html | `books/templates/books/` | M | Low | 4.5.2 |
| 4.6.5 | Create author_list.html | `books/templates/books/` | M | Low | 4.5.3 |
| 4.6.6 | Create author_detail.html | `books/templates/books/` | M | Low | 4.5.4 |
| 4.6.7 | Create _read_button.html | `books/templates/books/includes/` | S | Low | 4.5.5 |
| 4.6.8 | Create _genre_filter.html | `books/templates/books/includes/` | M | Low | 4.6.1 |

**Parallelization**: 4.6.2-4.6.8 can all run in parallel after 4.6.1

#### 4.7 Books Template Tags

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 4.7.1 | Create book_filters.py | `books/templatetags/book_filters.py` | M | Low | 4.2.1 |
| 4.7.2 | Add genre icon helpers | `books/templatetags/book_filters.py` | S | Low | 4.7.1 |
| 4.7.3 | Add page count formatter | `books/templatetags/book_filters.py` | S | Low | 4.7.1 |

**Parallelization**: Sequential (same file)

---

### Phase 5: GoodReads Integration

#### 5.1 GoodReads Service

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 5.1.1 | Research GoodReads API/scraping options | Documentation | M | Medium | None |
| 5.1.2 | Create goodreads.py API client | `books/goodreads.py` | L | Medium | 5.1.1 |
| 5.1.3 | Create GoodreadsImporter service | `books/services/goodreads_importer.py` | L | Medium | 5.1.2 |
| 5.1.4 | Add rate limiting and caching | `books/goodreads.py` | M | Low | 5.1.2 |
| 5.1.5 | Create fetch_goodreads_data command | `books/management/commands/` | M | Low | 5.1.3 |
| 5.1.6 | Add tests for GoodReads integration | `books/tests/test_goodreads.py` | L | Low | 5.1.5 |

**Parallelization**: Sequential (each depends on previous)

#### 5.2 Open Library Fallback

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 5.2.1 | Create openlibrary.py client | `books/openlibrary.py` | M | Low | None |
| 5.2.2 | Integrate as fallback in importer | `books/services/goodreads_importer.py` | M | Low | 5.2.1, 5.1.3 |

**Parallelization**: 5.2.1 parallel with Phase 5.1

---

### Phase 6: Client-Side Rendering

#### 6.1 Books JavaScript Renderer

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 6.1.1 | Create BookRenderer class | `books/static/books/js/book-list-renderer.js` | L | High | 1.3.3 |
| 6.1.2 | Create book-cache.js | `books/static/books/js/book-cache.js` | M | Medium | 6.1.1 |
| 6.1.3 | Create book-client-filter.js | `books/static/books/js/book-client-filter.js` | M | Medium | 6.1.1 |
| 6.1.4 | Create book-client-filtering.js | `books/static/books/js/book-client-filtering.js` | L | Medium | 6.1.1-6.1.3 |
| 6.1.5 | Update minify script for books | `scripts/minify_js.sh` | S | Low | 6.1.1-6.1.4 |
| 6.1.6 | Create bundle file | Build process | S | Low | 6.1.5 |

**Parallelization**: 6.1.2-6.1.3 parallel, then 6.1.4

#### 6.2 Verify Dual-Rendering Consistency

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 6.2.1 | Manual testing: server vs client render | Manual | M | High | 6.1.6, 4.6.1-4.6.3 |
| 6.2.2 | Create visual regression tests | `books/tests/` | L | Medium | 6.2.1 |
| 6.2.3 | Cross-browser testing | Manual | M | Medium | 6.1.6 |

**Parallelization**: 6.2.2-6.2.3 parallel

---

### Phase 7: Navigation & UI Integration

#### 7.1 Navigation Updates

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 7.1.1 | Add books to main navigation | `games/templates/base.html` | M | Medium | Phase 4 |
| 7.1.2 | Update sidebar for media type tabs | `games/templates/includes/_sidebar.html` | M | Medium | 7.1.1 |
| 7.1.3 | Add books route to sitemap | `games/sitemaps.py` | S | Low | Phase 4 |
| 7.1.4 | Update footer links | `games/templates/includes/_footer.html` | S | Low | 7.1.1 |

**Parallelization**: All can run in parallel (different files)

#### 7.2 Shared UI Components

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 7.2.1 | Create media type switcher component | `core/templates/core/_media_switcher.html` | M | Low | Phase 1 |
| 7.2.2 | Style media type tabs | `theme/static_src/src/styles.css` | S | Low | 7.2.1 |

**Parallelization**: Sequential

---

### Phase 8: Testing & QA

#### 8.1 Books Tests

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 8.1.1 | Create test_models.py | `books/tests/test_models.py` | M | Low | Phase 4.2 |
| 8.1.2 | Create test_views.py | `books/tests/test_views.py` | L | Low | Phase 4.5 |
| 8.1.3 | Create test_api.py | `books/tests/test_api.py` | M | Low | Phase 4.4 |
| 8.1.4 | Create test_admin.py | `books/tests/test_admin.py` | M | Low | Phase 4.3 |
| 8.1.5 | Create test_template_tags.py | `books/tests/test_template_tags.py` | M | Low | Phase 4.7 |

**Parallelization**: All can run in parallel

#### 8.2 Regression Testing

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 8.2.1 | Run full games test suite | All games tests | L | High | All phases |
| 8.2.2 | Manual smoke testing of games | Manual | M | Medium | All phases |
| 8.2.3 | Performance benchmarking | Manual | M | Low | All phases |

**Parallelization**: 8.2.1-8.2.3 parallel

---

### Phase 9: Cleanup & Refactoring

#### 9.1 Games Refactoring (Optional)

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 9.1.1 | Update Game to inherit MediaItemBase | `games/models.py` | M | Medium | All phases |
| 9.1.2 | Update Developer to inherit CreatorBase | `games/models.py` | M | Medium | 9.1.1 |
| 9.1.3 | Update GameRenderer to extend BaseRenderer | `games/static/games/js/game-list-renderer.js` | M | Medium | 9.1.1 |
| 9.1.4 | Remove backward-compat re-exports | `games/mixins.py` | S | Low | 9.1.3 |

**Parallelization**: Sequential (model changes must be careful)

#### 9.2 Documentation

| Task ID | Task | Files | Complexity | Risk | Dependencies |
|---------|------|-------|------------|------|--------------|
| 9.2.1 | Update CLAUDE.md for books | `CLAUDE.md` | M | Low | All phases |
| 9.2.2 | Document books skills | `.claude/skills/` | S | Low | Phase 5 |
| 9.2.3 | Update README | `README.md` | S | Low | All phases |

**Parallelization**: All parallel

---

## 6. Task Dependency Graph

```
Phase 1 (Core Infrastructure)
    │
    ├──────────────────────────────────────────────┐
    │                                              │
    ▼                                              ▼
Phase 2 (List Generalization)              Phase 4 (Books App)
    │                                              │
    │                                              ├──── 4.1-4.2 (Models)
    │                                              │         │
    │                                              │    ┌────┴────┬─────────┐
    │                                              │    ▼         ▼         ▼
    │                                              ├── 4.3     4.4       4.5
    │                                              │  (Admin)  (API)   (Views)
    │                                              │              │         │
    │                                              │              └────┬────┘
    │                                              │                   ▼
    │                                              └──────────► 4.6-4.7 (Templates)
    │                                                                 │
    │                                                                 ▼
    │                                                          Phase 5 (GoodReads)
    │                                                                 │
    └──────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
                    Phase 6 (Client-Side Rendering)
                           │
                           ▼
                    Phase 7 (Navigation & UI)
                           │
                           ▼
                    Phase 8 (Testing & QA)
                           │
                           ▼
                    Phase 9 (Cleanup)
```

---

## 7. Parallelization Strategy

### 7.1 Maximum Parallel Workers

Given the dependency graph, the maximum useful parallel workers at each phase:

| Phase | Max Workers | Tasks That Can Parallelize |
|-------|-------------|---------------------------|
| 1 | 4 | 1.1.3-1.1.6 (abstract models), 1.2.1-1.2.4 (utilities), 1.3.1-1.3.3 (templates) |
| 2 | 4 | 2.1.4-2.1.7 (after 2.1.1-2.1.3) |
| 3 | 1 | None - high-risk sequential work |
| 4 | 8 | 4.2 (models), 4.3 (admin), 4.4 (API), 4.5 (views), 4.6 (templates), 4.7 (tags) |
| 5 | 2 | 5.1 (GoodReads) + 5.2.1 (OpenLibrary client) |
| 6 | 3 | 6.1.2-6.1.3 (JS modules) |
| 7 | 4 | 7.1.1-7.1.4 (navigation updates) |
| 8 | 5 | 8.1.1-8.1.5 (books tests) + 8.2.1-8.2.3 (regression) |
| 9 | 3 | 9.2.1-9.2.3 (documentation) |

### 7.2 Recommended Worker Allocation

**Optimal Setup: 4 Workers**

| Worker | Primary Responsibility | Phases |
|--------|----------------------|--------|
| Worker 1 | Core infrastructure & models | 1, 4.2 (models), 9.1 |
| Worker 2 | Views & templates | 4.5, 4.6, 7.1 |
| Worker 3 | API & services | 4.4, 5, 6.1 |
| Worker 4 | Admin, tests, docs | 4.3, 8.1, 9.2 |

### 7.3 Parallel Execution Timeline

```
Week 1:
├── Worker 1: Phase 1 (Core Infrastructure)
├── Worker 2: Phase 2 (List Generalization)
├── Worker 3: Phase 5.1.1 (GoodReads Research)
└── Worker 4: (Waiting/Supporting)

Week 2:
├── Worker 1: Phase 4.2 (Books Models)
├── Worker 2: Phase 4.5 (Books Views)
├── Worker 3: Phase 4.4 (Books API)
└── Worker 4: Phase 4.3 (Books Admin)

Week 3:
├── Worker 1: Phase 4.2 (continued)
├── Worker 2: Phase 4.6 (Books Templates)
├── Worker 3: Phase 5.1 (GoodReads Service)
└── Worker 4: Phase 4.7 (Template Tags)

Week 4:
├── Worker 1: Phase 6 (Client-Side Rendering) - CRITICAL PATH
├── Worker 2: Phase 7 (Navigation & UI)
├── Worker 3: Phase 5.1 (GoodReads continued)
└── Worker 4: Phase 8.1 (Books Tests)

Week 5:
├── Worker 1: Phase 6 (continued)
├── Worker 2: Phase 8.2 (Regression Testing)
├── Worker 3: Phase 5.1 (continued)
└── Worker 4: Phase 9.2 (Documentation)

Week 6:
├── All Workers: Phase 8 (Final QA), Phase 9 (Cleanup)
```

### 7.4 Critical Path

The critical path (longest sequential chain) is:

```
Phase 1.1 → Phase 1.3.3 → Phase 6.1.1 → Phase 6.1.4 → Phase 6.2.1
(Core)      (base-renderer.js) (BookRenderer)  (Integration)  (Verification)
```

**Bottleneck**: The client-side rendering work (Phase 6) depends on both the base renderer (Phase 1.3.3) and the templates (Phase 4.6). This is the most complex and highest-risk work.

---

## 8. Risk Analysis

### 8.1 High-Risk Tasks

| Task | Risk | Mitigation |
|------|------|------------|
| 3.1 Move User to Core | Data loss, auth breakage | Skip - use settings.AUTH_USER_MODEL reference instead |
| 6.1.1 BookRenderer | Complex dual-rendering | Extensive manual testing, mirror game-list-renderer.js closely |
| 6.2.1 Dual-render verification | Visual bugs | Create visual regression test suite |

### 8.2 Medium-Risk Tasks

| Task | Risk | Mitigation |
|------|------|------------|
| 5.1 GoodReads integration | API changes, rate limits | Implement fallback to OpenLibrary |
| 4.6.1 Books homepage | Performance issues | Use same caching/compression as games |
| 2.1 List media_type | Migration issues | Use default value, no data changes |

### 8.3 Low-Risk Tasks

Most other tasks are low-risk because they:
- Create new files without touching existing code
- Follow established patterns exactly
- Have no database migration complexity

---

## 9. Testing Strategy

### 9.1 Unit Tests

| Area | Test Coverage Target | Priority |
|------|---------------------|----------|
| Books models | 90%+ | P0 |
| Books API | 90%+ | P0 |
| Books views | 80%+ | P0 |
| GoodReads service | 70%+ | P1 |
| Book template tags | 90%+ | P1 |

### 9.2 Integration Tests

| Test | Description | Priority |
|------|-------------|----------|
| Books homepage load | Verify page loads with data | P0 |
| Book detail page | Verify all sections render | P0 |
| Read book toggle | Verify HTMX interaction | P0 |
| Client-side filtering | Verify JS renders correctly | P0 |

### 9.3 Regression Tests

| Test | Description | Priority |
|------|-------------|----------|
| Games test suite | All existing tests pass | P0 |
| Games homepage | No visual changes | P0 |
| Games performance | No degradation | P1 |

### 9.4 Manual QA Checklist

- [ ] Games homepage loads correctly
- [ ] Games detail pages work
- [ ] Games filtering works (server + client)
- [ ] Games played/want-to-play toggles work
- [ ] Books homepage loads correctly
- [ ] Books detail pages work
- [ ] Books read/want-to-read toggles work
- [ ] Navigation between games/books works
- [ ] Admin for both games/books works
- [ ] API endpoints return correct data

---

## 10. Rollback Plans

### 10.1 Phase-Level Rollback

| Phase | Rollback Action | Data Impact |
|-------|-----------------|-------------|
| 1 | Remove core from INSTALLED_APPS | None |
| 2 | Migration reverse (remove media_type) | None |
| 3 | Restore User to games, revert AUTH_USER_MODEL | High - avoid |
| 4 | Remove books from INSTALLED_APPS, drop tables | None (new data only) |
| 5 | Remove GoodReads service | None |
| 6 | Remove JS files, disable client-side filtering | None |
| 7 | Revert navigation template changes | None |

### 10.2 Emergency Rollback

If critical issues arise post-deployment:

1. Revert to previous git commit
2. Remove books from INSTALLED_APPS
3. Run `python manage.py migrate books zero` to remove tables
4. Deploy

---

## Appendix A: File Inventory

### Files to Create

| File | Phase | Lines (Est.) |
|------|-------|--------------|
| `core/__init__.py` | 1 | 5 |
| `core/apps.py` | 1 | 10 |
| `core/models.py` | 1 | 150 |
| `core/mixins.py` | 1 | 60 |
| `core/templatetags/core_filters.py` | 1 | 100 |
| `core/templates/core/_pagination.html` | 1 | 30 |
| `core/templates/core/_base_media_row.html` | 1 | 80 |
| `core/static/core/js/base-renderer.js` | 1 | 300 |
| `books/__init__.py` | 4 | 5 |
| `books/apps.py` | 4 | 10 |
| `books/models.py` | 4 | 400 |
| `books/admin.py` | 4 | 200 |
| `books/views.py` | 4 | 500 |
| `books/urls.py` | 4 | 30 |
| `books/api/serializers.py` | 4 | 200 |
| `books/api/views.py` | 4 | 300 |
| `books/api/urls.py` | 4 | 30 |
| `books/services/goodreads_importer.py` | 5 | 400 |
| `books/goodreads.py` | 5 | 300 |
| `books/openlibrary.py` | 5 | 150 |
| `books/templatetags/book_filters.py` | 4 | 150 |
| `books/templates/books/home.html` | 4 | 200 |
| `books/templates/books/book_detail.html` | 4 | 150 |
| `books/templates/books/author_list.html` | 4 | 100 |
| `books/templates/books/author_detail.html` | 4 | 100 |
| `books/templates/books/includes/*.html` | 4 | 300 |
| `books/static/books/js/book-list-renderer.js` | 6 | 400 |
| `books/static/books/js/book-cache.js` | 6 | 150 |
| `books/static/books/js/book-client-filter.js` | 6 | 200 |
| `books/static/books/js/book-client-filtering.js` | 6 | 300 |
| `books/tests/test_models.py` | 8 | 300 |
| `books/tests/test_views.py` | 8 | 500 |
| `books/tests/test_api.py` | 8 | 300 |
| `books/tests/test_admin.py` | 8 | 200 |
| `books/management/commands/fetch_goodreads_data.py` | 5 | 200 |
| **Total New** | | **~6,400** |

### Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `acclaimedgames/settings.py` | 1, 4 | Add apps to INSTALLED_APPS |
| `acclaimedgames/urls.py` | 4 | Add books routes |
| `games/models.py` | 2 | Add media_type to List |
| `games/mixins.py` | 1 | Re-export from core |
| `games/admin.py` | 2 | Show media_type in List admin |
| `games/api/serializers.py` | 2 | Add media_type to ListSerializer |
| `games/views.py` | 2 | Filter lists by media_type |
| `games/templates/base.html` | 7 | Add books navigation |
| `games/templates/includes/_sidebar.html` | 7 | Add media tabs |
| `games/sitemaps.py` | 7 | Add books sitemap |
| `scripts/minify_js.sh` | 6 | Add books JS files |
| `CLAUDE.md` | 9 | Document books |

---

## Appendix B: Database Changes

### New Tables (books app)

| Table | Columns | Relationships |
|-------|---------|---------------|
| `books_book` | id, name, slug, rank, year, description, goodreads_id, isbn, page_count, ... | M2M: authors, genres, publishers |
| `books_author` | id, name, slug, goodreads_id, parent_id | Self-FK |
| `books_bookgenre` | id, name, slug, parent_id, level | Self-FK |
| `books_bookseries` | id, name, slug, goodreads_id | |
| `books_bookpublisher` | id, name, slug | |
| `books_booklist` | id, name, url, year, type, publisher_id | FK: Publication |
| `books_booklistmembership` | id, rank, list_id, book_id | FK: BookList, Book |
| `books_readbook` | id, user_id, book_id, goodreads_id, created | FK: User, Book |
| `books_wanttoreadbook` | id, user_id, book_id, goodreads_id, created | FK: User, Book |
| `books_goodreadsbookdata` | id, book_id, goodreads_id, cover_url, rating, ... | FK: Book |
| `books_wikipediabookdata` | id, book_id, page_title, genres, ... | FK: Book |

### Modified Tables

| Table | Change |
|-------|--------|
| `games_list` | Add `media_type` column (VARCHAR(20), default='game') |

---

## Appendix C: Skill Definitions

After implementation, add these skills:

```yaml
# .claude/skills/books.md
/books - Import book data and manage rankings

# .claude/skills/goodreads.md
/goodreads - Fetch GoodReads metadata for books
```

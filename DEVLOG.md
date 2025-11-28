# Developer Log

## 2025-11-28

- Replaced pagination with "Load More" button on advanced search (ghost-style, 1000 item limit)
- Added year preview: game release years highlight blue during year grid drag selection
- Removed filter toggle - filters always visible on advanced search
- Moved CSV download button into filters header with console-style button
- Fixed first game row alignment with filters panel (reset Bulma negative margin)

## 2025-11-26

- MDI CSS subset: reduced 53KB CDN file to ~1KB by including only 10 used icons (98% reduction)
- Deferred Google Analytics loading with requestIdleCallback to eliminate 39ms forced reflow on mobile
- Self-hosted CSS: combined Bulma + Bulmaswatch + custom styles into single file (~600ms render-blocking reduction)
- Fixed mobile CLS (0.31→target <0.1): logo aspect-ratio, icon sizing, x-cloak on hidden elements
- PageSpeed optimizations: deferred HTMX/Alpine.js scripts, async MDI CSS loading, preconnect hints
- Self-hosted MDI font with font-display: swap to eliminate FOIT (~40ms FCP improvement)
- Image optimization: lazy loading, explicit dimensions, fetchpriority for hero image
- Accessibility: skip navigation link, screen-reader labels for search, ARIA labels on buttons
- SEO: meta descriptions, canonical URLs, Open Graph/Twitter Cards, JSON-LD structured data
- Added XML sitemap with games, developers, and static pages (/sitemap.xml)
- Added robots.txt with sitemap reference (/robots.txt)
- Security headers: HSTS, X-Frame-Options, Secure cookies (production only)
- WhiteNoise optimization: Brotli/gzip compression, 1-year cache headers with hash-based cache busting
- Accessibility contrast fixes: improved text contrast for WCAG AA compliance
- Responsive hero logo with srcset for optimized image delivery
- IGDB cover images: added 2x retina support with srcset for crisp thumbnails on high-DPI displays

## 2025-11-25

- Added `sync_from_prod` management command for syncing production PostgreSQL to local SQLite
- Added Enter key navigation to nav search bar (goes to full search results page)
- Added optional author field to Posts (ForeignKey to User, displays as "Author · 2 hours ago")
- Added contact form with Navi theme, Brevo SMTP email integration (console in dev, SMTP in prod)
- Redesigned thank you page with Portal theme (animated envelope flying into glowing portal)
- Backend refactoring: split utils.py (~1150 lines) into focused service modules (import_handler, ranking_service, query_filters, game_filter_service)
- CSS: added custom properties for theming, extracted dual-range slider styles from template
- UI fixes: download CSV button shows text label, disabled browser autocomplete on search input
- JavaScript refactoring: created utils.js with shared utilities, consolidated duplicate fetch functions (~430 lines removed)
- CSS refactoring: extracted ~1000 lines from base.html to external stylesheets (main.css, import.css)

## 2025-11-24

- Major performance optimizations: 50-70% query reduction (N+1 elimination, caching, prefetch)
- Added 24-hour caching for genre/platform lists and year statistics
- Added database indexes on Game.name, Developer.name, Genre.name, Post fields
- Refactored IGDB importer to eliminate 170 lines of duplicated code
- Fixed beta advanced search scroll behavior (force reload on back-forward cache)
- Fixed beta mobile game list highlight (scroll and auto-dismiss)
- Added Google Analytics HTMX tracking for page view monitoring

## 2025-11-23

- **Completed beta migration to 100%** - All 11 routes and 28 components with legacy URL redirects and custom 404
- Fixed beta advanced search (navbar duplication, filter persistence, URL params, input focus, counts, pagination, mobile layout)
- Fixed beta developer pages (search triggering, dynamic game counts) and converted Source Lists to HTMX
- Fixed beta styling to match Vue (navbar/search colors, dropdowns, links, badges, pagination hover, fonts, no white flash)
- Fixed memory leaks (7 in Vue components) and optimized server memory (50-90% reduction)
- Fixed IGDB import progress bar, decade rank calculation, and enhanced data management tools
- Removed vite-ssg/SSR, reverted to client-side Vue SPA, added prefetching for better performance

## 2025-11-22

- Implemented dynamic tagline with real-time database counts
- Added game counts to decade filters
- Optimized IGDB import for maximum performance (100+ games/sec, 75x improvement with Pro tier)
- Fixed developer list search double-load and implemented real-time search
- Enhanced import page with file validation fixes, completion indicators, and auto-IGDB trigger
- Achieved 95% overall test coverage with comprehensive test suite expansion
- Upgraded to Heroku-24 stack
- Migrated repository from BitBucket to GitHub

## 2025-11-19

- Fixed memory leak in Vue route watchers causing accumulation during pagination
- Major beta app migration (game/developer lists, search, detail pages with HTMX)

## 2025-11-18

- Fixed pagination back button navigation to return to correct page

## 2025-11-17

- Implemented vite-ssg for server-side static generation and Wayback Machine compatibility
- Fixed Wayback Machine archival by serving pre-rendered HTML
- Implemented client-side pagination with Vuex caching for instant navigation

## 2025-11-16

- Achieved 100% test coverage with 95% threshold enforcement via pre-commit hooks
- Added database indexes and query optimizations for API performance
- Set up comprehensive test suite (Django + Vue.js with Vitest)
- Applied Black formatter to entire codebase

---

## Historical Log (Sean's Notes)

### 2025

- **2025-03-01** - 1 hour
- **2025-01-25** - 1 hour
- **2025-01-19** - 2 hours
- **2025-01-12** - 2 hours
- **2025-01-02** - 2 hours

### 2024

- **2024-12-08** - 2 hours
- **2024-11-10** - 2 hours
- **2024-07-28** - 2 hours
- **2024-07-14** - 3 hours
- **2024-06-30** - 1 hour - Misc changes
- **2024-06-23** - 2 hours - Misc changes
- **2024-05-26** - 3 hours - Misc changes
- **2024-05-19** - 2 hours - Deploy SPA and import latest data
- **2024-05-05** - 1 hour - Feedback on screenshots
- **2024-05-04** - 1 hour - Feedback on screenshots
- **2024-04-14** - 2 hours - SPA refactor
- **2024-04-13** - 1 hour - SPA refactor
- **2024-04-07** - 4 hours - SPA refactor
- **2024-04-06** - 4 hours - SPA refactor
- **2024-04-01** - 1 hour - New search page and slug fields
- **2024-03-31** - 1 hour - New search page
- **2024-03-24** - 2 hours - New search page
- **2024-03-23** - 1 hour - Updates to new list pages
- **2024-03-17** - 1 hour - Updates to posts and themes
- **2024-03-16** - 3 hours - Add themes to games, add posts list page

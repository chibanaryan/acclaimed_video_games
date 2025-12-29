# Developer Log

## 2025-12-28

- Fixed icon issues: updated filter icons (Action, Simulation, Retro, Strategy), sidebar icons, replaced MDI subset with full font
- Platform filters: added canonical year ranges (e.g., "NES 1983-1995"), fixed count double-counting, improved sorting
- Filter appearance: removed checkboxes, unavailable options now dimmed instead of hidden (years, platforms, genres)
- Client-side filtering: loading skeleton for counts, client-side sorting, pure client-side filtering (removed server fallback)
- Developer search: unified games + developers in nav search bar with "See all results" links
- Added "Report incorrect data" link to game detail pages (opens contact modal with pre-filled info)
- Genre system: added mappings (Bullet hell→Shooter, Roguelite→Roguelike), fixed orphan genre hierarchy bug
- Bug fixes: mobile rankings flash, studio filter checkbox clipping, mobile search "No results" bug, year heatmap clearing
- Tablet layout: narrowed sidebar, compact controls, fixed game row breakpoint (was 768px, now 1024px like navbar)
- Jump-to-game: now works for all sort modes (position-based), fixed mobile scroll offset for fixed header
- Desktop breakpoint: changed to 1088px (when game list equals filter sidebar width), narrower nav sidebar (192px)
- Mobile nav: added Devs/Lists/News links (responsive), larger buttons, active page indicator
- Fix blurry sidebar logo by using high-resolution images (548w/1092w) instead of small variants

## 2025-12-27

- Changed badge filter behavior: scroll to top instead of highlighting clicked game (cleaner UX)
- Fixed genre normalization bug: management commands now normalize Wikipedia genres consistently
- Added --cleanup-orphans flag to fetch_wikipedia_metadata to remove orphan WikipediaGenre records
- Simplified genre filtering from multi-select to single-select for better UX
- Removed "Match All" / "Match Any" toggle (no longer needed with single-select)
- Added clear (×) buttons next to selected genres for easy deselection
- Updated desktop and mobile genre filter components with new single-select behavior
- Added client-side filtering with IndexedDB caching for Rankings page (instant filter updates)
- Replaced Select All/Clear All buttons with company checkbox at top of developer studio filter tree

## 2025-12-16

- Fixed CSV download to use Wikipedia genres instead of IGDB genres (now matches genre display on site)

## 2025-12-15

- Added sorting options (Rank, Release Year, Alphabetical) to Rankings page
- Server-side implementation with URL parameter state management for persistence
- Responsive layout with separate mobile/tablet/desktop dropdown positions
- Added comprehensive test coverage for all sorting modes and filter combinations
- Implemented Wikipedia genre hierarchy with multi-level filtering (replaces IGDB genres)
- Added genre normalization service to consolidate variant names (e.g., "MMORPG" variants → "MMORPG")
- Redesigned game row hover: square thumbnails, Global Rank on title row, smoother transitions
- Filter dropdown now excludes genres with 0 games while preserving parent categories
- Fixed Global Rank display on developer detail pages (now shows on filtered game lists)
- Made platform and genre badges clickable to filter games (resets other filters for simplicity)
- Added game highlighting when filtering via badges (scrolls to game, fades after 4 seconds)
- Badge clicks now trigger HTMX filter updates with smooth transitions

## 2025-12-14

- Fixed critical bug where metadata refresh cleared game slugs (997 games affected)
- Updated slug generation logic to preserve existing slugs when IGDB returns None/empty
- Added regression tests to prevent future slug clearing during IGDB updates
- Updated favicon to black outline version (32x32 square) to prevent squishing in browser tabs
- Fixed social media link preview to use white background (better contrast on dark-themed platforms)
- Fixed studio filter data structure to map only direct games (not descendants) for proper hierarchical filtering

## 2025-12-10

- Added fetch_wikipedia_metadata management command (combines page lookup + genre scraping in one command)
- Command replicates "Fetch Wikipedia Pages" button functionality for production CLI use
- Changed IGDB and Wikipedia metadata to persist when games are deleted (SET_NULL instead of CASCADE)
- Metadata automatically reconnects when games are re-imported (avoids re-fetching from APIs)
- Optimized Wikipedia genre fetching to eliminate duplicate page searches (60-67% faster throughput)
- Fixed Wikipedia genre capitalization to preserve original casing (e.g., "RPG" stays "RPG", not "Rpg")
- Refactored import page to use site-wide theme and navigation (extends base.html for consistency)
- Temporarily disabled CSP middleware due to nonce mismatch in production (header nonce ≠ HTML nonce)

## 2025-12-09

- Completed Developer/DeveloperAlias to Company/Studio refactor (clearer naming for parent companies vs game studios)
- Fixed game count double-counting across sibling studios (now counts unique games only)
- Removed auto-creation of 0-game parent Studios during IGDB import (prevents database bloat)
- Fixed studio expansion animation to wait for DOM settling (prevents layout jank)
- Fixed deep hierarchy navigation to find and highlight games at any nesting level
- Updated Import page to show separate counts for Companies and Studios
- Added alphabetical sorting for studios at all hierarchy levels in company detail view
- Fixed recursive parent fetching in IGDB integration to capture entire company hierarchy

## 2025-12-05

- Removed game description section from game detail pages (simplified UI)
- Fixed genre subtitle to show "AND" when "Match All" is selected instead of always showing "OR"

## 2025-12-04

- Removed Game of the Day feature (model fields, service, templates, views, tests)
- Home page now shows 5 latest posts instead of 3
- "All posts" button on home page now links to page 2 (skipping first 5 posts)
- Mobile home page now shows only top 10 games (desktop still shows 30)
- Removed Subscribe page links from sidebar and mobile navigation
- Implemented Wikipedia page lookup feature with Wikidata ID integration
- Added "Fetch Wikipedia Pages" button to /import/ page with real-time SSE progress tracking
- Primary lookup via Wikidata API (10x faster with authentication), fallback to OpenSearch API
- Authentication support via WIKIDATA_ACCESS_TOKEN environment variable (0.75s vs 2.0s delay)
- New database fields: wikipedia_page_title, wikipedia_lookup_source (wikidata/opensearch)
- Created get_wikipedia_pages management command with CSV output and --save option
- Wikipedia page lookup separate from genre scraping (enables future optimization)
- Added wikipedia_page_title and wikipedia_lookup_source to Game admin display/search
- Fixed Wikipedia page lookup bug (changed "year" to "year_of_release" field reference)
- Added time estimates next to IGDB and Wikipedia import buttons with format_duration filter
- Simplified import progress UI: replaced detailed progress bars with loading spinners
- Simplified backend progress reporting: removed unused percentage/time calculations
- Fixed redundant text in database status cards ("data data" and "pages pages")
- Fixed Wikipedia API response handling: added type checking for None/list responses preventing AttributeError crashes
- Implemented newsletter subscription feature with double opt-in email confirmation
- Email notifications automatically sent to confirmed subscribers when posts are published (active=True)
- One-time notification per post using notification_sent field to prevent duplicate emails
- Subscribe form added to home page (next to Latest News) and sidebar navigation
- Multipart emails (HTML + plain text) with full post content and working markdown links
- Token-based unsubscribe links for easy opt-out
- Admin interface for managing subscribers (view-only, no manual additions)
- CSP exemption added for Django admin to fix script loading issues
- Fixed 404 page formatting: increased card width to max-w-2xl, removed width/height attrs from button icon, sized button appropriately
- Added post author name to notification emails (displays full name or username)
- Fixed theme persistence issue: removed hardcoded data-theme attribute, added validation to prevent invalid theme values
- Theme now auto-detects system preference when localStorage contains invalid values (like 'auto')
- Restricted DaisyUI configuration to only load lofi and forest themes (prevents "auto" theme from being available)
- Removed stale 'night' theme references from theme toggle logic (fixes theme switching issues)
- Changed Open Graph image from light logo to dark logo (affects social media previews)
- Removed old theme references (night, nord, synthwave) from CSS and template toggles to prevent theme confusion

## 2025-12-03

- Added press quotes to home page hero section from GameStar, 4Players, and 3dJuegos
- Quotes positioned adjacent to logo with centered tagline below for cohesive layout
- Made Game of the Day card more compact: narrower (max 448px), centered, smaller cover (160px vs 192px), tighter spacing
- Added DaisyUI 3D hover effect to Game of the Day cover with mouse-tracking tilt animation
- Improved press quote formatting: publication names now inline with quotes, increased spacing between quotes
- Added "Support This Project" donate button to home page linking to /page/donate/
- Fixed ranking chip overlay on Game of the Day cover by moving it to header area as secondary badge

## 2025-12-02 - 2025-12-03

- Performance optimizations: optimized mobile images (square thumbnails save ~214 KiB), converted logo images to WebP format (36-44% smaller), split/minified JavaScript (60% less main thread blocking), inlined MDI CSS (510ms faster), deferred Google Analytics, enabled GZip compression, optimized WhiteNoise caching
- Mobile LCP improvements: preload critical images, streamlined theme script, responsive image loading with width descriptors (saves 105-195 KB per page), server-side render mobile title to eliminate 1,120ms Alpine.js render delay
- Implemented Game of the Day feature with weighted random selection (top 300 games = ~50% probability), daily caching, and optional quote display
- Fixed CLS on home page by reserving image space (aspect-ratio, eager loading, fetchpriority) for Game of the Day card
- Implemented responsive game row layout with platform/genre icon columns that adapt to screen width (1200px+, 1100px+ breakpoints)
- Redesigned game detail page with 50/50 split layout, centered game cover with 3D hover effect, improved table alignment
- Added Jump to Rank feature with bug fixes (max value, overshoot, scroll position) and floating Back to Top button
- Eliminated layout shifts: fixed HTMX navigation jumps, filter dropdowns, sidebar search thumbnails, and filter section borders/padding

## 2025-12-01

- Migrated navigation from top navbar to persistent left sidebar on desktop (≥1024px)
- Sidebar includes: logo, search, navigation links, Contact Us modal trigger, theme switcher, social links
- Mobile navigation remains as hamburger menu with same functionality
- Implemented global Contact Us modal accessible from any page using DaisyUI checkbox method
- Modal plays Navi sound effect ("Hey! Listen!") when opened
- Search dropdown in sidebar extends beyond sidebar width for long game titles
- Theme-aware logos: dark version on light themes, light version on dark themes
- Mobile filter improvements: instant filter updates (no "Apply" button), genres sorted by popularity, dropdown search panel, year range dropdowns

## 2025-11-29

- Migrated CSS framework from Bulma/Bulmaswatch to Tailwind CSS v4 + DaisyUI v5
- Added django-tailwind integration for development workflow with hot-reload
- Implemented theme switcher with 5 themes: Forest (default), Night, Sunset, Nord, Lo-Fi
- Theme persists across sessions via localStorage
- Converted all templates to use Tailwind utilities and DaisyUI components
- Removed Bulma CSS files (combined.css, main.css, vendor/)
- Updated documentation (CLAUDE.md, README.md) for new CSS workflow

## 2025-11-28

- Replaced pagination with "Load More" button on advanced search (ghost-style, 1000 item limit)
- Added year preview: game release years highlight blue during year grid drag selection
- Removed filter toggle - filters always visible on advanced search
- Moved CSV download button into filters header with console-style button
- Fixed first game row alignment with filters panel (reset Bulma negative margin)
- Dynamic year heatmap: reflects filtered game counts, years "wink out" when no matches

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

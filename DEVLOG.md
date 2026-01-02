# Developer Log

## 2026-01-02

- Refactor game detail source lists: sort by publication importance, group by type with expand/collapse
- Refactor Lists page: group lists by publication with expand/collapse, sort years descending
- Add rank distribution chart: smooth SVG area chart showing game distribution across rankings (1-1000), updates dynamically with filters
- Fix rank distribution chart: position data points at edges to eliminate flat sections at start/end
- Add peak count indicator to rank distribution chart for scale context on filtered views
- Add colored badges for list types: BGYR rainbow order (info/success/warning/error) with custom theme colors

## 2026-01-01

- Show multiple developers in game rows with smart filtering (removes redundant parent companies when subsidiary is also credited)
- Performance: reduce main-thread work by self-hosting HTMX/Alpine.js, bundling client-filtering scripts, deferring modal handlers
- Fix sync_from_prod: add missing models (Series, WikipediaGenre, GameQuote, IGDBGameData, WikipediaGameData)
- Fix signal handler crash during bulk deletion when parent developer already deleted
- Bump cache version to v3
- Improve game list density: show developer and list count by default (not just on hover)
- Add list appearances row to game detail properties
- Add list counts to section headers on game detail page (e.g., "All-Time Lists (15)")
- Fix badge truncation: use overflow-hidden + nested span.truncate pattern
- Mobile game row: split metadata into two rows (developer/list count, platforms/genres)
- Sync client-side game rendering with updated server templates
- Performance: fix platform filter duplicate results, add missing .distinct()
- Performance: cache genre hierarchy expansion (24h TTL) with signal-based invalidation
- Performance: cache game detail counts (total, decade, year) to reduce per-page queries
- Performance: add HTTP caching to API views (15-30 min TTL)
- Performance: optimize 404 page image (PNG to WebP, 392KB → 23KB)
- Fix developer search debounce: increase from 150ms to 300ms to reduce server load
- Fix CSV export N+1: add wikipedia_genres prefetch
- Optimize home page: cache hero stats, fix highlight pagination N+1, simplify series cache key, cache played games per-user
- Optimize developers page: add hierarchy caching service to eliminate recursive N+1 queries
- Theme refinements: fix background color (base-200 instead of base-300), use accent color for rankings and sidebar active state
- Fix developer detail layout shift: server-render game count and rank distribution to reserve space
- Add visual divider between hero section and filters on home page
- Fix sign up modal on mobile: add scrolling and compress vertical spacing for small screens
- Fix platform filter sorting: individual platforms now sort by (start year, end year, alphabetical) instead of game count
- Fix mobile developers page overflow: truncate long developer names and game titles in cards
- Add expand/collapse all button for platform and genre filter dropdowns

## 2025-12-31

- Fix layout shift on game list: use CSS Grid with calc() to reserve sidebar space on initial render
- Fix filter skeleton loading states: match actual rendered heights to prevent layout shift on load
- Add player rank/percentile to profile: shows "#X of Y players" for small groups, percentile for 10+
- Fix hierarchical filter drill-down: clicking child when parent selected shifts selection down, not toggle
- Make rankings page the homepage (redirect /rankings/ and /games/ to /)
- Add dedicated contact page at /contact/ with form fallback for modal errors
- Add news page at /news/ for blog post listing
- Filter title now shows all selected genres (not just first one)
- Various home page layout refinements: tighter spacing, reordered sections
- Add rank position indicator bar on game detail page using DaisyUI progress component
- Change homepage game tooltips to show above covers (avoid rank chip collision)
- Fix Load More showing filtered rank on unfiltered list after Jump to Rank
- Fix profile played count to exclude orphaned games (games no longer in rankings)
- Fix badge opacity on Load More: client-side rendered badges now match server opacity (70%)
- Add opt-in notification for posts: new send_notification checkbox, publish without notifying subscribers
- Developers page redesign: add Top Rank, Top Game (with thumbnail), and Subsidiaries columns
- Add sort options for subsidiaries count and top game rank on developers list
- Wider developers layout (max-w-5xl), pagination reduced to 100 per page
- Fix series badge truncation on mobile: prevent text wrap/overflow with ellipsis and max-width
- Fix Load More button: use CSF's loadMore when ready, initialize renderer state from server-rendered content
- Fix Jump to Rank: centralize state management, get authoritative loaded count from CSF/DOM
- Fix rank display: show 'alltime' rank (no global rank indicator) when no filters active
- Fix logout button reliability: restructure to match DaisyUI menu pattern, separate hidden form
- Sidebar vertical squish: scrollable bottom section for short viewports, tightened margins throughout
- Consolidate Terms/Privacy into single Legal link (sidebar, mobile nav, login modal)
- Add series display to game properties: clickable badges link to filtered game list with highlight
- Fix played button on game detail page: preserve large size when toggling played status
- Add played games filter: three-way toggle (All/Played/Unplayed) in rankings page search section
- Played filter updates faceted counts (genres, platforms, year heatmap) dynamically
- Played filter: URL parameter support (?played=yes/no), page title suffix, client-side filtering
- Reorder navigation: Home → Search → Login → Developers → Lists (consistent across sidebar and mobile)
- Mobile nav priority system: more items show outside hamburger when space permits (About, Contact, Donate)
- Move login/account to primary nav area, add logout button to Account modal
- Remove News and Legal from navigation (link Legal from About page instead)
- Unify game row templates: split into desktop/mobile partials with data-slot attributes for JS template cloning
- Played button: hide star for unauthenticated users (no empty space), show only when logged in
- CSV download: support series/played filters, show Played column (Yes/No) for authenticated users
- Fix mobile filter race condition: re-dispatch facet counts when filter sheet opens for first time
- Add legal disclaimer link to profile form
- Add Microcomputers sub-grouping: Commodore, UK, Japan, Atari, Other (sorted by game count)
- Sort all platform filter levels by game count: manufacturers, form factors, and individual platforms
- Add Microcomputer form factor titles: "UK Microcomputer Games", "Japanese Microcomputer Games", etc.
- Mobile filters: match desktop multi-select behavior with drill-down and exclusive parent selection

## 2025-12-30

- Add PlayedGame model for tracking user's played games with IGDB ID-based reconnection across re-imports
- Add toggle-played-game API endpoint with HTMX partial response
- Jump to Rank: use client-side filtering for instant navigation (no network requests)
- Jump to Rank: validate against filtered total, show error if rank exceeds list size
- Jump to Rank: use event delegation for reliable button handling, auto-initialize on script load
- Added django-allauth for user authentication (email/username login, social auth providers ready)
- Add UserProfile model with auto-creation signal for display name and email subscription preferences
- Add auth modal structure with HTMX-powered multi-step flow (feature-flagged, disabled in production)
- Auth modal Phase 4: working email login form with allauth LoginForm, HTMX submission, error display
- Auth modal: login redirects to previous page, logout via POST with immediate redirect
- Sidebar auth section: shows Sign In button (logged out) or user email + logout (logged in), behind feature flag
- Added MDI icons: arrow-left, login, logout, account-circle
- Auth modal Phase 5: user dropdown in sidebar/mobile, Edit Profile form with display name and email subscription
- Subscriber sync: profile checkbox syncs with Subscriber model, new users inherit existing subscription state
- Auth modal Phase 6: signup form with email/password, HTMX navigation between login/signup forms
- Custom allauth adapter sets username=email for guaranteed uniqueness and cleaner admin display
- Auth modal Phase 7: forgot password flow with HTMX, shows success message in modal, reset link via email
- Auth modal Phase 8: profile form shows read-only email field for user reference
- Auth modal Phase 9: custom adapters for modal-friendly redirects, comprehensive adapter tests
- Fix sign out button: add @click.stop to prevent menu from closing before form submits
- Custom User model: consolidate auth.User, Subscriber, and UserProfile into single games.User model
- Mandatory email verification: signup requires email confirmation before login, with resend option
- Login accepts email or username, signup has optional username field and newsletter checkbox
- Remove Posts feature and old newsletter subscription pages (consolidated into auth flow)
- Test speed optimization: parallel execution (36s→12s), in-memory SQLite, setUpTestData for fixtures
- Fix client-side renderer to match Django template exactly (desktop:grid, game-rank/game-title classes, hover effects)
- Played button: fix star glow clipping, add DaisyUI tooltip, fix HTMX swap on client-rendered rows
- Played button UI: Mario star PNG when played, MDI outline when not, in game rows and detail page
- Played button: HTMX toggle, desktop/mobile sync, no layout shift with fixed-size wrappers
- Client-side renderer: add played button rendering with playedGameIds state sync
- Fix played buttons on Load More: add htmx.process() to reinitialize HTMX for dynamically rendered content

## 2025-12-29

- Year grid heatmap: orange color scheme with theme-specific variants, smart corner rounding based on adjacency
- Game row hover: title shrinks on hover to make room for properties, properties indented under title
- Game row hover: rank scales up, thumbnail shows full cover art and expands, gradient background fades right, removed borders
- Platform filters: add 4 missing platforms (ARCH, E60, HP21, PDP) to Microcomputers, remove phantom NGP/WS from Retro
- Platform year ranges: move from hardcoded JS to database fields (year_start, year_end) for admin management
- Search bar clear buttons: standardize all inputs using DaisyUI label pattern, show X immediately on typing
- Mobile filter clear buttons: add text labels ("Clear Years", "Clear Platforms", etc.) to match desktop UX
- Fix mobile filter Range tab: add year_range (1970-present) to context, fix From/To dropdowns not populating
- Mobile filters: dim zero-count items (opacity-40), simplify decade selection to exact match only
- Fix mobile filter loading state: dispatch facet counts even when game-list-container not found
- Mobile filter sheet: hide nav when open, full-screen layout, fix overflow issues
- Filter sections: default collapsed, remember expansion state in localStorage
- Compact filter headers: short year format ('79-'81), badge shows count only, X button for clear
- Fix mobile nav active state: only highlight list pages (not detail pages) to match desktop sidebar behavior
- Fix mobile sort dropdowns: replace DaisyUI dropdown with native select for touch compatibility (Games, Developers, Developer detail)
- Source Lists: fix table column reflow on Load More, use percentage-based widths with table-fixed, add ellipsis truncation for long names
- Responsive layout: reduce filter width by 15% (420px→357px), lower breakpoint (1088px→962px) for narrower desktop support
- Mobile nav: add active state highlighting, cache overflow state in sessionStorage to prevent layout shift
- Mobile game row: plain text metadata (no badges), platforms • genre format, improved truncation
- Controls row: reorder to Sort | Count | Jump on both mobile and desktop, more compact mobile inputs
- Contact modal: fix scrollability on small screens with max-height constraint
- Source lists filters: blur select on change to dismiss mobile dropdown
- 404 page: handle mobile autoplay blocking gracefully (navigate immediately if audio can't play)
- Dynamic developer detail page title: updates based on checkbox selection (e.g., "Nintendo EAD (Nintendo)" or "Nintendo (3 developers selected)")
- Fix developer links in search bar: now matches Developers list page format (#developer-X for subsidiaries, no hash for root)
- Add "Submit a list" link to Source Lists page (opens contact modal with List Submission category)
- Desktop rankings: always show global rank (#N format) when filtered, matching mobile behavior
- Fix N+1 query issue in developers page: use prefetch cache instead of values_list (reduces queries from ~16 to ~3)
- Fix IGDB import bug: developer parent chains now correctly set (e.g., Nintendo EAD → Nintendo)
- Clear slugs from non-root developers: only root developers need slugs (children accessed via hash anchors)
- Fix developers missing in client-side filtered results (stale IndexedDB cache after schema change)

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
- Developers list: added sort options (# Games default, Name A-Z), recursive game counting, secondary alpha sort for ties
- Series filter: bidirectional count responsiveness, integration in dynamic title, mushroom icon
- Genre category counts now include root-level games (e.g., games tagged "Role-Playing" directly)
- Add pre-commit hook for automatic JS minification (prevents stale .min.js files)
- Add Series to unified search: navbar/sidebar search now shows series with game counts, links to filtered rankings

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

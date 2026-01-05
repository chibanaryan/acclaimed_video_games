# Developer Log

## 2026-01-04

- Fix sitemap.xml 500 error: exclude subsidiary developers without slugs from DeveloperSitemap
- Add grid view toggle: responsive cover art grid with dual ranking (filtered + global), hover overlays
- Add IGDB links to developer detail pages (dynamic link updates based on filter selection)
- Add ProtonDB Steam Deck compatibility integration (data stored, display coming later)
- Optimize main thread: defer scripts, lazy filter indexes, requestIdleCallback for initialization
- Lazy-load Alpine.js via requestIdleCallback to reduce main-thread blocking (~92KB shifted to idle)
- Bridge gaps between selected tiles in year grid heatmap (box-shadow connections)
- Fix HLTB import: skip deprecated Wikidata IDs, support multiple Wikidata entries per game
- Restore HLTB name search as default fallback (opt-out with --no-name-search)

## 2026-01-03

- Add Wikidata metadata during Wikipedia import: game modes (P404), country of origin (P495), Wikiquote links
- Add WikipediaCountry and WikipediaGameMode models with M2M relationships for efficient filtering
- Add "Want to Play" game status: three-way filter becomes four-way (All/Unplayed/Want/Played)
- Fix mobile filter sheet: Game Status section now matches desktop styling (icon, buttons, centering)
- Fix "Last 5/10 years" presets: now show previous complete years (2021-2025) instead of including current year
- Add Blog feature: Article model with markdown content, draft/published status, auto-publish date
- Blog admin: live markdown preview (iframe-isolated), Cloudinary upload widget for images
- Blog views: /blog/ list page with pagination, /blog/<slug>/ detail page (staff can preview drafts)
- Add Blog link to sidebar and mobile navigation
- Saved Filters: logged-in users can save up to 10 filter sets with API, dropdown UI, and mobile support
- Mobile saved filters: collapsible section with large touch targets, rename/delete actions
- Add YouTube video embeds to game detail page (fetched from IGDB, privacy-enhanced mode)
- Update CSP to allow YouTube iframe embedding with proper referrer policy
- Add HLTB integration: playtime data fetched from HowLongToBeat API, displayed on game detail pages
- Integrate HLTB into weekly metadata refresh with Wikidata P2816 property lookups
- Fix HLTB filtering: server/client now use exact decimal values (API sends floats, filtering uses precise comparisons)
- Fix Load More/Jump to Rank with HLTB filters (parse hltb_mode, hltb_min, hltb_max from URL)
- Fix rank distribution chart flash on page load (hide with inline CSS until Alpine.js initializes)
- Fix rank distribution showing when only sort option changed (sorting doesn't count as active filter)
- Show "want to play" backlog count in profile modal (with star-plus icon)
- Rename "Unplayed" to "Untracked" in filter buttons and tooltips (clearer terminology)

## 2026-01-02

- Mobile: inline rank next to title (saves ~40px horizontal space, larger accent-colored rank number)
- Fix list count doubling on server render (add distinct=True to annotation with prefetch_related)
- Fix client-side developer filtering to match server-side logic (filter out ancestor companies)
- Refactor developer filter tree to use DaisyUI menu component with nested structure (cleaner hierarchy display)
- Add rank distribution chart to developer detail and home page (SVG area chart with peak indicator, updates with filters)
- Simplify game detail page: move played star to title, sort lists by year desc, remove accordions and progress bar
- Add colored badges for list types using BGYR rainbow order with custom theme colors
- Fix slow highlight navigation with client-side filtering (10x faster jump to deep ranks)
- Make platform/genre links on developer page redirect to filtered home rankings
- Show all leaf-level developers in game rows (removed 2-developer limit)
- Change default theme from light (lofi) to dark (forest)
- Increase test coverage from 93.6% to 95% with 61 new tests
- Fix DaisyUI theme base colors (base-100/200/300 hierarchy was inverted)
- Improve filter UI contrast: visible hover effects, consistent input backgrounds, subtle borders

## 2026-01-01

- Show multiple developers in game rows with smart filtering (removes redundant parent companies)
- Performance: extensive caching (genre hierarchy, game counts, hero stats, API views) and query optimizations
- Performance: reduce main-thread work by self-hosting HTMX/Alpine.js, bundling scripts, deferring modal handlers
- Improve game list density: show developer and list count by default, add list appearances to game detail
- Mobile improvements: split game row metadata into two rows, fix signup modal scrolling, truncate overflow
- Fix developer detail layout shift: server-render game count and rank distribution
- Optimize developers page: add hierarchy caching service to eliminate recursive N+1 queries
- Theme refinements: fix background color (base-200), use accent color for rankings and sidebar

## 2025-12-31

- Add played games filter: three-way toggle (All/Played/Unplayed) with URL params and client-side filtering
- Developers page redesign: add Top Rank, Top Game, Subsidiaries columns with new sort options
- Make rankings page the homepage (redirect /rankings/ and /games/ to /)
- Add player rank/percentile to profile: shows ranking among players who've played the same games
- Navigation overhaul: reorder nav items, mobile priority system, consolidate Terms/Privacy into Legal
- Fix layout shift issues: CSS Grid for sidebar, filter skeleton heights, Load More state management
- Add Microcomputers sub-grouping in platform filters (Commodore, UK, Japan, Atari, Other)
- Unify game row templates: desktop/mobile partials with data-slot attributes for JS template cloning

## 2025-12-30

- Implement user authentication with django-allauth: email/username login, signup, forgot password, email verification
- Custom User model: consolidate auth.User, Subscriber, and UserProfile into single games.User model
- Add PlayedGame model and played button UI (Mario star when played, HTMX toggle, client-side sync)
- Auth modal: multi-step HTMX flow for login, signup, profile editing, and password reset
- Jump to Rank: client-side filtering for instant navigation with validation
- Test speed optimization: parallel execution (36s→12s), in-memory SQLite, setUpTestData
- Fix client-side renderer to match Django template (desktop:grid, hover effects, played button)
- Remove Posts feature and old newsletter pages (consolidated into auth flow)

## 2025-12-29

- Redesigned game row hover: title shrinks, rank scales up, thumbnail expands with full cover art
- Year grid heatmap: orange color scheme with theme variants, smart corner rounding based on adjacency
- Mobile filter improvements: full-screen sheet, dim zero-count items, clear buttons with labels
- Platform year ranges: move from hardcoded JS to database fields for admin management
- Responsive layout: reduce filter width 15%, lower breakpoint (1088px→962px) for narrower desktops
- Fix N+1 query issue in developers page: use prefetch cache (reduces queries ~16 to ~3)
- Fix IGDB import: developer parent chains now correctly set (e.g., Nintendo EAD → Nintendo)
- Filter sections: default collapsed, remember expansion state in localStorage

## 2025-12-28

- Client-side filtering: pure client-side with loading skeleton, removed server fallback
- Developer search: unified games + developers + series in nav search bar with "See all results" links
- Platform filters: added canonical year ranges, fixed count double-counting, improved sorting
- Filter appearance: removed checkboxes, unavailable options now dimmed instead of hidden
- Developers list: added sort options (# Games, Name A-Z), recursive game counting
- Tablet/Desktop layout: narrowed sidebar, compact controls, fixed breakpoints (1024px/1088px)
- Genre system: added mappings (Bullet hell→Shooter, Roguelite→Roguelike), fixed orphan hierarchy bug
- Add pre-commit hook for automatic JS minification (prevents stale .min.js files)

## 2025-12-27

- Added client-side filtering with IndexedDB caching for Rankings page (instant filter updates)
- Simplified genre filtering from multi-select to single-select with clear (×) buttons
- Fixed genre normalization bug: management commands now normalize Wikipedia genres consistently
- Added --cleanup-orphans flag to fetch_wikipedia_metadata to remove orphan WikipediaGenre records
- Changed badge filter behavior: scroll to top instead of highlighting clicked game
- Updated desktop and mobile genre filter components with new single-select behavior
- Replaced Select All/Clear All buttons with company checkbox at top of developer studio filter tree

## 2025-12-16

- Fixed CSV download to use Wikipedia genres instead of IGDB genres (now matches genre display on site)

## 2025-12-15

- Added sorting options (Rank, Release Year, Alphabetical) to Rankings page with URL persistence
- Implemented Wikipedia genre hierarchy with multi-level filtering (replaces IGDB genres)
- Added genre normalization service to consolidate variant names (e.g., "MMORPG" variants → "MMORPG")
- Redesigned game row hover: square thumbnails, Global Rank on title row, smoother transitions
- Made platform and genre badges clickable to filter games with game highlighting
- Filter dropdown now excludes genres with 0 games while preserving parent categories
- Fixed Global Rank display on developer detail pages (now shows on filtered game lists)
- Added comprehensive test coverage for all sorting modes and filter combinations

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

- Implemented Wikipedia page lookup with Wikidata API (10x faster), fallback to OpenSearch
- Implemented newsletter subscription: double opt-in, email notifications on publish, token-based unsubscribe
- Removed Game of the Day feature (model fields, service, templates, views, tests)
- Created get_wikipedia_pages management command with CSV output and --save option
- Fixed theme persistence: validate localStorage, auto-detect system preference, restrict to lofi/forest themes
- Added time estimates and simplified progress UI for IGDB and Wikipedia imports
- Mobile home page now shows only top 10 games (desktop still shows 30)
- Fixed Wikipedia API response handling to prevent AttributeError crashes

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

- PageSpeed optimizations: self-hosted CSS (~600ms faster), deferred scripts, async MDI CSS, preconnect hints
- Fixed mobile CLS (0.31→target <0.1): logo aspect-ratio, icon sizing, x-cloak on hidden elements
- MDI CSS subset: reduced 53KB CDN file to ~1KB (98% reduction), self-hosted font with font-display: swap
- SEO: meta descriptions, canonical URLs, Open Graph/Twitter Cards, JSON-LD structured data, XML sitemap
- Security headers: HSTS, X-Frame-Options, Secure cookies; WhiteNoise Brotli/gzip compression
- Accessibility: skip navigation link, ARIA labels, improved text contrast for WCAG AA compliance
- Image optimization: lazy loading, explicit dimensions, fetchpriority, 2x retina support for covers
- Added robots.txt with sitemap reference (/robots.txt)

## 2025-11-25

- Added `sync_from_prod` management command for syncing production PostgreSQL to local SQLite
- Added contact form with Navi theme, Brevo SMTP email integration (console in dev, SMTP in prod)
- Backend refactoring: split utils.py (~1150 lines) into focused service modules
- JavaScript refactoring: created utils.js, consolidated duplicate fetch functions (~430 lines removed)
- CSS refactoring: extracted ~1000 lines from base.html to external stylesheets (main.css, import.css)
- Redesigned thank you page with Portal theme (animated envelope flying into glowing portal)
- Added optional author field to Posts (ForeignKey to User, displays as "Author · 2 hours ago")
- UI fixes: download CSV button shows text label, disabled browser autocomplete on search input

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

- Optimized IGDB import for maximum performance (100+ games/sec, 75x improvement with Pro tier)
- Achieved 95% overall test coverage with comprehensive test suite expansion
- Enhanced import page with file validation fixes, completion indicators, and auto-IGDB trigger
- Implemented dynamic tagline with real-time database counts
- Fixed developer list search double-load and implemented real-time search
- Added game counts to decade filters
- Upgraded to Heroku-24 stack and migrated repository from BitBucket to GitHub

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

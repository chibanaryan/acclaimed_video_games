# Developer Log

## 2026-10-31

- **A year range draws and clears as one fade, on both sites.** The gaps were
  shadows that fell behind the cells, and Clear's list render froze them
  outright. The fill and gaps are now boxes fading `opacity`, which keeps
  running through a render; the gaps take 100 ms of the fill's 150, because
  green over the page stays green longer than green over amber
- **`MUSIC_ENABLED` is gone.** Production had it on, so the off state was dead
  code. `music/access.py`, the CSRF failure view and every hidden-section
  branch went with it. Readers see no change; music is now public in
  development and tests too, and its test suites run as a reader, not staff
- **`rimraf` is gone from the CSS build.** It only deleted one folder and held
  `glob` and `minimatch` on versions with new advisories, so `build:clean` now
  uses Node's `fs.rmSync`. Nine packages leave the lock; the CSS is unchanged

## 2026-10-30

- **Caches cannot be refilled with old rows, in music or games.** Invalidated
  caches drop after the commit, not during it, and a write skips its save if
  a drop ran while it was querying (`core.cache_helpers.cached`). Games' hero
  counts could stay wrong for a day after an import
- **Smaller fixes the reviews found.** Old filter links keep redirecting past
  a cached landing page; any tracking tag stays on it; a trailing-dot host
  finds its site; a page with no artwork asks X for the small card; `/contact/`
  names the apex's copy as canonical
- **A cache error no longer fails a committed music write.** It is logged,
  and an import shows an amber warning naming the fix, where it used to
  report a live release as failed. The weekly metadata job finishes too
- **The modal's rank lines say what is true.** A percentage compares a reader
  with everyone else, so more games users see a slightly higher number; a
  leader or last place gets a position; "top 1%" is only said of the top 1%
- **The Account modal shows a reader's albums beside their games**, the
  current site's block first, with a rank among listeners. It is absent
  while music is hidden from them. The rank logic moved to
  `core/services/percentile.py`, shared with games, and a tie now shares the
  better rank in both sections: tied players were each told the worst
- **Three sites, one app: a landing page at `acclaimedmedia.org`, games at
  `games.`, music at `music.`.** `core/sites.py` and `SiteHostMiddleware`
  pick the URLconf by host. Music moves from `/music/` to the root of its
  host, every old apex path redirects to its new home, and each host has
  its own sitemap, robots.txt and canonical origin
- **One name and one sign-in.** Acclaimed Media everywhere, and domain-wide
  cookies renamed `am_sessionid` / `am_csrftoken`, so everyone is signed out
  once. The contact pages go neutral; the Zelda 404 stays on games
- **The sidebar's toggle becomes a site menu**, the music Import links go,
  and music says it is in beta on every page and every way in (`MUSIC_BETA`)
- **The old default `og:image` is gone.** Pages without artwork of their own
  now have none until new art is drawn; game and album pages keep their
  covers, and a game with no cover no longer sends `None`
- **Sharper game covers on the landing page**: a 2x `srcset`, as the rows
  have, for a cover shown at ~84px. Midwest Emo is classified, as an alias
  of Post-Hardcore: one album, too few for a leaf of its own
- **Sentry triage after the move.** `manage.py shell` no longer reports, on
  a dyno either, since each typo in a one-off query filed an issue and fired
  the alert. A Cover Art Archive request that keeps failing is a warning,
  because the cover pass falls back to the group's releases (all 1000 albums
  have covers). The uptime monitor moved from the landing page to `games.`
- **The Donate page is ready for an enforced CSP.** Ko-fi's script widget is
  now a plain link in the FlatPage, and `form-action` allows PayPal, whose
  buttons enforcement would have stopped

- **Music's rankings pages batch their cache reads too**, as games' did
  the day before: `/music/` and its genre and decade landing pages make
  one `get_many` and the nav's articles check, from 7-9 reads. The
  landing views now inject their filters in `render_rankings`, inside the
  batch (`MusicCacheRoundTripTests`)
- **Links into `?highlight=` URLs are `rel="nofollow"`**, in all three
  sections' detail pages and rows, server- and client-rendered. robots.txt
  already disallowed them; Meta's crawler walked the game badges anyway
  (`core/tests/test_nofollow_links.py`)
- **Developer machines no longer report to Sentry.** Tagging them
  `development` kept them out of production's numbers but not out of the
  inbox: 40 issues in two weeks against production's 22, and the alert rule
  covers every environment, so a mid-edit syntax error in a worktree emailed
  this morning. `core.csp.sentry_enabled` gates `sentry_sdk.init` and the
  CSP's `report-uri`; set `SENTRY_ENVIRONMENT` to anything else to opt in
- **`scripts/smoke_seed.py` refuses a database that already has data.** Run
  locally it collided on "Super NES", then on its own "Smoke Action" from
  the first attempt (ACCLAIMED-VIDEO-GAMES-9G/9H)
- **The open issues were all triaged, and no live bug was among them.** The
  three `cache_table` N+1s stopped with `a609570`: `/` went from ~14 reads a
  request to 2. The old-domain CSP issues are Meta's crawler re-rendering
  pages stored before the move, carrying a policy no change of ours can
  reach (see "Content Security Policy" in `AGENTS.md`); archived for 30 days

## 2026-10-29

- **The site moves to `https://acclaimedmedia.org`, at the bare root.**
  `settings.CANONICAL_ORIGIN` is now the one place the origin is written
  (canonical and Open Graph links, structured data, robots.txt, the email
  footers, the fetchers' User-Agent), where it was hard-coded in nine.
  Migration `0122` moves `Site.domain`, which the sitemap reads. The new
  root is DNS-only to Heroku, so `get_client_ip` still sees the visitor;
  `www.acclaimedmedia.org` and the old domain are 301s at Cloudflare's edge.
  The name and `contact@acclaimedvideogames.com` stay
- **The repo is `chibanaryan/acclaimed_media`** (was `acclaimed_video_games`;
  GitHub redirects the old URLs). The Heroku app stays `acclaimedgames`
- **Search leads with the better match, in both sections.** "Beatles"
  filled all five album rows with Beatles albums, matched on their credit
  line, and the band sat below the dropdown's fold. Each group is now
  scored (exact name, word start, substring, credit-only) and the best
  group comes first: "Beatles" leads with the artist, "Nintendo" with the
  developer, "Halo" with the series, "Abbey Road" with the album. Albums
  and games stay in rank order except an exact title
  (`core/services/search_ranking.py`)
- **List types come from the release file.** `ListData.txt` gained the
  games file's type column; an unknown word fails the import with its row
  number, and the title-guessing `infer_list_type` is gone (it filed
  AllMusic's "Decade in Review" as all-time)
- **Music marks are illustrated, as games' are.** Heard is a gold record
  and Have that record leaving its sleeve, as Played is the Mario Star;
  Want is the record with a plus, as games' is the star with one. Both
  sections' status filters are now the one shared control, each option
  showing its button's mark in its colours
- **Artist and developer lists:** the count is the second column, centred;
  the top item's rank moved under its title, where in a column of its own
  it read as the artist's rank. The developer sort sits beside the search
  box, as the shared control the artist list uses

- **The CSP lets GA4 send its hits to `www.google.com`.** gtag.js now also
  posts to `https://www.google.com/g/collect`, which `connect-src` didn't
  allow, so Sentry reported it (ACCLAIMED-VIDEO-GAMES-99, from `/lists/`).
  The policy is still report-only, so nothing was being blocked. The source
  is scoped to that path, so the rest of google.com stays out, and the test
  reads the served header
- **The games rankings page reads the shared cache once, not fifteen
  times.** In production every `cache.get` is a Postgres query, and a
  crawler walking `/?platforms=N&highlight=G` (which skips the page cache)
  paid ~15 of them per hit (Sentry ACCLAIMED-VIDEO-GAMES-9E). The view now
  fetches every key it needs in one `get_many`
  (`core.cache_helpers.batched_cache_reads`); pinned against a real
  `DatabaseCache` by `GamesHomeCacheRoundTripTests`

## 2026-10-28

- **Music artists have name variants instead of relation tags.** The
  provider's new release lists each artist with every name it is credited
  under, and credits an album to `artist,variant` (`8,1`: Prince, as "Prince
  and the Revolution"), with `VA` last for various artists. Five days after
  the tag system shipped, `ArtistRelation`, the `ArtistGraph` roll-up and
  "Appears on" are gone: an album is simply its credited artists'. The
  credit line reads as credited and links to the artist; "Also credited as"
  lists only the names a ranked album uses, since some variants are
  leftovers. 18 artists that became variants or dropped out (Prince and the
  Revolution, Neil Young & Crazy Horse, Wings, Crazy Horse...) were deleted,
  and their pages 404. Soundtracks credit an artist and others ("Jimmy Cliff
  & Various Artists"). The release itself: 996 albums kept, 4 added, 4
  removed, one new list (AllMusic's 2010s)
- **The album year heatmap no longer goes blank after a filter is
  cleared.** A page loaded already filtered (`/music/?listened=no`) gave
  the grid that filter's counts as its colour scale; clearing it asked for
  opacities over 100%, which the CSS drops, so only the filtered years
  stayed coloured. The page now renders the whole corpus's counts as the
  grid's scale (`year-baseline-counts-data`), and the grid caps the opacity
- **Artist slugs follow the current names.** Every import rebuilds them,
  numbering same-named acts by provider id, so 2Pac is no longer
  `tupac-shakur` and John Mayall no longer `john-mayall-the-bluesbreakers`.
  Fine while music is a staff beta; add old-slug redirects before launch.
  Same-named acts are told apart by their Wikipedia titles
  ("nirvana-british-band"), fetched with the Wikidata pass
- **Artist pages list "With other artists" apart** (Getz/Gilberto on Stan
  Getz's), still counted; **no artist pk is public** any more - `?artists=`
  takes slugs and `/api/music/all/` is keyed by slug - since the pks gave
  away the provider's entry order; and the import **warns when an artist
  id seems reused** for a different act

## 2026-10-26

- **Sentry's gzip-less uptime check gets a 2-byte 200.** Two Sentry uptime
  monitors poll `/` once a minute; one sends no `Accept-Encoding`, so it
  pulled the whole ~667 KB page every minute (~1 GB a day), and the router
  logged 6 H13s in 12 hours on those transfers, each cut off ~80 KB in.
  `UncompressedUptimeCheckMiddleware` answers it before rate limiting and
  sessions. The gzip monitor still fetches the real page. Sentry Support
  says the gzip-less check is not ours (our organization has one monitor,
  the gzip one at :17); the :39 check now logs its `sentry-trace` and
  `baggage` to `games.middleware.uptime` for them - temporary, remove once
  they name it
- **Lighthouse pass.** Mobile performance on `/` 92 → 98 and on the
  genre/decade landing pages 83 → 94; accessibility and best practices
  reach 100 on every page tested but one developer page (a tap-target
  size, left as is). Alpine no longer initialises the hidden
  desktop sidebar on phones or the mobile filter sheet before it opens,
  which was ~870 ms of the 920 ms init task at 4x CPU throttle; the album
  rankings page gets the same (~360 → ~75 ms on a phone). Developer pages
  went from 338 queries to ~7 on a cache hit (thumbnails and the studio
  parent chain were N+1s); `/developers/nintendo/` had taken ~800 ms
  server time on production
- **Filter changes are 3-6x faster**, on the games and album pages alike.
  A decade click reaches the list in ~60 ms instead of ~290 (~250 vs ~710
  at 4x), and every click's INP stays under 200 ms at 4x. The filter
  debounce now fires on the leading edge after the next paint, and the
  sidebar's platform, genre and series rows look themselves up by index
  instead of scanning reactive arrays. Back no longer cuts off Forward. The
  rank distribution chart morphs in every browser: it relied on a CSS
  `transition: d`, which WebKit lacks, and is now a frame-capped JavaScript
  tween that respects reduced motion
- **Smaller fixes:** the contact form's Navi icon is self-hosted and lazy
  (35 KB hotlinked on every page → 1.4 KB on open); the game cover is no
  longer squashed and its preload is emitted once, early; an IGDB
  preconnect; labelled selects, accessible names and raised text contrast,
  on the album pages too (Discogs credit and notice, media switcher tabs,
  empty filter rows); music's tracking script no longer blocks first paint;
  overflow fixed for long studio names in the developer filter tree, the
  studio and genre lines of mobile game cards, and long titles in the
  sidebar search dropdown (DaisyUI menus size to their content). Jump to
  rank on a landing path (`/games/2010s/`) jumped in the unfiltered list;
  the played toggle is atomic; `/developers/?sort=name` drops studios
  with no games; game JSON-LD is valid and every game URL has a sitemap
  `<lastmod>`; the admin article preview is styled in production. The
  shared cache is keyed per Heroku release; CI checks minified JS,
  migrations and manifest-storage renders; tests cannot reach the network
  (four were calling IGDB and HowLongToBeat); the `?v=N` busters are gone.
  Client-built rows (Load More, the grid, any filter change) dropped
  Game & Watch, Vectrex and three microcomputer platforms, which the
  renderer's family map lacked, so Donkey Kong showed no platform; the
  client heading had drifted the same way. Tests now hold both to the
  server's tables
- **Six CodeQL alerts fixed.** The IGDB client secret rode in the Twitch
  token URL, so a failed auth logged it (and sent it to Sentry); it is in
  the POST body now. Login and logout followed any `Referer`, an open
  redirect; they now follow only this site's. The staff import streams
  sent raw exception text to the browser; they log it and say "see the
  server logs". The filter cache key hashes with SHA-256, not MD5.
  Rate limits read the last `X-Forwarded-For` entry, the one Heroku's
  router appends; the first was the client's to forge, and allauth's
  limits keyed on the router, one bucket for every visitor. The auth
  modal enforces signup, reset and verification-email limits. 76 of 210
  malformed query strings (`/?genres=abc`, `/api/games/?order_by=x`)
  returned 500s; they no longer do, and `order_by` and `limit` are bounded
- **Open-ended games show no playtime.** HLTB's "Main Story" for League of
  Legends (~1162h), WoW or Rocket League is time invested, not time to
  beat, so "Playtime: longest" opened on MMOs and "Short" listed Rocket
  League. `HLTBGameData.is_open_ended` comes from HLTB's own `game_type`
  (not `comp_lvl_combine`, which marks any co-op or versus mode), plus
  ~190 staff calls made in the admin (sandbox sims, sports league sims,
  looping arcade games, endless puzzle games). Those games are left out of rows, sort,
  filters, counts, the backlog total and the CSV; the detail page keeps
  the hours under a "No finish line" note
- **Accessibility and a Content Security Policy.** The year grid, genre,
  platform, series and playtime rows and the section headers work from the
  keyboard and announce their state; the mobile filter sheets are dialogs
  (focus kept inside, Escape closes, focus returns); result counts are
  announced. A report-only CSP: every inline script carries the request's
  nonce, cached pages included, and inline handlers became delegated
  listeners. A browser smoke test and a client/server parity test joined
  CI; the parity test found games' name sort disagreeing with the
  database's collation, now sent as a server index (`ni`) as music's is
- **The games filters are one function** (`apply_game_filters`): the
  sidebar counts and the CSV ignored accent-insensitive search, the counts
  ignored series and playtime, and the CSV ignored the sort. Also: SEO
  descriptions for developer and list pages, a real 500 page, newsletter
  emails sent off the request, Sentry Crons for both Sunday jobs, a
  `/healthz/` that checks the database, platform years kept across imports,
  the navbar search matching developers and series in the database,
  `games/views.py` split into a package, and the deploy skill waiting for
  CI and backing up before migrations


## 2026-10-25

- **Python 3.14 and Django 6.1, every package at its latest.** The
  `django<6.0` cap is gone (it was only there because Django 6 needs Python
  3.12+), along with Dependabot's Django-major ignore. Email moves to
  Django's `MAILERS` setting, unchanged in behaviour. A scheme-less URL
  typed into an admin URL field now gets `https://`, not `http://`
  (Django 6.0's new `assume_scheme` default). Tailwind 4.3, DaisyUI
  5.7, postcss-cli 12, postcss-nested 9, Black 26, flake8 7.4 and Actions
  v7 come with it; the CSS grows 32 → 36 KB gzipped, with no visible change
  apart from a ~3px shift in the music Filters header
- **Remove the unused YouTube Data API helpers.** Nothing called
  `is_youtube_video_embeddable` or `check_youtube_videos_embeddable`, so
  `YOUTUBE_API_KEY` goes with them. Game pages embed trailers from IGDB's
  `youtube_video_id`, which needs no key
- **Python dependencies are pinned.** `requirements.in` / `requirements-dev.in`
  compile to locked `requirements.txt` / `requirements-dev.txt` with
  pip-tools; Heroku builds are reproducible, and test and dev tools no
  longer ship to production. Dropped `anthropic`, unused since the
  GameQuote feature went
- **Dependabot and CI.** Weekly grouped update PRs for pip and npm, security
  updates, secret scanning and push protection on GitHub. A GitHub Actions
  workflow runs lint, both test runners, the suites on Postgres 18, a
  dependency audit, and a check that the committed CSS matches a fresh build
- **Six high npm advisories fixed** in the CSS build tooling (postcss and
  transitive glob/minimatch); the compiled CSS is byte-identical
- **The test suite runs on Postgres** in CI. Migrations `0055` and `0061`
  now apply to a fresh database; tests that reach an import thread run it
  inline instead of committing past the test transaction
- **The staff batch import validates prerequisites again.** It passed
  "GAMES" where the check expects `TYPE_GAME`, so games without platforms
  (or positions without lists) were never refused up front; five tests
  that should have caught it patched stale `games.utils` names
- `/upgrade-deps`: the monthly upkeep routine. The shared venv is rebuilt
  on Homebrew's Python 3.11.17, production's patch, from the locks; its
  `sitecustomize.py` certificate workaround is no longer needed

## 2026-10-23

- **Music artists come from the provider's `ArtistInfo.txt`.** The release
  is now four files: every artist under a permanent id, with tags for how
  it is made up (alias, project, collaboration, featuring, backed by), and
  `WebRankings.txt` credits albums by artist id. The importer no longer
  guesses artists by splitting credit text on commas, and the Wikidata pass
  no longer rewrites credits; credit lines are derived ("Paul McCartney &
  Wings", "Various Artists"). Artists upsert by id, so pages and links
  survive imports. Migration `0008` drops `Artist.parent` for an
  `ArtistRelation` table and puts credit order in an `AlbumCredit` through
  table
- **Artist pages roll up projects and aliases.** Purple Rain is on Prince's
  page as well as Prince and the Revolution's; Déjà Vu on CSN's and Neil
  Young's. Featured and backing acts get an "Appears on" list instead. Pages
  show "Project of …" lines and "Also credited as" links, album pages spell
  out a joint act's make-up and "More by" names the main artist, and
  `?artists=` expands the same way on the server and in the browser
- **Artist search finds acts that only appear on others' records**
  (Crazy Horse), after the owners, labelled "appears on N albums"
- **Music imports keep albums instead of recreating them.** Albums are
  matched on any of their Wikidata ids and updated in place, so pages,
  covers, genres and listening history survive a new release; only added
  albums wait for metadata. The import, `--dry-run` and the staff page
  report albums kept, added and removed
- **The MusicBrainz pass adopts orphaned rows whole** rather than
  re-fetching them. After the last release it re-requested all 1000 albums
  (~22 minutes); a re-import now leaves a metadata run with almost
  everything skipped
- **Weekly refresh of the stalest MusicBrainz data.** `--refresh-stale 125`
  re-reads the 125 oldest rows per run (~2 minutes), so genre tags and
  release dates are re-read every eight weeks

## 2026-10-22

- **Tidy the subscriber email for news posts.** The "Read More" button
  linked to `/#latest-news`, an anchor nothing on the site carries, so it
  just opened the home page; it is gone, since the email is the whole post.
  The subject is the post's title alone, the date replaces a "By Acclaimed
  Video Games" byline that repeated the sender, and the plain-text part is
  the post's markdown, which keeps paragraph breaks and link URLs that
  stripping the HTML's tags lost

## 2026-10-20

- **The admin tells "Have" from "Heard".** Have is a `ListenedAlbum` row
  with `owned=True`, not a table of its own, and the admin showed neither
  the field nor the difference: the User admin's "Listened" count and list
  lumped both together. The Listened albums changelist now has an Owned
  column and filter, and the User admin has separate Have and Heard counts
  and lists

## 2026-10-19

- **Jump to rank renders 50 either side of the target**, not every row
  from #1 down to it (8,000 DOM rows at game #4,000). A target already on
  the page just scrolls, one within a page of the rendered rows extends
  them, and a new **Load Previous** button fills in what a jump skipped;
  the count reads "Showing 950–1,050 of 1,400". Games and music. Focusing
  the games jump box now also starts the engine, which it never did, so
  every jump had been fetching each page down to the target from the server
- **Fix highlights fading before the row arrived.** A `?highlight=` link
  or a jump faded on `mouseenter` of any other row, and rows sliding under
  the still cursor during the smooth scroll fire it, so the highlight was
  gone on arrival - and it often went on the row wrapper, which nothing
  colours. One `flashHighlight()` in `utils-base.js` now waits for the
  scroll to settle and fades only on a real pointer move
- **Quick-mark mode**, from a reader marking off their collection: a
  "Mark" button in the results header (beside Filters on mobile) picks a
  status, and one click on an item's button then applies it - a second
  click clears it - instead of opening the menu each time. Music and games
  both; remembered per browser, off on detail pages. The results header is
  now a three-column grid, so the count sits at the true centre and no
  longer overflows narrow desktop windows
- **Albums gain a "Have" state** for readers who track what they own:
  Have / Heard / Want / Untracked, exclusive, with "Listened" relabelled
  "Heard". Stored as `ListenedAlbum.owned` (migration `0007`), so old
  `?listened=yes` links and saved filters are unchanged; new
  `?listened=own` filter and `?status=own` toggle. Its icon is the record in
  a filled sleeve
- **Fix `?highlight=` links not landing on the album.** A genre or decade
  link from album detail opened the rankings with the row marked but
  nothing scrolled to it, and an album past the first hundred was not
  rendered at all. `album-client-filtering.js` now scrolls on load, paging
  down through the engine when the album is further on, as the games page
  does. View mode comes from the engine, not the container's Alpine class,
  which is not applied yet on a fresh load in grid view
- **Album detail names the artist once**, in the subtitle under the title;
  the properties table's "Artist:" row repeated it
- **Artist pages sort by Rank or Release Date**, for artists with three or
  more albums, swapped in place over HTMX with the shared entity sort
  control. Rank stays the default; "best is" names the top-ranked album
  whatever the order
- **Music's year sort is now "Release Date"**: within a year, albums run in
  release order instead of by rank, on the rankings, landing pages, CSV and
  artist pages, server and client alike. New `Album.release_date` from
  Wikidata P577 or MusicBrainz, refreshed after each metadata run and
  backfilled by migration `0006`; the year stays the published one, and
  undated albums sit last in their year. `?sort=year` is unchanged
- **Artist pages show the full release date** ("November 4, 1970"), or the
  month where that is all that is known - a month-precise date is stored as
  the 1st, so its precision is stored too. Until the next Wikidata pass in
  production, Wikidata dates show their month only

## 2026-10-18 (music: ready to launch behind MUSIC_ENABLED)

- **`MUSIC_ENABLED` is the public-launch switch.** Off (the default, and
  production until the config var is set) is exactly the staff-only beta.
  On, every music read is public; the listen toggle and saved filters want a
  login, answering a signed-out visitor as games does (login redirect, 403);
  `/music/import/` stays staff-only. One predicate, `music.access.
  music_visible_to`, behind `MusicVisibleMixin` and `MusicAPIGateMixin`.
  The setting is read through `settings`, not the raw environment
  `BOOKS_ENABLED` reads, and is forced off under test
- **Nav keys off the flag alone**, so staff still see no link during the
  beta. On, the media switcher gains a Music tab (and shows with books off),
  the games mobile nav a Music icon, the sitemap four music sections, and
  robots.txt its two music rules, which would otherwise name the hidden
  section in a public file. The Beta badges go
- **Fix a signed-in outsider learning the saved-filter API existed.** DRF
  authenticates before it checks permissions, and session authentication
  enforces CSRF for any signed-in user, so a token-less POST got "CSRF
  Failed" 403 instead of the section's 404. The gate now runs in `initial()`
  before authentication
- **Discogs attribution, from its API terms** (read by hand; the site 403s
  fetches): the non-affiliation notice verbatim at the foot of every music
  page, and "Data provided by Discogs" beside the data, linked without
  `nofollow` - on album detail under the genres, linked to the master, and
  once beside the genre filter and an artist's album list. No Restricted
  Data is used. The six-hour freshness clause and our reading of it are in
  AGENTS.md
- **Music SEO landing pages**, `/music/genres/<root>/` (15 of 16 roots;
  Classical has 3 albums) and `/music/<decade>s/` (1950s-2010s), plus
  `/music/browse/`. The rankings page at a self-canonical URL with its
  filters injected, an ItemList, a meta description and the natural
  heading ("Most Acclaimed Rock Albums of All Time"); sitemap-only, and
  404 while the section is hidden. No year pages: `/music/1999/` is an album
- **Album slugs avoid every fixed `/music/` segment**, decades included -
  `search`, `lists`, `artists` and the rest were already shadowable by an
  album of that name
- **The client pushed filter URLs relative to the current path**, so on a
  landing page clearing the genre pushed the genre's URL and a reload
  restored it. Pushes now go to `/music/?...`, and Back to a landing page's
  bare path restores its filters. `media-list-controls.min.js` is `?v=5` on
  every page that loads it (the artist and source-list pages were on 3)
## 2026-10-18 (music genres: the MusicBrainz labels classified)

- **The first MusicBrainz pass brought 104 labels the vocabulary did not
  know**, plus Discogs' "Nu-Disco" on prod. All are now a leaf alias
  ("garage rock revival" -> Garage Rock, "2-step" -> UK Garage), a root alias
  ("motown" -> Soul, "dirty south" -> Hip Hop) or a dropped tag
  ("progressive", on everything from Master of Puppets to 3 Feet High and
  Rising). `RealVocabularyTests` lists all 367 MusicBrainz labels in use
- **Three obvious readings misfiled albums and were changed:** "ambient pop"
  as Dream Pop put Bon Iver under Rock, "minimal synth" as Synth-pop put
  Suicide under Pop, and "tejano" as Latin put Marty Robbins under World,
  because Discogs' "Folk, World, & Country" counts as a second vote. Read
  the rebuild's per-album diff before shipping a vocabulary change
- 10 albums gained a genre (Pearl: Blues; Secrets of the Beehive: Art Pop);
  none lost one, and the tree stays at 103 leaves
## 2026-10-18 (rankings page weight, and gthread)

- **The rankings page is 690 KB anonymous (was 897 KB) and 833 KB logged in
  (was 1.35 MB)**, measured on the local corpus with the test client
- **The server renders no grid cards.** The 100 hidden cards were ~160 KB of
  every page. Grid mode shows the list rows until the client-side filtering
  bundle, fetched at once for a grid reader, builds the grid; the rows are
  hidden only `:has(.game-grid)`. Load More and jump-to-rank build a grid
  from rank 1 when none exists yet
- **Platform and genre spans name their filter in data attributes**; one
  delegated listener in `base.html` replaces an inline onclick on every span
  (~54 KB), on game and album rows alike
- **One game status menu per page.** Each of the two buttons per game carried
  its own Alpine dropdown and three `hx-post` items; `played-menu.js` now
  opens one shared `#played-menu` beside whichever was clicked (~250 KB
  logged in). The twin-sync script also copies the tooltip and aria-label
  now, and the menu flips below a button the mobile header would cover
- **Two older bugs grid mode would have hit on every visit**: a
  client-rendered Load More loaded two pages per click (the button's own
  listener and `utils-loadmore.js`'s delegated one both answered), and
  switching view rewrote `/` as `/games/?start=1971&end=2025`
- **gunicorn runs `--worker-class gthread --threads 2`.** The rate limiter's
  counter is now `add`-then-`incr`, so two threads meeting a new key both
  count, and the importer's background threads close their DB connection
  when they finish rather than when the garbage collector gets to them

## 2026-10-18 (Sentry: a laptop is not production)

- **Two "production" issues came from a local shell script.** The local
  `.env` carries `SENTRY_DSN` and `sentry_sdk.init` never set `environment`,
  so the SDK's default filed every local runserver, shell and agent script
  as production. Neither error (ACCLAIMED-VIDEO-GAMES-7W/7X) was in app code
- **`SENTRY_ENVIRONMENT` now defaults from `DYNO`**: `production` on any
  Heroku dyno, `development` everywhere else, overridable by setting it

## 2026-10-18 (housekeeping)

- **The second test runner had already been lost.** `manage.py test
  games.tests` ran on every commit from `.git/hooks/pre-commit.legacy`, which
  today's venv rebuild deleted when it re-ran `pre-commit install`. It is now
  a versioned manual-stage hook (`pre-commit run django-tests --hook-stage
  manual`, via `scripts/run_tests.sh`) covering all four apps, not just
  games, and documented in AGENTS.md. All 3134 tests pass under it. `tblib`
  joins `requirements.txt` so that a parallel failure reports a traceback
- **`/api/books/all/` reads the genre table once**, through
  `core.services.genre_tree.descendants_by_id`, the way music and games
  already did. An eight-genre test tree cost 18 `books_bookgenre` selects
- **`MEDIA_URL` / `MEDIA_ROOT` are gone**, along with the DEBUG-only media
  route. The forum's avatars were their only consumer. `FORUM_ENABLED` is
  unset on Heroku (v855)

## 2026-10-18 (music metadata on a schedule; first MusicBrainz pass)

- **`DISCOGS_TOKEN` is set on Heroku.** The Discogs pass was paced by the
  anonymous 25 requests a minute, about 40 minutes for 1000 albums
- **The music refresh runs weekly on Heroku Scheduler**:
  `python manage.py fetch_album_metadata --weekly --with-musicbrainz`, a
  daily job that `--weekly` turns into a Sunday one, as games'
  `refresh_all_metadata --weekly` does. Not `--force`: every pass but
  Wikidata skips what already landed, so a routine run costs seconds plus
  whatever an import left missing. `--with-musicbrainz` adds the pass to the
  others; `--musicbrainz` still means that pass alone
- **The MusicBrainz pass ran for the first time on this release.** 1000
  release groups in 20 minutes, no errors, with a 503 backoff every few
  seconds that the client absorbed. The genre rebuild changed 412 albums and
  took the tree from 95 leaves to 103, none with a single album; no album is
  without a genre. It also surfaced 105 MusicBrainz labels the vocabulary
  does not classify (`progressive` 18 albums, `pop soul` 14, `ambient pop`
  13, ...), which add nothing until they are classified - see ROADMAP
- The games `--weekly` guard had no test; it has one now, and the
  refresh-metadata skill's "Schedule: Weekly" (a frequency Heroku Scheduler
  does not offer) now says what the job actually is

## 2026-10-18 (album covers: a front flag is not a sleeve)

- **"It Takes a Nation of Millions" showed a photo of its jewel case and
  disc.** Its release group's art is broken on archive.org, so the cover pass
  fell back to the earliest release, whose only image is one photo of the
  whole package tagged Front + Back + Medium. `_pick_front_cover` took the
  first `front` image and never read its `types`
- **Covers are now ranked by their Cover Art Archive types**
  (`music.musicbrainz.cover_quality`): clean, compromised (Obi, Sticker,
  Spine) or package photo (Back, Medium, Tray, ...). A non-clean pick sends
  the pass through the releases for a clean scan, keeping the best that
  downloaded rather than none. An audit of all 1000 covers found 9 to re-pick
- **Cassette releases sort last in that walk**, from `inc=media` on the same
  browse request: a J-card is tagged a plain Front, and The Rising swapped a
  shrink-wrapped CD for one until the format was consulted. Releases
  MusicBrainz says have no front art are dropped before the 12-release cap
## 2026-10-18 (music genres: our own vocabulary, voted on by three sources)

- **The album genre tree had 207 leaves, 73 holding a single album.** Every
  Discogs style became its own row. `genre_normalizer.GENRE_VOCABULARY` now
  names every genre (16 roots, ~125 leaves) and classifies each Discogs and
  Wikidata label as a leaf, an alias ("Glam" -> Glam Rock), a root, or a
  dropped descriptor. After pruning leaves under 3 albums: 95 leaves, none
  with a single album
- **45 unmapped styles were misfiled.** Their root came from the album's own
  Discogs genres, so Bubblegum sat under Electronic, Son under Jazz, and
  "Post-Modern" moved between Classical and Electronic every run. An
  unclassified label now creates nothing
- **Wikidata was evaluated as a replacement and rejected.** It has more
  distinct labels than Discogs (272 vs 222) and names one genre for 533 of
  973 albums. Discogs stays the base; Wikidata and MusicBrainz only add what
  a second source corroborates. A strict two-source rule was tried and lost
  real genres (*Purple Rain* lost Funk)
- **Hybrid leaves tag a second root on the album.** Folk Rock, Country Rock,
  Synth-pop and a few others sit under one parent in the tree, but *Harvest*
  is now under Rock as well as Folk and Country
- **`rebuild_album_genres` derives genres offline, corpus-wide.** The metadata
  passes only store; `fetch_album_metadata` runs the rebuild at the end.
  Aliased rows are renamed in place so `?genres=` ids survive, and saved
  filters naming a deleted genre are remapped

## 2026-10-18 (the rankings page: 1.4 MB -> 870 KB)

- **36% of every page was template indentation.** The row partials sit
  eight to ten levels deep and render 300 times on `/`, so 491 KB of its
  1.36 MB was leading whitespace. `core/template_loaders.py` strips it once,
  at load, inside the cached loader, so the cost is nothing per request.
  Each newline is kept, so `<a>A</a>` and `<a>B</a>` on two lines still render
  with a space between them. That is why it is not `django-spaceless-templates`
  or `django-htmlmin`, which remove whitespace between tags, and htmlmin is a
  per-request middleware that adds a second copy of the page anyway. The
  inside of `<pre>`/`<textarea>`, and every non-`.html` template, is left as
  written. `base.html` has a `<textarea>`, which is why the element is exempt
  rather than the whole template: skipping templates left the chrome
  unstripped. `/` 1.36 MB -> 870 KB, and every other page drops 23-39%
- **Logged in, `/` carried 448 KB of a script that did nothing.**
  `_played_button.html` renders twice per game, and each copy shipped a 2.2 KB
  `<script data-played-sync>`. On a page render that script re-adds the id to
  Sets `home.html` already filled, syncs sibling buttons the server already
  rendered alike, and announces `game-status-changed` before anything is
  listening. On an HTMX filter swap it announced it 200 times. It now ships
  only with the toggle response, the one place it has work to do. The 600
  per-button `hx-headers` CSRF copies, which repeated `<body hx-headers>`,
  are gone, from music's shared `_tracking_button.html` too. Logged-in `/`
  2.44 MB -> 1.32 MB
- **Measured, not assumed**, with prod-shaped settings (DEBUG off, cached
  loader, no toolbar). Render peak 9.0 -> 6.6 MB anonymous and 14.6 -> 9.0 MB
  logged in. Local maxrss after 60 cold renders was 334 -> 239 MB and
  365 -> 288 MB. 19 pages across games and music, anonymous and staff, are
  identical to before once whitespace is normalised, and their `<pre>`
  contents are byte-identical. In Chrome at 1440 and 420 px the rows,
  client-side filtering (which clones the now-stripped `<template>`s) and a
  played toggle all work, the toggle sending the token it inherits from
  `<body>`. The new tests fail against the old code

## 2026-10-18 (games genre hierarchy: one query, and no stale cache)

- **`/` cost 109 queries on a cold cache, 75 of them `games_wikipediagenre`.**
  All 75 came from `get_landing_genres`, which filters once per root genre,
  and every filter expanded its genre through `WikipediaGenre.get_descendant_ids`,
  which walked `children` a query per node - the N+1 music had. Games now uses
  `core/services/genre_tree.py` like music: `genre_descendant_map()` is one
  `(id, parent_id)` SELECT, `apply_genre_filter` takes it as `descendants=`,
  and `HomePageView._genre_descendants` builds it once per request for the
  list and both facets. `/` 109 -> 38, `/?genres=<root>` 109 -> 39, and
  `/api/games/all/` drops its own copy of the walk for `descendants_by_id`.
  All three are byte-identical to before, toolbar aside
- **The per-genre descendant cache was stale, and is gone.**
  `_expand_single_genre_with_descendants` cached under
  `genre_descendants:<id>`, while the `WikipediaGenre` signal deleted
  `genre_descendants:<id>:True` and `:False` - so re-parenting a genre in the
  admin left the filter expanding the old tree, in every worker, for 24 hours.
  In production the shared cache is a Postgres table, so a hit was a query
  anyway; the cache, `invalidate_genre_descendant_cache` and its receiver are
  deleted rather than fixed. Pinned by
  `games/tests/test_signals.py::GenreHierarchyChangesApplyImmediatelyTests`,
  and the page budget by
  `games/tests/test_main_views.py::GamesHomeGenreQueryBudgetTests`. All four
  new tests fail against the old code

## 2026-10-18 (artist Load More, hidden POSTs, year-count parity)

- **Load More on `/music/artists/` only ever loaded page 2, and never on a
  phone.** The button targeted the desktop `<tbody>`, removed itself after
  its request, and the append response sent no replacement. The response
  now wraps its rows in a `<table>` that the button's `hx-select` lifts the
  `<tr>`s out of, and swaps the mobile cards, `#loaded-count` and the next
  button in out of band. htmx 1.9 runs out-of-band swaps before
  `hx-select`, which is what makes one response feed both layouts.
  Checked in Chrome at 1440 and 420 px through all seven pages (627 rows,
  627 cards, the button gone at the end, appended cells the same width as
  the first page's)
- **An anonymous POST to any `/music/` path now answers 404.**
  `CsrfViewMiddleware` used to reject it with 403 before `StaffOnlyMixin`
  ran, which told an outsider which paths resolve. `CSRF_FAILURE_VIEW` is
  `core.views.csrf_failure`; staff still get the real 403
- **Under a genre or artist filter, every year cell read 1.** Those filters
  call `.distinct()`, a DISTINCT query has to select its ordering columns,
  and so `Album`'s default `rank` ordering went into `_year_counts`'s GROUP
  BY, making each album its own group. Found by the AGENTS.md parity check
  rather than by a test - the fixture had one album per year. Fixed with
  `.order_by()` and pinned with two albums in one year
- **`AlbumFilterEngine.facets()` now sends every year in the corpus range,
  zeros included**, as `_year_counts` does. The engine's year arrays now
  equal the server's for no filter, a narrow genre, a genre plus a decade,
  and the listened status. Bundle cache-buster bumped to `?v=3`

## 2026-10-18 (parallel worktrees; one local interpreter)

- **`scripts/setup_worktree.sh` provisions a worktree in ~2 seconds**, so
  several sessions can run at once without each paying for a checkout.
  `venv` (243 MB) and `theme/static_src/node_modules` (351 MB) are symlinked
  to the main checkout, `db.sqlite3` is cloned with `cp -c` - APFS
  copy-on-write, 100 MB in 4 ms, sharing blocks until one side writes - and
  the untracked `.env`, `.env.development.local` and
  `.claude/settings.local.json` are copied. That last one is ignored by the
  *global* gitignore, so a fresh worktree had been silently losing the
  permission allowlist. The old `conductor.json` setup built a whole venv per
  worktree and then migrated an **empty** database, so every worktree started
  with no games, no albums and no staff user
- **A `SessionStart` hook provisions whatever made the worktree** - Conductor,
  claude-squad, opencode, `/worktree`. It locates the script through
  `--git-common-dir`, so it runs the main checkout's copy even on a branch
  that predates the file, and `--quiet` keeps it silent when there is nothing
  to do, since a hook's output lands in every session's context
- **All eight existing worktrees were unusable, not merely stale.** Their
  `.git` files still pointed at `/Users/rchibana/Development/acclaimedgames`,
  the pre-rename path, so git refused to run inside any of them. Repaired
  with `git worktree repair` first in order to read them, which showed every
  branch fully merged and 8-10 months old but three holding uncommitted work
  - archived, then all eight removed, along with 47 merged branches
- **The venv was a major Django version ahead of production.** Django 6.0
  requires Python 3.12+, so prod's 3.11 resolved unpinned `django` to 5.2.18
  while a 3.14 venv resolved the same line to 6.0.1; the framework 3.14
  interpreter had 5.2.8, and a dead `activate` (also pre-rename) meant
  `source venv/bin/activate && pytest` silently ran that one instead. Rebuilt
  on 3.11 per `.python-version`, `django` pinned `>=5.2,<6.0` so a future
  `.python-version` bump cannot become a silent major upgrade, and
  `pre-commit` moved into the venv with the hook repointed at it - which ends
  the rule that every dependency had to be installed into both interpreters
- **Framework 3.11 ships no CA bundle**, and its certificate installer cannot
  write to `/Library` without root, so `ssl.create_default_context()` trusted
  nothing and every aiohttp call failed - the HLTB fetch above all. A
  `sitecustomize.py` in the venv points `SSL_CERT_FILE` at certifi. `requests`
  was never affected because it carries certifi itself, which is why only the
  aiohttp paths broke

## 2026-10-18 (saved album filters, on shared components)

- **The album rankings page can save a filter combination by name**, which
  was the roadmap's last open parity item. `core.models.SavedFilterSetBase`
  abstract, `music.SavedAlbumFilterSet` concrete,
  `/api/music/saved-filters/` for list/create/rename/delete, and three new
  `core/includes/` partials: the sidebar dropdown, the three modals and the
  sheet's collapsible block
- **Built shared, wired to music only** - the precedent album tracking set.
  The partials were lifted from games' own markup and bind to the method
  names games' `filterComponent` already exposes (`loadSavedFilters`,
  `applySavedFilter`, and six more), so games can migrate by swapping three
  includes. Nothing of games' own saved-filter code was touched
- **The whole feature is inert without a `savedFiltersUrl`**, so adding the
  methods to the shared `mediaListControls` gave books and any future
  section the capability without rendering them a button they cannot use
- **Applying a saved filter must not announce `year-reset`/`genres-reset`.**
  It did at first, on the reasonable-sounding theory that the sidebar needed
  telling. But those events do not mean "refresh": the mobile sheet's two
  subcomponents answer them by assigning the full year range and `[]`, and
  **the sheet shares the page's Alpine state at every width**. So applying a
  filter restored the sort and its direction and then silently dropped the
  genre and the years, with the heading naming the unfiltered page. Every
  server-side test passed and the stored JSON was correct throughout; only
  a real browser showed it. The grid and the tree read `filters` reactively
  and need no telling
- **`applyingSavedFilter` was a hook with nothing on the other end.**
  `_year_grid.html` has always passed `isApplyingSavedFilter` behind a
  `typeof` guard, so a component without the flag got `false` and the grid
  treated a programmatic range as a hover preview. Defining it lit the hook
  up with no template change - and the guard is why the omission could
  never throw, which is what made it worth a test
- **Games' `applySavedFilter` never restored `sortDirection`**, though
  `submitSaveFilter` had stored it since the feature shipped, so a saved
  "Year, newest first" came back ascending. One line, and pinned in source
  *and* minified form for both components, since the page loads only the
  minified copy
- **Music's first write endpoint**, so CSRF now applies to `music/api/`,
  whose docstring had said no unsafe method existed to trigger it.
  `StaffWriteAPIMixin` sits beside `StaffReadAPIMixin` to mark which views
  that covers. An outsider gets 404 rather than games' 403, and the CSRF
  behaviour is tested with `Client(enforce_csrf_checks=True)` because the
  ordinary test client does not enforce it at all
- **Three multi-line `{# #}` comments rendered as visible page text.**
  Django's `{# #}` cannot span lines; the headers had to be
  `{% comment %}` blocks. A sweep found no other instance in the repo
- **Verified beyond the suite**: 28 browser checks in real Chrome covering
  save, reload, apply, rename, delete, the duplicate-name error and the
  mobile sheet; a 5-case client/server parity check confirming the engine's
  rendered ids match `?partial=true` exactly, in order, with the engine
  confirmed to be answering locally; and seven games pages diffed
  byte-identical once the `?v=` literal is masked

## 2026-10-18 (music query counts; the filtered heading)

- **`/music/` cost 443 queries and now costs 26**, `/music/artists/` 305 and
  now 6, `/api/music/all/` **1218** and now 10. Two one-shape N+1s:
  `prefetch_related("children")` populates only the rows it fetched, so
  recursing into a child's own `children` is a query per genre - and
  `_genre_counts` walked all 223 twice per render. On the artist list
  `artist.albums.first` was unprefetched and the row then read `thumbnail`
  through an unjoined OneToOne
- **The roadmap had two things wrong here.** The 418 genre selects were not
  "the cost of a cache miss" - only the flat `.values()` list is cached, so
  every request paid all of them. And `/api/music/all/` had the worst N+1 on
  the site, unrecorded: 1000 albums each lazy-loading a MusicBrainz row from
  a missing `select_related`
- **`core/services/genre_tree.py` answers the hierarchy in one query**, with
  a cycle guard the games copy lacks. It returns the map in *arrival* order
  rather than the post-order the walk resolves nodes in, because callers
  iterate it to build the counts dict the page serializes. Deliberately
  uncached: games caches per genre because its hot path wants a few ids;
  music's wants the whole table, where 200 cache round trips lose to one
  SELECT of 200 rows
- **The artist list took a `Prefetch`, not games' bulk-fetch-and-attach**, so
  no template changed and both row halves, the HTMX partial and
  `?append=true` were fixed at once. The mobile card block runs
  `albums.first` a second time, which is why it was 200 selects for 100 rows
- **Output is byte-identical across eleven pages** once CSRF tokens and
  toolbar timings are masked, so no `SCHEMA_VERSION` bump. The budgets are
  pinned by SQL shape plus "adding rows adds no queries" rather than by a
  number, and every new test fails against the previous code
- **A genre clicked in an album row filtered the list but not the heading.**
  `album-client-filtering.js` answers `add-genre` by writing the hidden
  select and re-rendering from the engine; `filters` lives on
  `mediaListControls`, which owns the heading *and* the sidebar genre tree.
  So Rock albums showed under "Most Acclaimed Albums of All Time" with
  nothing selected in the sidebar, and a reload appeared to fix it because
  the server composes the heading from the URL. The row now announces
  `genres-selected` and the component listens. Games was never affected - it
  routes the event through `component.addGenre`
- **The games tab title never tracked filters at all.** `<title>` came from
  `seo_title`, which only the SEO landing views set, and nothing in the
  codebase set `document.title` during client-side filtering in either
  section. `base.html` now publishes one `window.documentTitleSuffix` and
  both filter components rebuild `heading + suffix`. Search stays out of the
  games heading on both sides, as before
- **Both script cache-busters bumped** (`filter-component.min.js` to `?v=8`,
  `media-list-controls.min.js` to `?v=3`). They are hand-maintained, so a JS
  fix that forgets them reaches nobody who has visited before

## 2026-10-18 (music genre icons)

- **Every music root genre has its own glyph.** Three were doubled up -
  `guitar-electric` for Rock and Metal, `guitar-acoustic` for Blues and Folk,
  and R&B sitting on `DEFAULT_GENRE_ICON` itself, so a name that fell out of
  the map was indistinguishable from one still in it. Metal took `skull`,
  Blues `piano`, Country `violin` (its `guitar-pick` rendered as a solid
  blob), Funk `music-clef-bass`, Hip Hop `boombox` and R&B the freed
  `microphone-variant`. `test_every_root_gets_its_own_glyph` pins both
  rules: no duplicate, and none equal to the fallback
- **Glyph names mislead at row size.** `record-player` was the obvious pick
  for Hip Hop and is unusable: at the 18px a filter row gives it, it and
  `cassette` collapse into a featureless horizontal slab. `boombox` survives
  because its two speaker circles stay open. Candidates have to be rendered
  from the rebuilt subset font and looked at, not chosen from the name

## 2026-10-18 (bulk listen marking; admin tracking columns)

- **`mark_albums_listened` marks a collection in one go.** Importing listens
  matched elsewhere - a RateYourMusic export - meant several hundred toggle
  requests through the web. The command takes the Wikidata ids that matching
  produced and does only the database half, with the toggle's semantics: one
  transaction, `update_or_create` on the `unique_together`, want-to-listen
  cleared for the same album, caches dropped on commit. Re-running is
  harmless, and an id already marked keeps its original `created` timestamp
- **The matching deliberately stays outside it.** Deciding that an export's
  "E·MO·TION" is our "Emotion" is a judgement call for whoever is looking at
  both lists, not something to bury in a management command
- **The User admin carries all four tracking counts**, with a read-only
  capped list of each and the same orphan fallback the game lists have: a row
  whose album a reimport removed names its Wikidata id rather than raising
- **Those counts are correlated subqueries now.** Four `Count(..., distinct=True)`
  annotations join four multi-valued relations onto one queryset and multiply:
  822 listened albums and 178 want-to-listen rows made 146k intermediate rows
  before `distinct` collapsed them again. One subquery each stays one row per
  user

## 2026-10-18 (web dyno memory)

- **The dyno is back inside its 512 MB quota.** It had been running at
  496-533 MB of RSS in every hourly bucket with up to 86 MB of swap, peaking
  at 604 MB (112.6%) and firing R14 and H27 all day. The roadmap's reading
  was right - a baseline footprint larger than the quota, not a leak - and
  the numbers now account for all of it: a worker boots at ~110 MB and
  plateaus at ~200 MB, flat from 50 page renders out to 1000, so three of
  them needed ~570 MB
- **Two workers, not three.** 2 x 200 MB leaves ~110 MB of headroom on a
  Basic dyno. `--preload` was measured and rejected: a forked child touched
  ~160 MB of the parent's pages within 20 requests, because CPython
  refcounts dirty the page holding every object they read, so
  copy-on-write saved nothing (593 MB preloaded vs 585 MB not).
  `--max-requests` is a guard against slow growth rather than a lever - a
  recycled worker is back at the plateau within ~15 renders
- **The site-wide page cache middleware is gone.** Every page varies on
  `Cookie`, so Django keyed a separate copy of each page on each visitor's
  cookie header - and stored nothing at all for a cookieless first-time
  visitor, since it skips the write when the response sets cookies and the
  request carried none. All of the cost, none of the benefit, at 1.4 MB an
  entry for any client that did not ask for gzip.
  `AnonymousResponseCacheMixin` is the whole-page cache now
- **Cached page bodies are deflated.** 48 SEO landing URLs plus the home
  page at ~1.4 MB each was up to 67 MB in every worker; it is ~5 MB now,
  and a cache hit returns byte-identical HTML
- **Page HTML can no longer evict the rate limiter.** The per-IP counters
  had been sharing `local`'s 500 entries with whole rendered pages, so a
  crawl wide enough to matter culled out the counters meant to stop it. They
  have their own `ratelimit` alias
- **The contact form works again from a cached page.** Its CSRF token was
  being cached with the rest of the body, so a visitor served the cached home
  page got a token minted from someone else's secret - and no cookie at all,
  since a cache hit renders no template and so never calls `get_token`. Every
  such submission 403'd, silently, for anyone whose first page was `/` or one
  of the 48 SEO landing pages. The token is now swapped for a sentinel on the
  way into the cache and minted per request on the way out. Pre-existing, and
  found while verifying the deploy
- Sentry now samples tracing at 0.1 with profiling off - not a memory fix
  (the SDK's ~30 MB per worker is the import, not the sampling) but it was
  tracing and profiling every single request. `AlbumCoverView` also stopped
  holding a second full copy of every cover it serves

## 2026-10-18 (album tracking)

- **Albums can be tracked.** `ListenedAlbum` / `WantToListenAlbum` on
  `core.models.UserTrackingBase`, a staff-only POST toggle at
  `/music/<id>/toggle-listened/`, the 48px column on both row halves, a
  Listen Status filter in the sidebar and the mobile sheet, and the large
  button on the album page. This was the last structural difference between
  the games and music sections
- **The button and the status filter are shared, not copied.** Games and
  books each carry a near-identical tracking button and games duplicates its
  status filter between the sidebar and the mobile sheet;
  `core/includes/_tracking_button.html` and `_status_filter.html` take the
  verbs, icons and route as parameters instead. Music is the first user and
  games and books are untouched, so nothing regressed to find out
- **No inline script ships with a button swap.** Games and books each send a
  `<script>` inside the swapped partial that mutates the global id Sets and
  then deletes its own earlier copies to stop them accumulating.
  `core/js/media-tracking.js` is one delegated listener, and a page registers
  what its scope means
- **Tracking rows survive a reimport.** An import deletes every `Album`, so
  the rows keep the album's Wikidata id beside a nullable FK and
  `reconnect_tracking_records` re-adopts them afterwards in one bulk pass -
  normalising a secondary id to the primary, and merging two rows that now
  point at one album. Games' per-album service would have been ~4000 extra
  queries inside a web request
- **Two bugs that only a browser could find.** `htmx:afterSwap` hands you the
  element the swap *replaced*, so reading `data-status` there left the id
  Sets one toggle behind for ever; and the client-side filter's HTMX
  suppressor sits on `#album-results-container`, so it was cancelling every
  row's toggle POST - but only once the bundle had loaded, which made it look
  intermittent. The listener now reads the request, the suppressor now only
  cancels GETs, and both are pinned by source tests
- **Icons are a vinyl record**: an outline when untracked, filled and
  accented once listened, a plus for the backlog. `mdi-album-outline` does
  not exist in MDI 7.4.47, so untracked is `mdi-record-circle-outline`, the
  one glyph added to the subset font
- Verified against the real 1000-album database in Chrome, including the
  client/server parity check over eight filter and sort combinations

## 2026-10-18 (music/games parity; shared ranking components; 1000-album release)

- **The rankings pages now render the same chrome from `core/`.** The year
  heatmap, the genre tree, the sort/direction/view/jump controls, the rank
  distribution, the publication groups, the list-type groups and the search
  box all moved out of `games/` and are shared by both sections, with games
  switched over to the shared copies. Music had grown its own: decade chips
  instead of the heatmap, a flat `<select>` where a root genre and one of its
  styles looked identical, and no view toggle or jump-to-rank at all
- **Row and card styling is one rule set.** `.media-*` had been copied from
  `.game-*` without the row-level hover, so album rows lifted their thumbnail
  but never showed the gradient, the lift or the accented left edge. The two
  class families now share every rule through selector lists
- **Album rows lead with the artist.** The credit sits on its own line under
  the title, indented with the metadata and a step above it in weight; square
  covers are sized to the row. Beside the title it was the first thing
  truncated, and on exactly the rows that needed it
- **The music genre filter expands descendants**, as the games filter does, so
  picking "Rock" means rock. Counts beside a genre are distinct counts across
  its subtree: summing a root and its children double-counted an album tagged
  both "Classical" and "Modern Classical", and the sidebar claimed Classical
  had two albums when it had one
- **`get_or_create_genre` corrects a stale root.** It returned an existing row
  untouched, so "Alternative Rock" stayed filed under Electronic for 68 albums
  long after the resolution order was fixed - the fix could not reach a row
  that already existed
- **Music gained what it was missing**: a search box in the sidebar and mobile
  nav (`/api/music/unified-search/`), a CSV download, a filter-aware heading
  that updates on both the HTMX and the client path, a mobile filter sheet, a
  per-section "Updated: ..." stamp, and faceted counts that narrow with the
  other filters
- **New release imported: 1000 albums, 67 lists, 24 publications.** The
  release-file tests now read their counts from the files rather than pinning
  the previous release's. `ARTISTS_WITH_COMMAS` gained "Tyler, the Creator",
  which was splitting into two artists
- An import does not fetch metadata, on either section. The music import page
  now shows which passes have work left and the command to run

## 2026-10-17 (shared cache; client-side filtering for music; books stack repaired)

- **Move the shared cache onto Postgres.** Production ran `locmemcache://` on one
  dyno with three gunicorn workers, so `_invalidate_music_caches()` cleared one
  process of four and a metadata refresh left stale genre and artist options for
  up to 24 hours. `core/cache_config.py` now builds two aliases: `default`, which
  is `DatabaseCache` on the existing Postgres in production, and `local`, a
  per-process cache holding whole rendered pages and the rate-limit counters -
  those are large or high-churn and would otherwise push every anonymous page's
  HTML into Postgres and cull the shared entries back out. `MAX_ENTRIES` is set
  explicitly; Django's default of 300 culls a third of the cache per write
- **Client-side filtering for `/music/`.** `/api/music/all/` serves the whole
  corpus (500 albums, 38 KB gzipped) and `music/static/music/js/` filters, sorts
  and renders in the browser, ending a full HTMX round trip per filter change on
  100-row pages. No IndexedDB and no `version/` endpoint: at this size neither
  pays for itself. It is progressive enhancement - the HTMX sidebar keeps working
  until the bundle has data, and if it never does
- The payload carries `nn` (`name_normalized`) and `ni` (the server's own
  `Lower(name)` position) so client and server agree exactly: reimplementing
  `unidecode` in JS would drift, and no comparator reproduces a database
  collation - `localeCompare` files "Ágætis byrjun" with the A's where SQLite
  sorts it past Z. Verified by comparing the engine's output against
  `?partial=true` over 22 filter and sort combinations
- **Repair the books client-side stack, which had never run.** Its template
  referenced a bundle filename the build script does not write (a render-time
  error under manifest storage, not a 404), the bundle omitted the base class its
  renderer extends, the view never set `enable_client_filtering` or the four
  context variables the page renders, and - found while verifying - all 13 books
  API read views named `IsStaffOrHide` without an authenticator, so with
  `DEFAULT_AUTHENTICATION_CLASSES` empty the entire read API 404'd for a real
  staff session. Existing tests missed that because `force_authenticate` bypasses
  authentication
- Exempt `/music/cover/` from rate limiting. One rankings page requests up to a
  hundred covers against a 120/minute budget, so a second page load 429'd - and
  client-side filtering re-renders a hundred rows per filter change
- New guards for the mistakes above: `core/tests/test_static_bundles.py` (every
  referenced bundle exists; every bundle defines the base classes its members
  extend), `music/tests/test_visual_regression.py` (the row emits every slot the
  renderer declares, including when rendered empty for a `<template>`), a
  session-login test for the books API, and `core/tests/test_cache_config.py`

## 2026-10-17 (music metadata pipeline; import views staff-gated)

- **Gate the games import views on staff.** `ImportView`, `IGDBProgressView`,
  `WikipediaPageProgressView` and `BatchImportProgressView` were
  `LoginRequiredMixin` only, so any of production's 268 verified non-staff accounts
  could open `/import/` and POST to `/import/batch-progress/` to replace or delete
  all 1,400 games, 920 lists and 22,215 memberships. They now use
  `core.mixins.StaffOnlyMixin`, which 404s rather than redirecting. Every existing
  test for these views authenticated as a non-staff user, so the fixtures gained
  `is_staff=True` and `test_requires_authentication` inverted from 302 to 404
- Add the album metadata pipeline: `music/wikidata.py`, `music/discogs.py`,
  `music/musicbrainz.py` (MusicBrainz plus the Cover Art Archive),
  `music/services/genre_normalizer.py`, `music/services/metadata_service.py` for the
  orchestration and DB writes, and `fetch_album_metadata` with a `/music-metadata`
  skill. The four clients share `music/services/http_client.py` rather than each
  re-implementing a session, a delay, retries and the difference between "no data"
  and "request failed"
- Wikidata is the hub rather than one source among several: every album carries a
  QID, and `wbgetentities` takes 50 ids per request, so ~25 round trips yield the
  performers, genre candidates, release date, label and - the point - the Discogs
  and MusicBrainz identifiers the other clients are keyed by. Measured over the 502
  QIDs in the release: P175 and P577 on 502, P436 on 500, P1954 on 498, P136 on 499
- **Genres come from Discogs, not Wikidata.** Wikidata's P136 labels are messy (two
  of the 207 genre entities have no English label at all, and the set includes
  non-genres like "stage and screen"), and deriving a tree from its P279 subclass
  graph classified only 159 of the 207 unambiguously while filing thrash metal
  under Rock and mbaqanga under Jazz, with ska, dub and ambient unreachable. Discogs
  instead publishes a curated two-level vocabulary - a closed top-level `genres` set
  and `styles` beneath it, which is exactly what `MusicGenre` models - and assigns
  it per album by exact master ID. 498 of 502 albums have one
- The 16 roots are ours, not Discogs': Discogs files Punk and Metal as styles under
  Rock and collapses Funk, Soul and R&B into one "Funk / Soul", which is too coarse
  for a site ranking acclaimed albums. `STYLE_TO_ROOT` records only the corrections
- A style's root is resolved **globally** - explicit mapping, then the style name's
  rightmost root word, then the album's Discogs genres. That order is the fix for a
  real bug: taking the root from the album's genre list made `Alternative Rock` a
  child of Electronic, because OK Computer is tagged "Electronic, Rock", and that
  one global row then represented every alternative rock album on the site. All 153
  styles the release uses now resolve with no album context, pinned by
  `RealVocabularyTests` so a new release fails the suite rather than silently
  dropping genres
- **Cover art is downloaded and served from our own origin, not hotlinked.** The
  Cover Art Archive is the right source but answers with a 307 to archive.org,
  which returns an intermittent 500 on images that are present a moment later -
  roughly one request in ten, with a few items broken outright. A list page showing
  a hundred covers therefore showed several broken images on every load. The bytes
  now live in `AlbumCover` (two sizes, ~34 MB for 500 albums) and
  `music.views.AlbumCoverView` serves them with a year-long immutable cache,
  which also removes a redirect per image
- Downloading doubles as verification, which is what makes the fallbacks work: art
  that will not download is rejected and the next candidate tried. Three
  fallbacks, each added because a real album needed it - the release group's own
  front cover; then any release in the group, earliest first (two groups return a
  *persistent* 500 at the group level while their releases serve art fine); then a
  MusicBrainz search by title and artist, for the one album whose Wikidata entity
  carries no P436. 500 of 500 albums have cover art
- Retry 5xx, not just 429/503. Treating a server error as a permanent miss cost 26
  of 499 albums their covers on the first run; retrying recovered 24 of them
- The Discogs client paces itself from `X-Discogs-Ratelimit` rather than a constant,
  since the limit differs between the anonymous and token tiers and the docs 403
  automated clients. The headroom factor must be **above** one: a first attempt
  spread requests at 0.8 of the window average, which is faster than the limit
  allows, and earned a run of 429s a few dozen requests in
- Artists are the **union** of the published credit and Wikidata P175, matched on a
  normalized name. Neither alone is right: P175 names the canonical act, which is
  sometimes coarser than the credit, so trusting it alone lost Paul McCartney
  'Band on the Run' and both credited artists 'Clube da Esquina'; the credit alone
  only guesses at whether a comma is a separator. Normalizing on punctuation, `&`
  and `the` is what keeps P175's "Bob Marley & The Wailers" from doubling the
  importer's "Bob Marley and the Wailers". `Album.artist_credit` is never touched
- Fix album covers being cropped to a portrait 90:128 box. The shared row CSS
  hardcoded box-art proportions with `object-fit: cover`; the aspect ratio and fit
  are now variables, and `media-thumb-whole` makes a sleeve square and `contain`,
  so the whole cover shows. Adds a `mobile_thumbnail` block to
  `core/includes/_base_media_row.html`, whose mobile image was outside any block
  and so could not be overridden at all - it also emitted a `src`-less `<img>` when
  an item had no cover
- **13 of the 15 genre icons were missing from the MDI subset**, so every genre badge
  would have rendered as a blank box the moment genres existed. The test meant to
  catch this built a set of icons that *were* present and then asserted only that
  the fallback was among them; it now asserts over the whole map and separately
  checks that `base.html` and `mdi-subset.css` agree on each codepoint
- Turn on the genre filter: it was fully wired server-side and hidden only because
  `MusicGenre` was empty. The control groups styles under their root with
  `<optgroup>`, since a flat list of 150 names is unusable. Also fixes
  `_cached_genre_options()` annotating `albums_count` without selecting it, which
  would have rendered every count blank
- Album detail gains Discogs, release date, label and Wikipedia rows; the API gains
  `thumbnail_url` (what to render) alongside `cover_image_url` (the remote URL, kept
  because an Open Graph scraper cannot reach a staff-gated local route)
- The admin registration test now derives its model list from the app config. The
  hand-kept list passed while four new models went unregistered, which is exactly
  when that is easiest to miss
- The `--musicbrainz` pass also fills genres for the three albums that have no
  Discogs master at all, through the same normalizer; MusicBrainz's community
  genre names only need title-casing to match the Discogs spellings, so
  "southern soul" joins the existing Soul root rather than creating a second
  lower-cased row. It never overwrites a genre Discogs supplied
- Truncate external text to its column width before saving. Nothing bounds the
  length of a title an external service returns - Fiona Apple's "When the
  Pawn..." is 444 characters and both Discogs and MusicBrainz return all of it -
  and **SQLite ignores varchar length while PostgreSQL raises `DataError`**, so a
  clean local run was followed by the Heroku run aborting at album 451 of 497.
  `metadata_service.fit()` now cuts every bounded field fed from an external
  source, and the tests assert the stored lengths directly rather than waiting
  for a database to object. Second time this divergence has bitten the project:
  the books list-type fixture below only persisted `"AT"` in a `varchar(1)`
  because SQLite allowed it
- **Books:** remove the `cache_page` decorator from all eight staff-only API
  endpoints. `cache_page` wraps `dispatch`, so it was consulted before DRF checked
  permissions - a staff response was stored and replayed to anonymous callers,
  defeating `IsStaffOrHide` entirely. `BookAllDataView` served the whole dataset
  that way, cached an hour. The same leak was removed from music before launch;
  books now has the regression test music already had
- **Books:** fix `_get_list_type_label` mapping `"AT"/"DEC"/"EOY"/"MISC"` against a
  `max_length=1` column that stores `A`/`D`/`E`/`M`. All four codes fell through to
  "Other", which was absent from the group ordering, so the list-appearances section
  rendered empty on every book page. Replaced with `core.constants.get_list_type_label`,
  which three other call sites already used correctly. Both tests covering it
  encoded the bug - one built its fixture with `type="AT"`, which only persists
  because SQLite ignores varchar length
- **Books:** guard `/api/books/meta/` against books with no `year_published`; a NULL
  decade raised `TypeError` and 500d the endpoint. Found by the new cache test.
  `games/api/views.py` has the same unguarded code, latent only because every game
  has a year

## 2026-10-17 (music vertical groundwork)

- Add a `music/` app: the third media vertical, staff-only and marked beta, carrying 500 ranked albums over 54 published source lists. `Album`, `Artist`, `MusicGenre`, `MusicPublication`, `MusicList` and `AlbumListMembership` subclass the `core` abstract bases; `Album` adds `artist_credit` (the credit exactly as published) alongside an `artists` M2M so the display text survives whatever the parser makes of it
- `music/services/import_handler.py` ingests the same three-TSV shape the games importer takes. The albums file substitutes an artist column for games' platforms and IGDB id; the positions file is byte-for-byte the same format, 0-indexed against the lists file. The two unranked lists (1001 Albums, Time's All-TIME 100) record every member at rank 1, matching the convention the games data already uses
- The music lists file has no type column, so `infer_list_type()` derives A/D/E/M from the title: decade and era wording is matched before all-time wording, or "The 100 Best Albums of the 1990s" would be swallowed by a looser all-time match. An unqualified title ("Top 100 Albums") falls back to all-time rather than end-of-year - every list in this corpus is retrospective. All 54 classify correctly: 13 all-time, 31 decade, 10 miscellaneous
- `split_artist_credit()` splits a credit on commas except for acts whose own name contains one, checked against the whole string first: `Neil Young, Crazy Horse` is two artists, `Crosby, Stills & Nash` is one. Nine distinct comma credits in the data, one exception needed; the later Wikidata pass (P175) can correct anything this misses
- Extract the staff gate to `core`: `StaffOnlyMixin` moves from `books/views.py` to `core/mixins.py` and `IsStaffOrHide` to `core/permissions.py`, both still 404 rather than 403 so an unlaunched section looks absent. Books imports them from core now
- Generalize the year/decade ranking into `core/services/ranking.py`: `update_year_decade_ranks(model, table, year_field)` keeps both the PostgreSQL window-function path and the SQLite chunked fallback, and `games.services.ranking_service` is a thin call-through. A row with no year now forms its own group on the Python path instead of raising, matching how PostgreSQL partitions NULLs
- Album rows extend `core/includes/_base_media_row.html`, which until now was referenced by nothing - `Book` lacks the `get_absolute_url`/`thumbnail`/`year` contract it renders, which is why the books rows are hand-maintained copies. `Album` satisfies it, so the shared template finally has a user, and `styles.css` gains the `.media-row` / `.media-card-mobile` / `.media-thumb-*` classes it emits. Albums have no cover art until the metadata pass, so a missing cover renders a placeholder rather than a broken image box
- Album slugs disambiguate by credit before falling back to a counter (`1999` is several different records)
- Music has **no entry point in the chrome**: no media-switcher tab, no sidebar or mobile-nav item, and it stays out of `sitemap.xml`. Staff reach it by URL. `core/includes/_media_switcher.html` and the two nav templates are therefore untouched, and there is no `MUSIC_ENABLED` flag - with nothing reading it, it would have been exactly the dead flag `BOOKS_ENABLED` is today (its setting is read by nothing; templates consult the raw env var instead). The staff gate is the single access mechanism; add a nav entry and a flag together when the section launches
- `music/tests/test_discoverability.py` pins that down: the games home, developer list and source-lists pages must contain no `/music/` link even for a staff user, the media switcher must offer no music tab, and the sitemap must not mention it - while staff can still reach every page by URL and everyone else gets 404
- Fix `scripts/build_mdi_subset.sh` subsetting the font in place: it fed the existing 117-glyph subset back into `pyftsubset`, so it could only ever drop glyphs and a newly referenced icon silently rendered as a blank box. It now subsets from the pinned upstream MDI v7.4.47 font, and uses `grep -ohE` instead of `rg`, which is not installed everywhere. Adds `mdi-album` and `mdi-music-note`; the font holds 119 glyphs and matches the declared codepoints exactly
- The music API is deliberately uncached. `cache_page` wraps `dispatch`, so it is consulted before permissions run - a response generated for a staff member was being replayed to anonymous callers, which defeats `IsStaffOrHide`. Confirmed by test, and the same pattern sits in `books/api/views.py` today
- Sort parameters declare their natural ascending form and `dir` flips only the primary field, so a tiebreaker keeps pointing the same way: albums by year descending is newest-first then best-ranked. Declaring a field pre-negated made `dir=desc` double-negate it
- No client-side filtering bundle: filtering is server-rendered with HTMX. The books IndexedDB stack is currently dead code - its `home.html` reads six context variables the view never sets and loads a bundle filename that does not exist on disk - so music gets working HTMX filtering now and the client-side renderer later, when there is something to optimize
- Add a staff import page at `/music/import/` (`MusicImportForm` + `MusicImportView`), for parity with the games importer: upload the three release files or tick "Use the bundled release files" to re-import the checked-in dev release. A partial upload is rejected rather than half-applied, since positions are meaningless against a different set of lists or albums, and the whole import is one transaction so a failure leaves the previous rankings in place. It runs inline rather than over SSE - 500 albums land in well under a second - and it is staff-gated, unlike `games.views.ImportView`, which is only login-gated and so lets any verified account replace the game rankings
- Remove the forum: django-machina and its `mptt`/`haystack`/`widget_tweaks` stack leave INSTALLED_APPS, middleware, template dirs, the attachments cache and `STATICFILES_DIRS`; `games/forum.py`, `acclaimedgames/forum_apps.py`, `setup_forum`, `scripts/scope_machina_css.py`, `templates/machina/` and `games/tests/test_forum.py` are gone, along with the two `Publication`/`User` forum signals and the nav links. Migrations 0104 and 0106 were edited to drop the `Publication.forum_topic` field and the `forum_conversation` dependency - 0106 removed that field again, so the net schema is unchanged and the graph no longer references an uninstalled app. `reputation_score` stays as editorial metadata with its forum wording dropped (migration 0114). migration 0115 then drops the 14 machina tables, their content types and permissions, the "Forum Moderators" group and machina's own `django_migrations` rows. It is irreversible and destroys every forum, topic and post - authorised deliberately. Tables go before content types so no foreign key can still point at them, and the migration records go last so a future machina reinstall would start clean rather than believing its migrations were applied. The drops are guarded by introspection and `IF EXISTS`, so the migration is a no-op on a fresh database
- Give each media section its own sidebar and mobile nav: `core/includes/_sidebar_nav.html` switches on `media_type`, so music shows Albums / Artists / Source Lists / Import Data (staff) and a "Back to Games" link, while the common bottom block - search, auth, donate, about, theme, social - stays shared. The games unified search is hidden on music pages, since it queries the games API and would return game results
- Bring the music pages into the site's existing visual idiom rather than inventing one: `/music/` now uses the games home's two-column skeleton (results left, 357px filter sidebar right, `mb-4 pb-3 border-b border-base-100` sections with accent icons); `/music/lists/` mirrors the games source-lists page (860px column, `h2#results-count`, horizontal filter bar, badge legend); `/music/artists/` mirrors the developer list (`table-minimal table-fixed`, top-album column, mobile cards). List-type badge colours now match the games page exactly (all-time info, decade success, misc warning, EOY error), the search box is shared via `core/includes/_search_box.html`, and `tr.developer-row`'s hover treatment is extended to `tr.entity-row` so the artist table reuses it instead of a third copy
- Fix a template comment leaking into the rendered music page as text - the same multi-line `{# #}` trap recorded on 2026-06-10. Django's lexer only strips single-line comments. Every music template is now audited for it, and a comment on the home page says why
- Page headings carry the filter state in the site's own wording ("Most Acclaimed Albums of the 1970s", "Albums matching ..."), avoiding "best"/"top" phrasing, with a test asserting that
- Deferred to the metadata session: `MusicBrainzAlbumData`/`WikipediaAlbumData`, cover art from the Cover Art Archive by release-group MBID, `MusicGenre` rows and the genre filter UI, and listened/want-to-listen tracking

## 2026-10-17 (metadata refresh streams)

- Fix the admin metadata refresh buttons failing in the browser: `GZipMiddleware` (added 2025-12-02) compressed the `text/event-stream` responses, and zlib holds its output, so every progress event - and every 15-second keepalive - stayed inside the compressor until the stream ended. Heroku's router saw no bytes for 55 seconds and dropped the connection, which the page reported as "Connection error"
- `EventStreamAwareGZipMiddleware` skips compression for `text/event-stream` and compresses everything else as before; the 2048-byte event padding that was added to force flushes is now actually reaching the client
- The import thread survives the dropped stream, so the Wikipedia and IGDB data usually did land despite the error toast - the browser just stopped hearing about it. Long refreshes are still better run as `heroku run:detached -- python manage.py refresh_all_metadata`
- Add a "Refresh All IGDB Data" button (`/import/igdb-progress/?force=true`) that re-fetches every game in place; previously the only way to update existing IGDB metadata from the admin was to clear it first and re-fetch
- The SSE Wikipedia path now stores the Wikidata-derived `hltb_id` (P2816), `steam_app_id` (P1733), and Wikiquote sitelink, matching `fetch_wikipedia_metadata`; games enriched through the button were missing the IDs that HLTB matching and quotes rely on
- Map the last three genres sitting under the "Other" fallback root: `dating sim` -> Life Simulation (Thirsty Suitors), `Word game` -> Puzzle (Wordle), and `Level editor and platformer` -> Platform (Super Mario Maker's infobox joins both halves into one link). Migration 0113 moves the existing links and metadata strings, then deletes the strays, leaving Other empty and out of the filter
- Fix "get() returned more than one WikipediaGameData" failing a game on every refresh (hit Resident Evil 2): an alternate Wikidata ID that resolves to the article a game already has created a second record with the same page title. `WikipediaGameData.upsert_for_game()` now collapses such duplicates into the primary record, and all seven Wikipedia save paths go through it

## 2026-10-14 (comma spacing)

- Fix stray spaces before commas in game row metadata (`BioWare , BioWare Edmonton`, `8 , DOS`): `{% if not forloop.last %}, {% endif %}` separators sat on their own indented line, so Django emitted the newline as rendered text
- Pull the developer, platform-family, and platform-code separators onto the preceding tag in the desktop and mobile row templates, and close the gap inside the platform-family badge; mobile's inner platform loop now uses the same `forloop.parentloop` form as desktop
- Spacing was previously inconsistent within a session: the client-side renderer already joined with `', '`, so rows lost the stray space whenever a filter re-rendered them

## 2026-09-30 (stray Other genres)

- Fix stray genres under the "Other" filter category (`and` on Super Mario Maker, `Clicker` on Universal Paperclips, `MMOFPS` on PlanetSide): unmapped Wikipedia infobox wording was passed through unchanged and filed under Other on each metadata refresh
- Map Clicker/Idle/Incremental variants to Puzzle and MMOFPS to First-Person Shooter; drop bare conjunctions ("and", "or", "&") in both the infobox scraper and the normalizer; retry unmapped "… game" / "… video game" names without the suffix
- Migration 0112 moves existing links and Wikipedia metadata to the canonical genres and deletes the strays; Other drops out of the filter once nothing under it has games

## 2026-09-30 (playtime mode)

- Fix game rows always showing main-story playtime: rows (list, mobile, grid; client- and server-rendered) now show 100% completion time when the Completion toggle is set to 100%, with a "(100%)" tooltip label
- Make the Main/100% toggle instant: rows carry both times and preset counts are computed for both modes, so switching swaps text in place with no re-filter, debounce, or server fetch (full re-filter only when a playtime range or playtime sort is active)

## 2026-06-18 (account fixes)

- Usernames held only by abandoned, never-verified accounts are now reclaimable: signup and profile rename treat such names as available and delete the dead account so a real user can claim it (staff/superuser and verified accounts are never touched)
- Fix admin "Bad Request (400)" when saving users with many tracked games: replace the per-game editable inlines on the User admin with read-only "Game Tracking" summaries so the change form no longer exceeds `DATA_UPLOAD_MAX_NUMBER_FIELDS`
- Confirm post-notification emails already go only to users who are both subscribed and email-verified (no change needed)

## 2026-06-10 (clean URLs)

- Client-side filtering now pushes clean SEO URLs (`/games/role-playing/`, `/games/1998/`) when the filter state matches a single SEO page; falls back to query params otherwise
- Back/forward navigation maps clean paths back to filter state; SEO routes eager-load the client filtering bundle
- Briefly trialed manufacturer-family pages (`/games/pc/` = Win+DOS+Linux+Mac etc.), then reverted to individual platform pages for every qualifying platform (migrations 0110/0111 net out to the original slugs)
- Fix Django template comments leaking into rendered page (multi-line `{# #}`)

## 2026-06-10 (SEO ranking pages)

- Add 94 crawlable SEO ranking pages: `/games/<genre|platform>/`, `/games/<year>/`, `/games/<decade>s/`, index at `/games/browse/`
- Pages serve the full interactive rankings page (HomePageView subclass injects path-implied filters into request.GET); titles reuse the natural `filter_title`
- Add unique meta descriptions, self-canonicals, and ItemList JSON-LD per page; sitemap-only discovery (deliberately no nav/footer/badge links)
- Add `Platform.slug` with SEO-friendly backfill (`pc`, `sega-genesis`, `snes`, ...)
- Extract `AnonymousResponseCacheMixin` from HomePageView; landing pages cached 1h for anonymous users
- Fix sitemap domain to canonical `www` host (Site record migration) and drop staff-only book pages that 404 for crawlers
- Fix double-space in generated filter titles

## 2026-06-10

- Remove public `/news/` page; route now returns 410 Gone so search engines deindex it (Posts kept for email notifications)
- Drop unused `PostSerializer` and `/news/` links in auth forms
- Add community forum at `/forum/` (django-machina) behind `FORUM_ENABLED` flag
- Site Feedback forum plus Publications forum with auto-maintained "Publication reputation scores" sticky topic (ranked table, syncs on Publication save/delete)
- Add `reputation_score` field to Publication (staff-edited in admin)
- Existing users can post automatically; staff auto-join Forum Moderators group; anonymous read access
- Render forum inside site chrome; scope machina's Bootstrap CSS under `#main-content` to protect DaisyUI sidebar/nav
- Replace machina search (broken on haystack simple backend) with working form/view
- Disable avatars until persistent file hosting exists; add Forum nav links with new `mdi-forum` icon

## 2026-03-11

- Fix played button (star icon) not appearing on "Load More" rows for logged-in users

## 2026-03-04

- Remove hardcoded YouTube API key fallback from source; require env-based key configuration
- Move Brevo SMTP username to `BREVO_SMTP_USER` environment variable in settings
- Document `BREVO_SMTP_USER` and `BREVO_SMTP_KEY` in `.env.example` for production setup

## 2026-02-21

- Reduce homepage main-thread cost by deferring Alpine/GA/CSF loading until explicit need/intent
- Remove timed fallback loaders and low-signal triggers from deferred script initialization
- Gate client-side filtering bundle load while preserving deep-link filter/highlight URL behavior
- Fix default list "Load More" rank display to keep all-time rows from showing filtered-rank parentheses
- Add reproducible MDI subset build script and regenerate icon font to a small codepoint subset
- Document MDI subset workflow in AGENTS and update `/icons` skill to require subset rebuild

## 2026-02-07

- Fix horizontal overflow on small phone screens (responsive logo + title sizing in hero section)
- Fix missing genre for What Remains of Edith Finch (map "Exploration" → "Walking Simulator")
- Add accent-insensitive search across all search functions (navbar, unified, client-side filters)
- Searching "Pokemon" now finds "Pokémon", "Ragnarok" finds "Ragnarök", etc.

## 2026-02-05

- Add rate limiting middleware (120 req/min, 1200 req/hr per IP) to protect against bot/crawler abuse
- Tune Gunicorn: 3 workers, 30s timeout, max-requests 1000 (prevents worker starvation from slow requests)
- Improve robots.txt: block aggressive crawlers, add crawl-delay, disallow expensive filtered queries
- Add DRF API throttling (60 req/min anonymous)

## 2026-02-03

- Add IGDB orphan reconnection during file import (matches Wikipedia/HLTB pattern)
- Prioritize games without metadata in refresh_all_metadata command
- Add streaming progress for batch file imports to prevent Gunicorn timeout
- Add defensive error handling to import page for database inconsistent states

## 2026-01-27

- Add donate button to mobile navigation (was missing, only existed in desktop sidebar)
- Fix rank distribution chart not restoring on bfcache back navigation
- Sync filter state from URL params on bfcache restore (prevents x-show mismatch after Alpine reinit)
- Add sortable Played and Want to Play count columns in User admin (annotated queryset, eliminates N+1 queries)

## 2026-01-26

- Fix year heatmap duplication on bfcache back navigation: use Alpine.destroyTree for proper x-for cleanup
- Add bfcache-restore listener to re-dispatch filter counts after component reinitialization
- Replace "Group by" toggle with auto-grouping: type filter selects flat year view, all types shows publication grouping

## 2026-01-25

- Fix jumpy scroll when navigating back to rankings with highlight: replace bfcache reload with Alpine.js reinitialization
- Skip scroll position restoration when highlight param present (let highlight scroll handle positioning)
- Add "Group by List Type" toggle to Source Lists page (All-time, Decade, Misc, EOY sections)
- Add Year and Alphabetical sort options for list type grouping
- Auto-switch sort direction when changing sort type (alpha→asc, year→desc)

## 2026-01-21

- Add Switch 2 (SW2) to platform family mappings for filter dropdown and game row display
- Fix orphaned "Party & Casual" genre: remap to "Party" under "Puzzle & Casual" hierarchy
- Add genre mappings for Beat'em up, Extraction shooter, Puzzle-adventure, Dystopian (consolidate to existing categories)
- Remove duplicate refresh_all_metadata_with_progress function (use management command directly)
- Update genre category icon: Party & Casual → Puzzle & Casual
- Fix source lists import varchar(100) error: increase List.name and Publication.name to 255 chars
- Add Heroku metadata refresh command to import page
- Fix played filter to use string instead of list (resolve filter title suffix issues)
- Update test expectations for sequential rank display (position 1, 2, 3...) vs global ranks
- Preserve platform year_start/year_end fields during imports (use get_or_create pattern)
- Create populate_platform_years command to restore year data for all 74 platforms
- Bump cache version to v11 to force global cache refresh after platform year population
- Fix Wikipedia metadata fetch to process all Wikidata IDs (enables HLTB lookup for multi-version games)
- Add title similarity validation to opensearch: reject false matches like "Sektori" → "Sektor Gaza"

## 2026-01-20

- Add support for multiple IGDB IDs and Wikidata IDs in import files (comma-separated, first is primary)
- Auto-reconnect orphaned metadata via alternate IDs when primary ID changes (HLTB fallback pattern)
- Clear and restore Wikipedia genres when Wikidata ID changes during import
- Normalize PlayedGame/WantToPlayGame igdb_id to primary when reconnecting via secondary ID
- Merge duplicate play tracking records when games are merged (keep earliest, delete duplicates)

## 2026-01-19

- Remove hardcoded 1000 game limit: dynamic scaling for rank distribution, Load More, and pagination
- Fix rank display: always show sequential position (1, 2, 3...) with global rank (#N) when sorted/filtered
- Fix Jump to Rank: load up to page boundary for smooth Load More continuation
- Clarify Delete Data button preserves user accounts and play tracking (update UI text, add regression test)

## 2026-01-18

- Fix profile modal showing stale played games count (add Cache-Control: no-store header)

## 2026-01-16

- Fix facet counts not updating when play status filters (Played/Want to Play/Untracked) are applied

## 2026-01-11

- Unify sort dropdown styling across pages: add min-w-20 text-left, use muted colors for direction buttons
- Add DaisyUI tooltips to list/grid view toggle buttons on games page

## 2026-01-10

- Fix untracked star icon shrinking to 80% after toggling (remove star-disappear animation from untracked state)
- Merge genre categories: Racing + Sports → "Racing & Sports", Puzzle + Party & Casual → "Puzzle & Casual"
- Consolidate 10 genre categories to 8, ensuring all have 5+ dropdown items
- Reorganize header: move logo from sidebar to desktop header next to site title
- Update brand assets: new logo-site.svg, favicon.ico, favicon PNGs (16/32/64), and og-image.png
- Move Sign Up and Donate buttons from header to sidebar bottom section
- Adjust header spacing and title sizing for better logo/text proportions
- Remove logo from sidebar and mobile navigation

## 2026-01-08

- Fix memory leaks: add guard to initYearPreview() and HTMX cleanup handler for developerFilter hashchange listener
- Fix genre hierarchy: move Maze/Platform/Metroidvania/Racing/Kart Racing to Action, Pinball to Party & Casual
- Fix genre mappings: Hack and Slash and Extreme Sports now separate genres (not mapped to Beat 'em Up/Snowboarding)
- Fix genre mappings: Exploration and Minigame now map to None (too vague for meaningful categorization)
- Add Puzzle Platformer as distinct genre under Puzzle (separate from action Platform)

## 2026-01-07

- Fix view mode flash: add inline script to set correct CSS before Alpine initializes (prevents list→grid flash on page load)
- Refactor List/Publication models to use abstract base classes in core (PublicationBase, ListBase, ListMembershipBase)
- Add independent BookPublication and BookList models to books app, removing games→books dependency
- Remove media_type field from games.List (books now have dedicated models)
- Fix visual regression tests: add StaffClientMixin for books staff access requirement

## 2026-01-06

- Refactor: extract shared cache helpers to core, add books/config.py mirroring games pattern
- Reorganize repo: move docs to docs/, archive old PRDs, add .env.example
- Add sort direction toggle (asc/desc) to developer list, game list, lists page, and developer detail filtered games
- Add hover effects to developer list rows (desktop table and mobile cards)
- Fix developer list href fallback: use span instead of href="#" for developers without slugs
- Fix developer list terminology: "studios" → "subsidiaries" to match table header
- Add publication search to source lists page with debounced HTMX filtering
- Polish source lists page: add subtitle, compact legend badges, hover transitions on cards
- Fix Alpine.js race condition: ensure utils-base.js loads before Alpine initializes to prevent "createUnifiedSearchData is not defined" errors
- Consolidate API paths: move search endpoints into app modules, fix /api/books/books/ double-path bug, add /api/developers/ and /api/genres/ aliases

## 2026-01-05

- Make source list page badges responsive to filters: counts update based on filtered set, sorting respects selected type
- Remove unused models: WikipediaCountry, WikipediaGameMode, IGDBGenre, and IGDBGameData.description field
- Remove GameQuote feature (model, services, management command, admin, tests)
- Fix test isolation bug: add cache.clear() to test setUp methods (home page caches full responses for anonymous users)
- Remove ProtonDB Steam Deck compatibility feature (low coverage, limited utility)
- Fix HLTB ID missing for games without English Wikipedia pages: fetch Wikidata metadata even when enwiki sitelink is absent, merge with Wikipedia page's Wikidata entry for union of all metadata (HLTB, Steam, game modes, countries)
- Fix accessibility: add aria-labels to played/tracking buttons for screen readers
- Fix contrast: increase unavailable year cell text opacity (/60→/70, hover /80→/90)
- Fix CLS: add explicit aspect-ratio to logo and game cover images to prevent layout shift
- Fix visual glitch: genre buttons in game rows no longer dim and pop-in during Alpine.js initialization
- Fix dark mode sidebar hover: use base-content text color for readability (was using dark primary color)
- Fix accessibility: year grid selected cells use white text, dark heatmap tiles get stronger text shadow for contrast
- Fix sidebar hover states: prevent DaisyUI from washing out active item colors, add accent color on non-active hover
- Fix accessibility: use grayscale instead of opacity for unavailable year cells (better text contrast)
- Fix accessibility: change game card h3 to span to fix heading order (no h2 before h3)
- Fix accessibility: year grid labels use theme-aware text color instead of white (better contrast on light backgrounds)
- Bump JS cache version to v=3 to fix stale filter-component.min.js being served from browser cache
- Fix LCP: add fetchpriority=high to hero logo images for faster initial render
- Use WebP format for large game cover images (detail page, grid view) for 15-20% size reduction; keep JPG for OG/social sharing compatibility
- Fix non-composited animations: convert background-color transitions to GPU-composited opacity on ::before pseudo-elements
- Fix accessibility: increase touch target sizes for mobile buttons (btn-xs → btn-sm with min-h-10)
- Fix accessibility: add aria-labels to mobile sort select, view toggle, and jump-to-rank buttons
- Fix accessibility: improve year grid heatmap contrast (increase text opacity /60→/70, strengthen cell label shadows)
- Fix accessibility: add aria-labels to sort dropdown and direction toggle buttons for screen readers
- Add page-level caching for anonymous home page requests (5-min cache reduces TTFB from ~1300ms to ~50ms)
- Fix accessibility: add aria-labels to genre filter expand/collapse buttons for screen readers
- Fix contrast issues: increase text opacity from /40 and /50 to /60 and /70 in filter panels
- Fix contrast issues: increase remaining /60 opacities to /70 across all templates and JS renderers
- Reduce TBT: remove deep watch on filters object, defer filter/year-grid init via requestIdleCallback
- Fix tooltip clipping: remove content-visibility containment from desktop game rows so tooltips can escape row bounds
- Fix 500 error on home page: remove reference to non-existent placeholder.webp from staticUrls
- Fix platform-icons.svg 404 in production: pass Django static URLs to JS via window.staticUrls
- Extract 90KB inline Alpine filter component to external JS file (52KB HTML reduction, enables caching)
- Optimize _calculateFacets(): consolidate 5 game loops into single pass (~60-70% faster facet calculation)
- Change htmx from async to defer to avoid main-thread blocking during critical rendering
- Add CSS containment (content-visibility: auto) for game rows to skip layout for off-screen elements
- Fix Load More bug: renderer property mismatch (currentGames → currentItems)
- Lazy-load client-side-filtering bundle via requestIdleCallback to reduce main-thread blocking (~47KB shifted to idle)
- Increase filter init retry limit to 3 seconds to accommodate lazy-loaded scripts
- Refactor Game model to inherit from MediaItemBase (Phase 9.1.1 complete)
- Add populate_mock_books management command for demo/testing data (30 books, 20 authors, 25 genres, 7 series)
- Add IndexedDB timeout to prevent infinite hangs on corrupted/blocked databases
- Fix IndexedDB timeout bug: reset _initPromise on failure so retries can succeed
- Fix IndexedDB upgrade hang: use new database name to avoid version upgrade path
- Fix missing Home button in sidebar when BOOKS_ENABLED is False
- Fix mobile nav home button icon consistency (gamepad → medal)

## 2026-01-04

- Refactor GameListRenderer to extend BaseMediaListRenderer (code reuse with BookListRenderer)
- Add books/ app skeleton with URL routing for multi-media platform expansion
- Add Open Library API client for book metadata (search, ISBN lookup, cover images)
- Add Hardcover GraphQL API client as optional secondary book metadata source
- Add fetch_book_metadata management command for book search and metadata retrieval
- Add core/ app with abstract models (MediaItemBase, CreatorBase) for multi-media platform foundation
- Move shared utilities to core: RobustPaginationMixin, HTMXPartialMixin, common template tags
- Fix sync_from_prod: include flatpages and sites, exclude user tracking models
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

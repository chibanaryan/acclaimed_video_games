"""
Configuration constants for the Acclaimed Games application.

Centralizes cache timeouts, IGDB settings, pagination defaults,
and other magic values that were previously scattered across the codebase.
"""

# =============================================================================
# Cache Timeouts (in seconds)
# =============================================================================

CACHE_TIMEOUT_1_HOUR = 60 * 60  # 3600 seconds
CACHE_TIMEOUT_24_HOURS = 60 * 60 * 24  # 86400 seconds
CACHE_TIMEOUT_DEFAULT = CACHE_TIMEOUT_24_HOURS

# Cache version - bump this to invalidate all caches after schema/data changes
CACHE_VERSION = "v6"

# =============================================================================
# Pagination Defaults
# =============================================================================

DEFAULT_PAGE_SIZE = 100
SEARCH_PAGE_SIZE = 100
POST_PAGE_SIZE = 5

# =============================================================================
# IGDB Configuration
# =============================================================================

# Genre themes that we treat as genres in our system.
# These are IGDB "themes" that match our curated genre list.
# Used by igdb.py to filter which themes to include as genres.
IGDB_GENRE_THEMES = [
    "4X (explore, expand, exploit, and exterminate)",
    "Action",
    "Horror",
    "Open world",
    "Party",
    "Sandbox",
    "Stealth",
    "Survival",
]

# API rate limiting (used by IgbdApi class)
IGDB_FREE_TIER_RATE_LIMIT = (
    3.8  # requests per second (4 req/s limit, use 3.8 for safety)
)
IGDB_PRO_TIER_RATE_LIMIT = 2500  # requests per second (3000 req/s limit)
IGDB_FREE_TIER_BATCH_SIZE = 50
IGDB_PRO_TIER_BATCH_SIZE = 500

# LRU cache sizes for IGDB API client
IGDB_COMPANY_CACHE_MAX_SIZE = 1000
IGDB_GAME_CACHE_MAX_SIZE = 1000
IGDB_GENRE_CACHE_MAX_SIZE = 500
IGDB_SERIES_CACHE_MAX_SIZE = 500

# =============================================================================
# Import Settings
# =============================================================================

# Batch size for bulk database operations during imports
IMPORT_BATCH_SIZE = 1000

# Progress reporting intervals
IMPORT_PROGRESS_INTERVAL_LISTS = 5
IMPORT_PROGRESS_INTERVAL_GAMES = 10
IMPORT_PROGRESS_INTERVAL_MEMBERSHIPS = 50
IMPORT_PROGRESS_INTERVAL_PLATFORMS = 10

# =============================================================================
# Year/Decade Defaults
# =============================================================================

DEFAULT_MIN_YEAR = 1970

# =============================================================================
# Wikipedia/Wikidata Configuration
# =============================================================================

# API endpoints
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"

# Rate limiting - Wikimedia requires minimum 1 second between requests
WIKI_REQUEST_DELAY = 1.0  # seconds between requests

# User agent (required by Wikimedia API policy)
WIKI_USER_AGENT = (
    "AcclaimedGamesBot/1.0 "
    "(https://www.acclaimedvideogames.com/; contact@acclaimedvideogames.com)"
)

# Wikidata property IDs
WIKIDATA_GENRE_PROPERTY = "P136"

# Wikipedia page lookup source tracking
WIKI_LOOKUP_SOURCE_WIKIDATA = "wikidata"
WIKI_LOOKUP_SOURCE_OPENSEARCH_YEAR = "opensearch_year"
WIKI_LOOKUP_SOURCE_OPENSEARCH_BASIC = "opensearch_basic"
WIKI_LOOKUP_SOURCE_OPENSEARCH_FALLBACK = "opensearch_fallback"

# Wikidata API rate limiting
# Authenticated: 5000 req/hr (~1.39 req/sec)
# Unauthenticated: 500 req/hr (~0.14 req/sec)
WIKIDATA_AUTHENTICATED_DELAY = 0.75  # seconds (safely under 1.39 req/sec limit)
WIKIDATA_UNAUTHENTICATED_DELAY = 2.0  # seconds (safely under 0.14 req/sec limit)

# Wikidata Game Mode (P404) Q-ID to label mapping
# Reference: https://www.wikidata.org/wiki/Property:P404
WIKIDATA_GAME_MODE_MAPPING = {
    "Q208850": "Single-player",
    "Q1628022": "Multiplayer",
    "Q1758804": "Cooperative",
    "Q6895044": "MMO",
    "Q3297989": "Online multiplayer",
    "Q61005756": "Split-screen",
    "Q2668023": "Hotseat",
}

# Wikidata Country (P495) Q-ID to label mapping
# Reference: https://www.wikidata.org/wiki/Property:P495
WIKIDATA_COUNTRY_MAPPING = {
    "Q30": "USA",
    "Q17": "Japan",
    "Q145": "UK",
    "Q142": "France",
    "Q183": "Germany",
    "Q16": "Canada",
    "Q408": "Australia",
    "Q38": "Italy",
    "Q29": "Spain",
    "Q159": "Russia",
    "Q148": "China",
    "Q884": "South Korea",
    "Q34": "Sweden",
    "Q36": "Poland",
    "Q55": "Netherlands",
    "Q39": "Switzerland",
    "Q40": "Austria",
    "Q35": "Denmark",
    "Q33": "Finland",
    "Q20": "Norway",
    "Q45": "Portugal",
    "Q214": "Ukraine",
    "Q213": "Czech Republic",
    "Q801": "Israel",
    "Q664": "New Zealand",
    "Q928": "Philippines",
    "Q334": "Singapore",
    "Q668": "India",
    "Q155": "Brazil",
    "Q96": "Mexico",
    "Q414": "Argentina",
}

# =============================================================================
# Wikiquote Configuration
# =============================================================================

# API endpoints
WIKIQUOTE_API_URL = "https://en.wikiquote.org/w/api.php"

# Quote validation
MIN_QUOTE_LENGTH = 10
MAX_QUOTE_LENGTH = 200

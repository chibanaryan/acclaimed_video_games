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

"""
Wikipedia genre scraping service.

Scrapes ordered genre lists from Wikipedia infoboxes.
Wikipedia infoboxes list genres by importance (editorial consensus).
Captures all genres while preserving their order so Primary Genre (index 0)
can be distinguished from Secondary Genres (index 1+).
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from games import config

logger = logging.getLogger(__name__)


class GenreSource(Enum):
    """Source of detected genre."""

    WIKIPEDIA = "Wikipedia"
    FAILED = "Failed"


@dataclass
class GenreResult:
    """Result of genre detection for a single game."""

    game_name: str
    source: GenreSource
    primary_genre: Optional[str] = None
    all_genres: List[str] = field(default_factory=list)
    source_url: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def all_genres_str(self) -> str:
        """Return all genres as pipe-separated string for CSV."""
        return " | ".join(self.all_genres) if self.all_genres else ""

    # Backwards compatibility
    @property
    def genre(self) -> Optional[str]:
        """Alias for primary_genre (backwards compatibility)."""
        return self.primary_genre

    @property
    def wikidata_id(self) -> Optional[str]:
        """Backwards compatibility - no longer used."""
        return None


class WikiGenreService:
    """
    Service for scraping video game genres from Wikipedia infoboxes.

    Uses a two-step approach:
    1. Use opensearch API to find the correct Wikipedia article URL
    2. Scrape the infobox to extract ordered genre list
    """

    def __init__(
        self,
        delay: float = config.WIKI_REQUEST_DELAY,
        user_agent: str = config.WIKI_USER_AGENT,
        progress_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialize the Wikipedia genre service.

        Args:
            delay: Delay between requests in seconds (default: 1.0)
            user_agent: User-Agent header for Wikimedia API compliance
            progress_callback: Optional callback for progress updates
        """
        self.delay = delay
        self.user_agent = user_agent
        self.progress_callback = progress_callback
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self.last_request_time: float = 0.0

    def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _make_request(
        self, url: str, params: Optional[Dict] = None
    ) -> Optional[requests.Response]:
        """
        Make rate-limited request with error handling.

        Args:
            url: URL to fetch
            params: Optional query parameters

        Returns:
            Response object, or None on error
        """
        self._wait_for_rate_limit()
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.warning("Request failed: %s", e)
            return None

    def _get_name_variants(self, game_name: str) -> List[str]:
        """
        Get name variants to try for games with multiple names.

        Handles cases like:
        - "Game A / Game B" -> ["Game A", "Game B"]
        - "Game A: Subtitle / Alternate: Name" -> each variant tried
        - "Pokémon Red/Blue/Yellow" -> ["Pokémon Red and Blue", "Pokémon Red", ...]
        - "Maniac Mansion II: Day of the Tentacle" -> [..., "Day of the Tentacle"]

        Args:
            game_name: Original game name, possibly with "/" separator

        Returns:
            List of name variants to try (original first if no "/")
        """
        variants = []
        seen = set()

        def add_variant(v):
            if v and v not in seen:
                seen.add(v)
                variants.append(v)

        # Check for both " / " (spaced) and "/" (unspaced) separators
        if " / " in game_name:
            parts = [p.strip() for p in game_name.split(" / ")]
            is_spaced = True
        elif "/" in game_name:
            parts = [p.strip() for p in game_name.split("/")]
            is_spaced = False
        else:
            # No slash - start with original name
            add_variant(game_name)

            # Extract subtitle if present (handles Wikipedia pages using subtitle)
            # e.g., "Maniac Mansion II: Day of the Tentacle" -> "Day of the Tentacle"
            if ": " in game_name:
                subtitle = game_name.split(": ", 1)[1]
                if len(subtitle) >= 5:  # Only if subtitle is meaningful
                    add_variant(subtitle)

            return variants

        # For unspaced "/" like "Pokémon Red/Blue/Yellow", try combining
        # first two parts with "and" (common Wikipedia naming convention)
        if not is_spaced and len(parts) >= 2:
            combined = f"{parts[0]} and {parts[1]}"
            add_variant(combined)

        # Add each part, but skip very short parts (< 5 chars) that aren't
        # the first part, as they may match wrong pages (e.g., "Blue" -> color)
        for i, part in enumerate(parts):
            if i == 0 or len(part) >= 5:
                add_variant(part)
                # Also extract subtitles from each part
                if ": " in part:
                    subtitle = part.split(": ", 1)[1]
                    if len(subtitle) >= 5:
                        add_variant(subtitle)

        return variants if variants else [game_name]

    def _search_wikipedia(
        self, game_name: str, year: Optional[int] = None
    ) -> Optional[str]:
        """
        Search Wikipedia using opensearch API to find the correct article URL.

        Tries multiple search variants to handle disambiguation:
        1. "{game_name} ({year} video game)" - if year provided (best for remakes)
        2. "{game_name} ({year} game)" - if year provided
        3. "{game_name} (video game)"
        4. "{game_name} (game)"
        5. "{game_name}" (bare name)
        6. Fallback: first result if it's a video game page (for different titles)

        For games with "/" in name, tries each part separately.

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            Wikipedia article URL or None if not found
        """
        # Get name variants (handles "/" separated names)
        name_variants = self._get_name_variants(game_name)

        # First pass: strict matching
        for name in name_variants:
            url = self._search_single_name(name, year, strict=True)
            if url:
                return url

        # Second pass: fallback to first video game result (for different titles)
        # E.g., "Maniac Mansion II: Day of the Tentacle" -> "Day of the Tentacle"
        for name in name_variants:
            url = self._search_single_name(name, year, strict=False)
            if url:
                logger.debug("Using fallback match for '%s': %s", game_name, url)
                return url

        return None

    def _search_single_name(
        self, game_name: str, year: Optional[int] = None, strict: bool = True
    ) -> Optional[str]:
        """
        Search Wikipedia for a single game name variant.

        Args:
            game_name: Name of the video game (single name, not "/" separated)
            year: Optional year of release for disambiguation
            strict: If True, validate result matches search name.
                    If False, accept first video game result (for different titles).

        Returns:
            Wikipedia article URL or None if not found
        """
        search_variants = []

        # Try year-based variants FIRST for disambiguation (common Wikipedia pattern)
        if year:
            search_variants.extend(
                [
                    f"{game_name} ({year} video game)",
                    f"{game_name} ({year} game)",
                ]
            )

        # Then try generic variants
        search_variants.extend(
            [
                f"{game_name} (video game)",
                f"{game_name} (game)",
                game_name,
            ]
        )

        for search_term in search_variants:
            params = {
                "action": "opensearch",
                "search": search_term,
                "limit": "1",
                "namespace": "0",
                "format": "json",
            }

            response = self._make_request(config.WIKIPEDIA_API_URL, params)
            if not response:
                continue

            try:
                data = response.json()
                # opensearch returns: [search_term, [titles], [descriptions], [urls]]
                if len(data) >= 4 and data[3]:
                    url = data[3][0]
                    title = data[1][0] if data[1] else ""

                    # Check if it's a disambiguation page
                    if "disambiguation" in title.lower():
                        logger.debug(
                            "Skipping disambiguation page for '%s'", search_term
                        )
                        continue

                    if strict:
                        # Validate result matches search term to prevent
                        # wrong pages like "Resident_Evil" for "Resident Evil 4"
                        if not self._is_valid_search_result(game_name, title):
                            logger.debug(
                                "Skipping mismatched result: searched '%s', got '%s'",
                                game_name,
                                title,
                            )
                            continue
                    else:
                        # Non-strict mode: verify it's actually a video game page
                        # by checking if it has a video game infobox
                        if not self._is_video_game_page(url):
                            logger.debug(
                                "Skipping non-game page for '%s': %s", game_name, title
                            )
                            continue

                    return url
            except (ValueError, IndexError, KeyError) as e:
                logger.warning("Failed to parse opensearch response: %s", e)
                continue

        return None

    def _is_video_game_page(self, url: str) -> bool:
        """
        Check if a Wikipedia page is a video game page.

        Verifies by checking if the page has a video game infobox with a genre row.
        This is used in non-strict mode to accept pages with different titles
        (e.g., "Day of the Tentacle" for "Maniac Mansion II: Day of the Tentacle").

        Args:
            url: Wikipedia article URL

        Returns:
            True if the page appears to be a video game page
        """
        response = self._make_request(url)
        if not response:
            return False

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for video game infobox
        infobox = soup.find("table", class_="infobox")
        if not infobox:
            infobox = soup.find("table", class_=re.compile(r"infobox"))
        if not infobox:
            return False

        # Check if it has a Genre row (strong indicator of video game page)
        for row in infobox.find_all("tr"):
            header = row.find("th")
            if header and "genre" in header.get_text().lower():
                return True

        # Also check for other video game indicators
        for row in infobox.find_all("tr"):
            header = row.find("th")
            if header:
                header_text = header.get_text().lower()
                # Common video game infobox rows
                if any(
                    indicator in header_text
                    for indicator in ["developer", "publisher", "platform", "release"]
                ):
                    return True

        return False

    def _is_valid_search_result(self, searched_name: str, result_title: str) -> bool:
        """
        Validate that a Wikipedia search result matches what we searched for.

        This prevents cases like:
        - Searching "Resident Evil 4" and getting "Resident Evil (video game)"
        - Searching "Final Fantasy VII" and getting "Final Fantasy VII Materia"

        Args:
            searched_name: The game name we searched for
            result_title: The Wikipedia article title returned

        Returns:
            True if the result appears to match our search
        """
        # Normalize both strings for comparison
        searched_lower = searched_name.lower()
        result_lower = result_title.lower()

        # Remove common suffixes from result for comparison
        for suffix in [" (video game)", " (game)", " (series)"]:
            if result_lower.endswith(suffix):
                result_lower = result_lower[: -len(suffix)]
                break

        # Also handle year suffixes like "(1993 video game)"
        result_lower = re.sub(r"\s*\(\d{4}\s*(video\s*)?game\)$", "", result_lower)

        # Exact match after removing suffixes
        if searched_lower == result_lower:
            return True

        # Result starts with search name - only valid if followed by
        # a roman numeral, number, colon, or nothing (not random words)
        # This allows "Doom" to match "Doom II" but not "Doom Eternal" for "Doom"
        if result_lower.startswith(searched_lower):
            remainder = result_lower[len(searched_lower) :].strip()
            # OK if nothing after, or starts with :, or is a roman numeral/number
            if not remainder:
                return True
            if remainder.startswith(":"):
                return True
            # Check for roman numerals or numbers (sequels)
            if re.match(
                r"^[ivxlcdm]+$|^\d+$", remainder.split()[0] if remainder.split() else ""
            ):
                return True
            # Otherwise reject - has extra words like "Materia", "Eternal", etc.
            return False

        # Search name ends with a number - result should contain that number
        # This prevents "Resident Evil 4" matching "Resident Evil"
        match = re.search(r"\d+$", searched_lower)
        if match:
            number = match.group()
            if number not in result_lower:
                return False

        return False

    def _clean_genre_text(self, text: str) -> str:
        """
        Clean genre text by removing reference markers and extra whitespace.

        Args:
            text: Raw genre text from Wikipedia

        Returns:
            Cleaned genre text
        """
        # Remove reference markers like [1], [a], [note 1], [citation needed]
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[[a-z]\]", "", text)
        text = re.sub(r"\[note\s*\d+\]", "", text)
        text = re.sub(r"\[citation needed\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[.*?\]", "", text)  # Catch-all for remaining brackets

        # Clean up whitespace
        text = text.strip()

        return text

    def _scrape_infobox_genres(self, url: str) -> List[str]:
        """
        Scrape genre list from Wikipedia infobox.

        Uses get_text(separator="|") to convert all visual breaks
        (commas, <br>, <li>) into a standard delimiter.

        Args:
            url: Wikipedia article URL

        Returns:
            Ordered list of genres (empty list if not found)
        """
        response = self._make_request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Find infobox table
        infobox = soup.find("table", class_="infobox")
        if not infobox:
            # Try alternative infobox classes
            infobox = soup.find("table", class_=re.compile(r"infobox"))
        if not infobox:
            logger.debug("No infobox found at %s", url)
            return []

        # Find Genre row
        for row in infobox.find_all("tr"):
            header = row.find("th")
            if header and "genre" in header.get_text().lower():
                data_cell = row.find("td")
                if not data_cell:
                    continue

                # Remove <sup> tags (reference markers) before extraction
                for sup in data_cell.find_all("sup"):
                    sup.decompose()

                # Remove hidden content
                for hidden in data_cell.find_all(class_="reference"):
                    hidden.decompose()
                for hidden in data_cell.find_all(style=re.compile(r"display:\s*none")):
                    hidden.decompose()

                # Check for <li> tags first (bulleted list)
                list_items = data_cell.find_all("li")
                if list_items:
                    genres = []
                    for li in list_items:
                        text = self._clean_genre_text(li.get_text(strip=True))
                        if text:
                            genres.append(text)
                    if genres:
                        return genres

                # Use get_text with pipe separator to catch all breaks
                # This handles commas, <br>, and other separators
                raw_text = data_cell.get_text(separator="|", strip=True)
                raw_text = self._clean_genre_text(raw_text)

                # Split by pipe or comma
                if "|" in raw_text:
                    parts = raw_text.split("|")
                else:
                    parts = raw_text.split(",")

                # Clean each part - strip whitespace and leading/trailing commas
                genres = []
                for part in parts:
                    cleaned = part.strip().strip(",").strip()
                    # Skip empty or very short parts (likely artifacts)
                    if cleaned and len(cleaned) > 1:
                        genres.append(cleaned)

                return genres

        logger.debug("No genre row found in infobox at %s", url)
        return []

    def get_genre(self, game_name: str, year: Optional[int] = None) -> GenreResult:
        """
        Get ordered genre list for a game from Wikipedia.

        1. Search Wikipedia for the game page (with year fallback)
        2. Scrape the infobox for genres
        3. If no genres found and year was used, retry without year

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            GenreResult with ordered genre list
        """
        # Step 1: Search Wikipedia (with year-based fallback)
        url = self._search_wikipedia(game_name, year)

        if not url:
            return GenreResult(
                game_name=game_name,
                source=GenreSource.FAILED,
                error_message="Page not found on Wikipedia",
            )

        # Step 2: Scrape infobox genres
        genres = self._scrape_infobox_genres(url)

        # Step 3: If no genres found and year was used, try without year
        # This handles cases like "Tetris (1989 video game)" which exists
        # but has no genre, while "Tetris (video game)" has the genre
        if not genres and year:
            logger.debug(
                "No genre on year-specific page for '%s', trying main page",
                game_name,
            )
            main_url = self._search_wikipedia(game_name, year=None)
            if main_url and main_url != url:
                genres = self._scrape_infobox_genres(main_url)
                if genres:
                    url = main_url  # Use the page that had genres

        if not genres:
            return GenreResult(
                game_name=game_name,
                source=GenreSource.FAILED,
                source_url=url,
                error_message="No genre found in Wikipedia infobox",
            )

        return GenreResult(
            game_name=game_name,
            source=GenreSource.WIKIPEDIA,
            primary_genre=genres[0],
            all_genres=genres,
            source_url=url,
        )

    def process_games(
        self, game_names: List[str]
    ) -> tuple[List[GenreResult], int, int]:
        """
        Process multiple games and return results.

        Args:
            game_names: List of game names to process

        Returns:
            Tuple of (results list, success count, failure count)
        """
        results = []
        success_count = 0
        failure_count = 0
        total = len(game_names)

        self._notify_progress("start", {"total": total})

        for idx, game_name in enumerate(game_names, start=1):
            result = self.get_genre(game_name)
            results.append(result)

            if result.source != GenreSource.FAILED:
                success_count += 1
                self._notify_progress(
                    "progress",
                    {
                        "current": idx,
                        "total": total,
                        "game_name": game_name,
                        "genre": result.primary_genre,
                        "source": result.source.value,
                    },
                )
            else:
                failure_count += 1
                self._notify_progress(
                    "error",
                    {
                        "current": idx,
                        "total": total,
                        "game_name": game_name,
                        "message": result.error_message,
                    },
                )

        self._notify_progress(
            "complete",
            {
                "total": total,
                "success": success_count,
                "failures": failure_count,
            },
        )

        return (results, success_count, failure_count)

    def _notify_progress(self, event_type: str, data: Dict) -> None:
        """Call progress callback if provided."""
        if self.progress_callback:
            self.progress_callback(event_type, data)

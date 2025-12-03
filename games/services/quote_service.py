"""
Wikiquote quote scraping service.

Fetches video game quotes from Wikiquote pages.
Extracts character dialogue and iconic quotes from game pages.
"""

import json
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


class QuoteSource(Enum):
    """Source of detected quotes."""

    WIKIQUOTE = "Wikiquote"
    FAILED = "Failed"


@dataclass
class QuoteResult:
    """Result of quote extraction for a single game."""

    game_name: str
    source: QuoteSource
    quotes: List[Dict[str, str]] = field(default_factory=list)
    source_url: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def quotes_json(self) -> str:
        """Return quotes as JSON string for CSV export."""
        return json.dumps(self.quotes) if self.quotes else ""


class QuoteService:
    """
    Service for fetching video game quotes from Wikiquote.

    Uses a two-step approach:
    1. Use opensearch API to find the correct Wikiquote article URL
    2. Parse the page to extract quote list items and attributions
    """

    def __init__(
        self,
        delay: float = config.WIKI_REQUEST_DELAY,
        user_agent: str = config.WIKI_USER_AGENT,
        progress_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialize the Wikiquote service.

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
        - "Pokémon Red/Blue" -> ["Pokémon Red and Blue", "Pokémon Red"]

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

            # Extract subtitle if present
            if ": " in game_name:
                subtitle = game_name.split(": ", 1)[1]
                if len(subtitle) >= 5:
                    add_variant(subtitle)

            return variants

        # For unspaced "/" like "Pokémon Red/Blue", try combining
        # first two parts with "and" (common Wikiquote naming convention)
        if not is_spaced and len(parts) >= 2:
            combined = f"{parts[0]} and {parts[1]}"
            add_variant(combined)

        # Add each part
        for i, part in enumerate(parts):
            if i == 0 or len(part) >= 5:
                add_variant(part)
                if ": " in part:
                    subtitle = part.split(": ", 1)[1]
                    if len(subtitle) >= 5:
                        add_variant(subtitle)

        return variants if variants else [game_name]

    def _search_wikiquote(
        self, game_name: str, year: Optional[int] = None
    ) -> Optional[str]:
        """
        Search Wikiquote using opensearch API to find the correct article URL.

        Tries multiple search variants to handle disambiguation:
        1. "{game_name} ({year} video game)" - if year provided
        2. "{game_name} ({year} game)" - if year provided
        3. "{game_name} (video game)"
        4. "{game_name} (game)"
        5. "{game_name}" (bare name)

        For games with "/" in name, tries each part separately.

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            Wikiquote article URL or None if not found
        """
        # Get name variants (handles "/" separated names)
        name_variants = self._get_name_variants(game_name)

        # Try each name variant
        for name in name_variants:
            url = self._search_single_name(name, year)
            if url:
                return url

        return None

    def _search_single_name(
        self, game_name: str, year: Optional[int] = None
    ) -> Optional[str]:
        """
        Search Wikiquote for a single game name variant.

        Args:
            game_name: Name of the video game (single name, not "/" separated)
            year: Optional year of release for disambiguation

        Returns:
            Wikiquote article URL or None if not found
        """
        search_variants = []

        # Try year-based variants first for disambiguation
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

            response = self._make_request(config.WIKIQUOTE_API_URL, params)
            if not response:
                continue

            try:
                data = response.json()
                # opensearch returns: [search_term, [titles], [descriptions], [urls]]
                if len(data) >= 4 and data[3]:
                    url = data[3][0]
                    title = data[1][0] if data[1] else ""

                    # Skip disambiguation pages
                    if "disambiguation" in title.lower():
                        logger.debug(
                            "Skipping disambiguation page for '%s'", search_term
                        )
                        continue

                    return url
            except (ValueError, IndexError, KeyError) as e:
                logger.warning("Failed to parse opensearch response: %s", e)
                continue

        return None

    def _clean_quote_text(self, text: str) -> str:
        """
        Clean quote text by removing reference markers and extra whitespace.

        Args:
            text: Raw quote text from Wikiquote

        Returns:
            Cleaned quote text
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

    def _is_valid_quote(self, text: str) -> bool:
        """
        Validate that text is a proper quote.

        Args:
            text: Cleaned quote text

        Returns:
            True if valid quote
        """
        # Check length
        if len(text) < config.MIN_QUOTE_LENGTH or len(text) > config.MAX_QUOTE_LENGTH:
            return False

        # Check for meaningful content (not just punctuation/symbols)
        if not re.search(r"[a-zA-Z]", text):
            return False

        # Check for common non-quote patterns
        if text in ["...", "!!!!", "????"]:
            return False

        return True

    def _parse_wikiquote_page(self, url: str) -> List[Dict[str, str]]:
        """
        Parse quotes from Wikiquote page.

        Extracts quotes from list items (<li> tags) within the page.
        Attempts to determine attribution from section headers.

        Args:
            url: Wikiquote article URL

        Returns:
            List of dicts with {"text": quote, "attribution": source}
        """
        response = self._make_request(url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        quotes = []
        current_attribution = "In-game dialogue"
        skip_until_next_section = False

        # Find main content area
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            logger.debug("No content found at %s", url)
            return []

        # Iterate through elements to track sections and quotes
        for element in content.find_all(["h2", "h3", "h4", "ul"]):
            # Update attribution when we hit a section header
            if element.name in ["h2", "h3", "h4"]:
                header_text = element.get_text(strip=True)

                # Extract clean section name (remove [edit] links and numbers)
                header_text = re.sub(r"\[edit\]", "", header_text, flags=re.IGNORECASE)
                header_text = header_text.strip()

                # Skip certain sections
                skip_sections = [
                    "external links",
                    "references",
                    "see also",
                    "notes",
                    "about",
                    "cast",
                ]
                if any(skip.lower() in header_text.lower() for skip in skip_sections):
                    skip_until_next_section = True
                    continue
                else:
                    skip_until_next_section = False

                # Use section as attribution if it looks like a character/level name
                if header_text and len(header_text) < 100:
                    current_attribution = header_text

            # Extract quotes from list items
            elif element.name == "ul":
                # Skip if we're in a skipped section
                if skip_until_next_section:
                    continue

                for li in element.find_all("li", recursive=False):
                    # Remove <sup> tags (reference markers)
                    for sup in li.find_all("sup"):
                        sup.decompose()

                    # Get text with space separator to prevent word concatenation
                    text = li.get_text(separator=" ", strip=True)
                    text = self._clean_quote_text(text)

                    # Validate
                    if not self._is_valid_quote(text):
                        continue

                    quotes.append(
                        {
                            "text": text,
                            "attribution": current_attribution,
                        }
                    )

        return quotes

    def get_quotes(self, game_name: str, year: Optional[int] = None) -> QuoteResult:
        """
        Get quotes for a game from Wikiquote.

        1. Search Wikiquote for the game page
        2. Parse the page to extract quotes

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            QuoteResult with quotes list
        """
        # Step 1: Search Wikiquote
        url = self._search_wikiquote(game_name, year)

        if not url:
            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.FAILED,
                error_message="Page not found on Wikiquote",
            )

        # Step 2: Parse quotes
        quotes = self._parse_wikiquote_page(url)

        if not quotes:
            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.FAILED,
                source_url=url,
                error_message="No quotes found on Wikiquote page",
            )

        return QuoteResult(
            game_name=game_name,
            source=QuoteSource.WIKIQUOTE,
            quotes=quotes,
            source_url=url,
        )

    def _notify_progress(self, event_type: str, data: Dict) -> None:
        """Call progress callback if provided."""
        if self.progress_callback:
            self.progress_callback(event_type, data)

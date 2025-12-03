"""
LLM-powered quote service with web search verification.

Uses Claude with web search to find verified game quotes from multiple sources.
Falls back to Wikiquote service when appropriate.
"""

import json
import logging
import os
from typing import Dict, List, Optional

import anthropic
import requests

from games.services.quote_service import QuoteResult, QuoteService, QuoteSource

logger = logging.getLogger(__name__)


class LLMQuoteService:
    """
    Service for fetching video game quotes using Claude with web search.

    Uses Claude API with search capabilities to find verified quotes from:
    - Wikiquote
    - Gaming wikis (Fandom, etc.)
    - Official game websites
    - Review sites with quotes

    Prioritizes accuracy and source verification over quantity.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        fallback_to_wikiquote: bool = True,
    ):
        """
        Initialize the LLM quote service.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Claude model to use
            fallback_to_wikiquote: Whether to fall back to Wikiquote service
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable must be set "
                "or api_key parameter provided"
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model
        self.fallback_to_wikiquote = fallback_to_wikiquote
        self.wikiquote_service = QuoteService() if fallback_to_wikiquote else None

    def _search_web(self, query: str) -> List[Dict[str, str]]:
        """
        Search the web for quotes using Brave Search API.

        Args:
            query: Search query

        Returns:
            List of search results with title, url, description
        """
        # Using Brave Search API (free tier available)
        api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
        if not api_key:
            logger.warning("BRAVE_SEARCH_API_KEY not set, skipping web search")
            return []

        try:
            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"X-Subscription-Token": api_key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for result in data.get("web", {}).get("results", []):
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "description": result.get("description", ""),
                    }
                )

            return results
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
            return []

    def _create_system_prompt(self) -> str:
        """Create the system prompt for Claude."""
        return """You are a video game quote curator. Your task is to find VERIFIED, AUTHENTIC quotes from video games.

CRITICAL RULES:
1. ONLY return quotes you can verify from reliable sources (Wikiquote, gaming wikis, official sources)
2. PRIORITIZE memorable, quippy, resonant, and iconic character dialogue
3. Each quote MUST have attribution (character name or 'In-game dialogue') - NO quotes without attribution
4. Each quote MUST have a source URL where you verified it
5. If you cannot find verified quotes, return an empty list - DO NOT make up quotes
6. Search multiple sources before accepting a quote as verified
7. Keep quotes under 200 characters
8. Clean up any grammar errors, typos, or formatting issues from source material
9. Reject: sound effects (AAAH!), incomplete sentences, meta-references (like "IGN said..."), reviewer commentary

QUOTE SELECTION CRITERIA (in order of priority):
1. Iconic/famous quotes that define the game or character
2. Emotionally resonant or dramatic moments
3. Witty, quippy, or humorous dialogue
4. Quotes that capture the game's theme or essence
5. Character-defining moments

QUOTE CLEANING:
- Fix typos and grammar errors
- Standardize punctuation
- Remove reference markers like [1], [a], [citation needed]
- Ensure proper capitalization
- Keep the quote's original meaning and voice

QUOTE VERIFICATION PROCESS:
1. Search for "[game name] quotes wikiquote"
2. Search for "[game name] character dialogue wiki"
3. Cross-reference quotes across multiple sources
4. Only include quotes you can cite with a source URL
5. Select the BEST 1-5 quotes (quality over quantity)

OUTPUT FORMAT (JSON):
{
    "quotes": [
        {
            "text": "The actual quote text (cleaned and grammar-corrected)",
            "attribution": "Character name (REQUIRED - never leave empty)",
            "source_url": "URL where you verified this quote"
        }
    ],
    "search_performed": true,
    "sources_checked": ["list of URLs you checked"]
}

If you cannot find ANY verified quotes, return:
{
    "quotes": [],
    "search_performed": true,
    "sources_checked": ["list of URLs you checked"],
    "reason": "Brief explanation of why no quotes were found"
}"""

    def get_quotes(self, game_name: str, year: Optional[int] = None) -> QuoteResult:
        """
        Get verified quotes for a game using Claude with web search.

        Args:
            game_name: Name of the video game
            year: Optional year of release for disambiguation

        Returns:
            QuoteResult with verified quotes and sources
        """
        # Try Wikiquote first if fallback is enabled
        if self.wikiquote_service:
            wikiquote_result = self.wikiquote_service.get_quotes(game_name, year)
            if (
                wikiquote_result.source == QuoteSource.WIKIQUOTE
                and wikiquote_result.quotes
            ):
                # Wikiquote found quotes - have LLM clean and select best ones
                logger.info(f"Cleaning Wikiquote quotes for {game_name} with LLM")
                return self._improve_wikiquote_quotes(game_name, wikiquote_result)

        # Wikiquote didn't find quotes, use LLM with web search
        logger.info(f"Using LLM web search for {game_name}")
        return self._search_and_extract_quotes(game_name, year)

    def _improve_wikiquote_quotes(
        self, game_name: str, wikiquote_result: QuoteResult
    ) -> QuoteResult:
        """
        Use LLM to clean up and select the best Wikiquote quotes.

        Args:
            game_name: Name of the game
            wikiquote_result: Original Wikiquote results

        Returns:
            Improved QuoteResult with cleaned quotes
        """
        quotes_text = "\n\n".join(
            [
                f'"{q["text"]}" - {q.get("attribution", "Unknown")}'
                for q in wikiquote_result.quotes[:20]  # Limit to first 20
            ]
        )

        user_prompt = f"""Here are quotes from Wikiquote for "{game_name}":

{quotes_text}

Your task:
1. Select the 3-5 BEST quotes (most memorable, quippy, or resonant)
2. Clean up grammar, typos, and formatting errors
3. Ensure all quotes have proper attribution
4. Remove sound effects, incomplete sentences, or junk
5. Keep quotes under 200 characters

Source URL: {wikiquote_result.source_url}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self._create_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )

            return self._parse_llm_response(response, game_name)

        except Exception as e:
            logger.error(f"LLM cleaning failed for {game_name}: {e}")
            # Return original Wikiquote results as fallback
            return wikiquote_result

    def _search_and_extract_quotes(
        self, game_name: str, year: Optional[int] = None
    ) -> QuoteResult:
        """
        Search web and extract quotes using LLM.

        Args:
            game_name: Name of the game
            year: Optional year

        Returns:
            QuoteResult with found quotes
        """
        year_context = f" ({year})" if year else ""

        # Perform web searches
        search_results = []
        queries = [
            f'"{game_name}" quotes wikiquote',
            f'"{game_name}" character dialogue',
            f'"{game_name}" famous quotes',
        ]

        for query in queries:
            results = self._search_web(query)
            search_results.extend(results)

        if not search_results:
            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.FAILED,
                error_message="No search results found",
            )

        # Format search results for LLM
        search_context = "\n\n".join(
            [
                f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['description']}"
                for r in search_results[:10]
            ]
        )

        user_prompt = f"""Find verified quotes for "{game_name}"{year_context}.

Here are search results to help you:

{search_context}

Based on these search results:
1. Identify quotes that appear on reliable sources (Wikiquote, gaming wikis)
2. Select 1-3 of the BEST quotes (most memorable/iconic)
3. Provide attribution for each
4. Include the source URL

Remember: Only return quotes you can verify from these search results. Quality over quantity."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self._create_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )

            return self._parse_llm_response(response, game_name)

        except Exception as e:
            logger.error(f"LLM search failed for {game_name}: {e}")
            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.FAILED,
                error_message=f"LLM search error: {str(e)}",
            )

    def _parse_llm_response(
        self, response: anthropic.types.Message, game_name: str
    ) -> QuoteResult:
        """
        Parse Claude's response and create QuoteResult.

        Args:
            response: Claude API response
            game_name: Name of the game

        Returns:
            QuoteResult with parsed quotes
        """
        try:
            response_text = response.content[0].text

            # Extract JSON from response (Claude might wrap it in markdown)
            if "```json" in response_text:
                json_start = response_text.index("```json") + 7
                json_end = response_text.index("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.index("```") + 3
                json_end = response_text.index("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            data = json.loads(response_text)

            quotes = data.get("quotes", [])

            if not quotes:
                reason = data.get("reason", "No verified quotes found")
                return QuoteResult(
                    game_name=game_name,
                    source=QuoteSource.FAILED,
                    error_message=f"LLM: {reason}",
                )

            # Format quotes for QuoteResult
            formatted_quotes = []
            source_urls = set()

            for quote in quotes:
                # Skip if missing required fields
                if not quote.get("text") or not quote.get("attribution"):
                    continue

                formatted_quotes.append(
                    {
                        "text": quote["text"],
                        "attribution": quote["attribution"],
                    }
                )
                if quote.get("source_url"):
                    source_urls.add(quote["source_url"])

            if not formatted_quotes:
                return QuoteResult(
                    game_name=game_name,
                    source=QuoteSource.FAILED,
                    error_message="LLM returned no valid quotes",
                )

            # Use first source URL or combine multiple
            source_url = ", ".join(list(source_urls)[:3]) if source_urls else None

            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.WIKIQUOTE,  # Reusing this enum value
                quotes=formatted_quotes,
                source_url=source_url,
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response for {game_name}: {e}")
            return QuoteResult(
                game_name=game_name,
                source=QuoteSource.FAILED,
                error_message=f"Parse error: {str(e)}",
            )

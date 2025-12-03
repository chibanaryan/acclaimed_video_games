#!/usr/bin/env python3
"""
Test script for LLM Quote Service.

Usage:
  export ANTHROPIC_API_KEY="your-api-key"
  python3 test_llm_quotes.py "Half-Life 2"
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "acclaimedgames.settings")
django.setup()

from games.services.llm_quote_service import LLMQuoteService  # noqa: E402


def test_game(game_name: str):
    """Test LLM quote service with a single game."""
    print(f"\n{'='*60}")
    print(f"Testing LLM Quote Service for: {game_name}")
    print(f"{'='*60}\n")

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("\nTo use this service:")
        print("1. Get an API key from https://console.anthropic.com/")
        print("2. export ANTHROPIC_API_KEY='your-key-here'")
        print("3. Run this script again")
        return

    try:
        # Initialize service
        service = LLMQuoteService(fallback_to_wikiquote=True)

        # Get quotes
        print("Fetching quotes...")
        result = service.get_quotes(game_name)

        # Display results
        if result.quotes:
            print(f"\n✓ Found {len(result.quotes)} quote(s):\n")
            for i, quote in enumerate(result.quotes, 1):
                print(f"{i}. \"{quote['text']}\"")
                print(f"   — {quote['attribution']}")
                print()

            if result.source_url:
                print(f"Source(s): {result.source_url}")
        else:
            print("\n✗ No quotes found")
            if result.error_message:
                print(f"Reason: {result.error_message}")

    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_llm_quotes.py <game-name>")
        print("\nExamples:")
        print("  python3 test_llm_quotes.py 'Half-Life 2'")
        print("  python3 test_llm_quotes.py 'Doom'")
        print("  python3 test_llm_quotes.py 'The Elder Scrolls V: Skyrim'")
        sys.exit(1)

    game_name = " ".join(sys.argv[1:])
    test_game(game_name)

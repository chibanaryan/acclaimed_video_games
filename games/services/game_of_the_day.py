"""
Game of the Day service - weighted random selection with daily caching.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from django.core.cache import cache
from django.db.models import Count

from games import models

logger = logging.getLogger(__name__)


def get_game_of_the_day() -> Optional[models.Game]:
    """
    Get the Game of the Day with weighted random selection.

    Selection is cached daily (resets at midnight UTC).
    Only selects "complete" games with cover, description, year, and
    developer(s).

    Returns:
        Game instance or None if no eligible games exist
    """
    # Generate cache key based on current date
    today = datetime.utcnow().date()
    cache_key = f"game_of_the_day_{today.isoformat()}"

    # Try to get from cache
    cached_game_id = cache.get(cache_key)
    if cached_game_id:
        try:
            return models.Game.objects.with_relations().get(id=cached_game_id)
        except models.Game.DoesNotExist:
            # Game was deleted, fall through to new selection
            cache.delete(cache_key)

    # Select new game with weighted randomization
    game = _select_weighted_random_game()

    if game:
        # Calculate seconds until midnight UTC for cache timeout
        now = datetime.utcnow()
        midnight = datetime.combine(today + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = int((midnight - now).total_seconds())

        # Cache the selection until midnight
        cache.set(cache_key, game.id, timeout=seconds_until_midnight)
        logger.info(f"Selected Game of the Day: {game.name} (rank {game.rank})")

    return game


def _select_weighted_random_game() -> Optional[models.Game]:
    """
    Select a game using weighted random selection.

    Weighting algorithm: weight = 1 / (rank ** 0.45)

    Probability distribution (assuming ~1000 total games):
    - Top 300 games: ~50% selection probability
    - Rank 1: ~1.25% (appears every ~80 days)
    - Rank 100: ~0.16% (appears every ~625 days)
    - Rank 500: ~0.08% (appears every ~1250 days)

    Only selects "complete" games with:
    - IGDB cover image (igdb_artwork_id not null)
    - Description (not empty)
    - Year of release (not null)
    - At least one developer

    Returns:
        Selected Game instance or None
    """
    # Build queryset for complete games only
    games = list(
        models.Game.objects.filter(
            igdb_artwork_id__isnull=False,
            description__isnull=False,
            year_of_release__isnull=False,
        )
        .exclude(description="")
        .annotate(
            developer_count=Count("developers"),
        )
        .filter(
            developer_count__gte=1,
        )
        .values("id", "rank")
        .order_by("rank")
    )

    if not games:
        logger.warning("No complete games available for Game of the Day")
        return None

    # Calculate weights using tuned exponential decay (rank ** 0.45)
    # Balanced to give top 300 games ~50% probability (assuming ~1000 total games)
    weights = [1 / (game["rank"] ** 0.45) for game in games]

    # Select game using weighted random choice
    selected_game_data = random.choices(games, weights=weights, k=1)[0]

    # Fetch full game object with relations
    return models.Game.objects.with_relations().get(id=selected_game_data["id"])


def get_featured_quote(game: models.Game) -> Optional[models.GameQuote]:
    """
    Get a featured quote for the game.

    Prioritizes quotes marked as featured, falls back to most recent.

    Args:
        game: Game instance

    Returns:
        GameQuote instance or None
    """
    # Try to get a featured quote first
    quote = game.quotes.filter(is_featured=True).first()

    # Fall back to any quote if no featured quotes
    if not quote:
        quote = game.quotes.first()

    return quote

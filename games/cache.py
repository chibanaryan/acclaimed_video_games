"""
Cache utilities for the games app.

Centralized cache key management and invalidation functions to avoid
tight coupling between signals and views.
"""

from django.core.cache import cache


def invalidate_played_games_cache(user_id):
    """Invalidate the played games cache for a specific user."""
    cache.delete(f"played_games_{user_id}")


def invalidate_want_to_play_cache(user_id):
    """Invalidate the want-to-play games cache for a specific user."""
    cache.delete(f"want_to_play_games_{user_id}")

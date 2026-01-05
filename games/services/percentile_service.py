"""
Percentile calculation service for user statistics.

Calculates where a user's played game count ranks relative to other users.
"""

from django.core.cache import cache
from django.db.models import Count, Q

from core.models import User
from games import config, models


def get_played_games_distribution():
    """
    Get cached distribution of played game counts across users.

    Returns a sorted list of (user_id, played_count) tuples for users
    with at least 1 non-orphaned played game.

    Cached for 1 hour.
    """
    cache_key = "user_played_games_distribution"
    distribution = cache.get(cache_key)

    if distribution is None:
        # Aggregate played game counts per user (non-orphaned only)
        distribution = list(
            User.objects.annotate(
                played_count=Count(
                    "played_games", filter=Q(played_games__game__isnull=False)
                )
            )
            .filter(played_count__gt=0)
            .values_list("id", "played_count")
            .order_by("played_count")
        )
        cache.set(cache_key, distribution, config.CACHE_TIMEOUT_1_HOUR)

    return distribution


def calculate_percentile(user_played_count: int) -> dict:
    """
    Calculate the percentile ranking for a user's played count.

    Args:
        user_played_count: Number of non-orphaned games the user has played

    Returns:
        dict with:
        - percentile: int (0-100) or None if not applicable
        - total_users: int - number of active users in comparison
        - message: str - formatted display message
    """
    if user_played_count == 0:
        return {
            "percentile": None,
            "total_users": 0,
            "message": "Start tracking games to see your rank!",
        }

    distribution = get_played_games_distribution()
    total_users = len(distribution)

    if total_users == 0:
        return {
            "percentile": None,
            "total_users": 0,
            "message": "Start tracking games to see your rank!",
        }

    if total_users == 1:
        return {
            "percentile": 100,
            "total_users": 1,
            "message": "You're the first to start tracking games!",
        }

    # Count users with FEWER played games and calculate rank
    users_with_fewer = sum(1 for _, count in distribution if count < user_played_count)
    rank = total_users - users_with_fewer  # 1 = best, total_users = worst

    # For small populations, show rank instead of percentile
    if total_users < 10:
        if rank == 1:
            message = f"You're #1 of {total_users} players!"
        else:
            message = f"You're #{rank} of {total_users} players"
        return {
            "percentile": None,
            "total_users": total_users,
            "message": message,
        }

    # Calculate percentile for larger populations
    percentile = round((users_with_fewer / total_users) * 100)

    # Format message
    if percentile >= 99:
        message = "You're in the top 1% of players!"
    else:
        message = f"You've played more games than {percentile}% of players"

    return {
        "percentile": percentile,
        "total_users": total_users,
        "message": message,
    }

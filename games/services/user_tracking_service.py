"""
User tracking service for PlayedGame and WantToPlayGame operations.

Handles reconnection of orphaned records and merging of duplicates
when games are imported.
"""

import logging
from typing import TYPE_CHECKING

from django.db import transaction

from games.cache import invalidate_played_games_cache, invalidate_want_to_play_cache

if TYPE_CHECKING:
    from games.models import Game

logger = logging.getLogger(__name__)


def reconnect_tracking_records(
    game: "Game",
    igdb_ids: list[int],
    primary_igdb_id: int,
) -> dict:
    """
    Reconnect orphaned PlayedGame and WantToPlayGame records to a game.

    This function:
    1. Finds orphaned records matching any of the provided IGDB IDs
    2. Updates them to point to the game
    3. Normalizes igdb_id to the primary ID
    4. Detects and merges duplicates (keeps earliest, deletes others)
    5. Invalidates affected user caches

    Args:
        game: The Game instance to reconnect records to
        igdb_ids: List of all IGDB IDs for this game (primary first)
        primary_igdb_id: The primary IGDB ID to normalize to

    Returns:
        dict with statistics: {
            'played_reconnected': int,
            'played_merged': int,
            'want_reconnected': int,
            'want_merged': int,
            'users_affected': set of user_ids
        }
    """
    from games import models

    stats = {
        "played_reconnected": 0,
        "played_merged": 0,
        "want_reconnected": 0,
        "want_merged": 0,
        "users_affected": set(),
    }

    if not igdb_ids:
        return stats

    with transaction.atomic():
        # Process PlayedGame records
        played_stats = _reconnect_model_records(
            model_class=models.PlayedGame,
            game=game,
            igdb_ids=igdb_ids,
            primary_igdb_id=primary_igdb_id,
        )
        stats["played_reconnected"] = played_stats["reconnected"]
        stats["played_merged"] = played_stats["merged"]
        stats["users_affected"].update(played_stats["users_affected"])

        # Process WantToPlayGame records
        want_stats = _reconnect_model_records(
            model_class=models.WantToPlayGame,
            game=game,
            igdb_ids=igdb_ids,
            primary_igdb_id=primary_igdb_id,
        )
        stats["want_reconnected"] = want_stats["reconnected"]
        stats["want_merged"] = want_stats["merged"]
        stats["users_affected"].update(want_stats["users_affected"])

    # Invalidate caches for affected users (outside transaction for safety)
    for user_id in stats["users_affected"]:
        invalidate_played_games_cache(user_id)
        invalidate_want_to_play_cache(user_id)

    if stats["played_reconnected"] or stats["want_reconnected"]:
        logger.info(
            "Reconnected tracking records for game '%s' (igdb_id=%s): "
            "played=%d (merged=%d), want=%d (merged=%d)",
            game.name,
            primary_igdb_id,
            stats["played_reconnected"],
            stats["played_merged"],
            stats["want_reconnected"],
            stats["want_merged"],
        )

    return stats


def _reconnect_model_records(
    model_class,
    game: "Game",
    igdb_ids: list[int],
    primary_igdb_id: int,
) -> dict:
    """
    Internal helper to reconnect records for a specific model.

    Handles:
    1. Finding orphaned records (game=None) matching igdb_ids
    2. Normalizing igdb_id to primary
    3. Detecting and merging duplicates per user
    """
    stats = {"reconnected": 0, "merged": 0, "users_affected": set()}

    # Get orphaned records matching any of the IGDB IDs
    orphaned_records = list(
        model_class.objects.filter(
            igdb_id__in=igdb_ids,
            game__isnull=True,
        ).select_for_update()
    )

    if not orphaned_records:
        return stats

    # Collect user_ids that need processing
    user_ids_with_records = {}
    for record in orphaned_records:
        if record.user_id not in user_ids_with_records:
            user_ids_with_records[record.user_id] = []
        user_ids_with_records[record.user_id].append(record)
        stats["users_affected"].add(record.user_id)

    # Process each user's records
    for user_id, records in user_ids_with_records.items():
        # Check if user already has a record for this game with primary ID
        existing_primary = model_class.objects.filter(
            user_id=user_id,
            igdb_id=primary_igdb_id,
            game=game,
        ).first()

        if existing_primary:
            # User already has a connected record with primary ID
            # Delete all orphaned records (they're duplicates)
            for record in records:
                record.delete()
                stats["merged"] += 1
        elif len(records) == 1:
            # Single orphaned record - reconnect and normalize
            record = records[0]
            record.game = game
            record.igdb_id = primary_igdb_id
            record.save(update_fields=["game", "igdb_id"])
            stats["reconnected"] += 1
        else:
            # Multiple orphaned records for same user - merge
            # Sort by created to keep earliest
            records.sort(key=lambda r: r.created)
            keeper = records[0]

            # Reconnect and normalize the keeper
            keeper.game = game
            keeper.igdb_id = primary_igdb_id
            keeper.save(update_fields=["game", "igdb_id"])
            stats["reconnected"] += 1

            # Delete the rest
            for record in records[1:]:
                record.delete()
                stats["merged"] += 1

    return stats

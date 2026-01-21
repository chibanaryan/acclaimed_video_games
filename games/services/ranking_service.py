"""
Ranking service for Acclaimed Games.

Handles year and decade ranking calculations for games.
"""

from typing import Tuple

from django.db import connection, transaction

from games import models


def year_to_decade(year: int) -> int:
    """Convert a year to its decade (e.g., 1985 -> 1980)."""
    return int(year / 10) * 10


def update_year_decade_ranks() -> Tuple[int, int]:
    """
    Bulk update year_rank and decade_rank for all games.
    Should be called after importing/updating game rankings.

    Uses efficient database queries to calculate ranking positions
    within each year and decade based on the global rank field.

    On PostgreSQL: Uses raw SQL with window functions for optimal performance.
    On SQLite: Falls back to chunked processing to avoid memory issues.

    Returns:
        Tuple of (games_updated, years_processed)
    """
    # Check database backend
    is_postgres = connection.vendor == "postgresql"

    if is_postgres:
        # PostgreSQL: Use raw SQL with window functions for optimal performance
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Update year_rank using window function
                cursor.execute("""
                    UPDATE games_game
                    SET year_rank = subquery.row_num
                    FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY year_of_release
                                   ORDER BY rank ASC
                               ) as row_num
                        FROM games_game
                    ) AS subquery
                    WHERE games_game.id = subquery.id
                """)

                # Update decade_rank using window function
                cursor.execute("""
                    UPDATE games_game
                    SET decade_rank = subquery.row_num
                    FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY (year_of_release / 10) * 10
                                   ORDER BY rank ASC
                               ) as row_num
                        FROM games_game
                    ) AS subquery
                    WHERE games_game.id = subquery.id
                """)

        games_updated = models.Game.objects.count()
        years_count = models.Game.objects.values("year_of_release").distinct().count()
        return (games_updated, years_count)
    else:
        # SQLite: Use chunked processing to avoid loading all games into memory
        from collections import defaultdict

        year_games = defaultdict(list)
        decade_games = defaultdict(list)
        years = set()

        # Process in chunks to avoid memory issues
        chunk_size = 1000
        total_games = models.Game.objects.count()

        # First pass: collect games by year (for year_rank)
        for offset in range(0, total_games, chunk_size):
            chunk = models.Game.objects.order_by("year_of_release", "rank")[
                offset : offset + chunk_size
            ]
            for game in chunk:
                year_games[game.year_of_release].append(game.id)
                years.add(game.year_of_release)

        # Second pass: collect games by decade ordered by global rank
        for offset in range(0, total_games, chunk_size):
            chunk = models.Game.objects.order_by("rank")[offset : offset + chunk_size]
            for game in chunk:
                decade = year_to_decade(game.year_of_release)
                decade_games[decade].append(game.id)

        # Bulk update year ranks
        games_updated = 0
        with transaction.atomic():
            for _, game_ids in year_games.items():
                for rank_position, game_id in enumerate(game_ids, 1):
                    models.Game.objects.filter(id=game_id).update(
                        year_rank=rank_position
                    )
                    games_updated += 1

            # Bulk update decade ranks
            for _, game_ids in decade_games.items():
                for rank_position, game_id in enumerate(game_ids, 1):
                    models.Game.objects.filter(id=game_id).update(
                        decade_rank=rank_position
                    )

        return (games_updated, len(years))

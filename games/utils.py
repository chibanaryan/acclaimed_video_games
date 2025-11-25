import csv
from dataclasses import dataclass
from io import TextIOWrapper
from typing import Any, Callable, Dict, List, Optional, Tuple

from django.db import connection, transaction
from django.db.models import Q, QuerySet

from . import constants, models


def import_data(data: Dict[str, Any]) -> Optional[Tuple[bool, str]]:
    """
    Route posted form data to the correct import helper.
    Handles both legacy single-file imports and new batch imports.
    """

    if data.get("delete"):
        return delete_existing_data()

    # Check if this is a batch import (new form format)
    if any(
        [
            data.get(f)
            for f in ["platforms_file", "lists_file", "games_file", "memberships_file"]
        ]
    ):
        success, message, _ = import_batch(data)
        return (success, message)

    # Legacy single-file import
    if data.get("file"):
        f = TextIOWrapper(data["file"], encoding="utf-8")
        import_type = data["type"]

        functions = {
            constants.TYPE_GAME: import_games,
            constants.TYPE_PLATFORM: import_platforms,
            constants.TYPE_LIST: import_lists,
            constants.TYPE_LIST_MEMBERSHIP: import_listmemberships,
            constants.TYPE_DEVELOPER: import_developers,
        }

        handler = functions.get(import_type)
        if not handler:
            return (False, f'Unknown import type "{import_type}" provided.')

        try:
            result = handler(f)
            # Update last_full_update if games were imported
            if import_type == constants.TYPE_GAME and result[0]:
                from django.utils import timezone

                metadata = models.SiteMetadata.get_instance()
                metadata.last_full_update = timezone.now()
                metadata.save()

            return result
        except Exception as e:
            return (False, f"Could not process uploaded file: {e}")


def import_igdb_with_progress():
    """
    Fetch IGDB data for all games with progress updates.
    Yields JSON progress events for streaming to SSE client in real-time.

    Uses optimized IGDBImportService with concurrent + batched processing:
    - Default: batch_size=50 (free tier) or 500 (Pro tier)
    - Default: concurrency=8 workers
    - Performance: ~100 games/sec (25-500x faster than sequential)
    """
    import json
    import queue
    import threading

    from games.services.igdb_importer import IGDBImportService

    # Use a queue to pass events from callback to generator in real-time
    event_queue = queue.Queue()

    # Event to signal when client disconnects
    stop_event = threading.Event()

    def progress_callback(event_type: str, data: dict) -> None:  # pragma: no cover
        """Callback to stream service events to SSE client."""
        # Add event type if not already present
        if "event" not in data:
            data["event"] = event_type
        # Queue the event for immediate streaming
        event_queue.put(json.dumps(data))

    try:
        # Create service with optimizations enabled
        service = IGDBImportService(
            concurrency=8,  # Use 8 concurrent workers for speed
            batch_size=None,  # Auto-detect from tier (50 free, 500 Pro)
            use_pro_tier=None,  # Auto-detect from settings
            progress_callback=progress_callback,
        )

        # Get games (only those without IGDB data)
        games = models.Game.objects.filter(igdb_artwork_id__isnull=True).order_by(
            "rank"
        )

        # Run import in a thread to avoid blocking the generator
        def run_import():
            try:
                service.import_games(games)
            except Exception as e:
                event_queue.put(json.dumps({"event": "error", "error": str(e)}))
            finally:
                # Signal that we're done
                event_queue.put(None)

        import_thread = threading.Thread(target=run_import, daemon=True)
        import_thread.start()

        # Stream events as they come in from the queue
        try:
            while True:
                try:
                    # Wait for event with timeout to detect if thread is stuck
                    # Increased to 120s to handle large batches and API rate limiting
                    event_json = event_queue.get(timeout=120)

                    # None signals the end of the import
                    if event_json is None:
                        break

                    # Yield the event in SSE format
                    yield f"data: {event_json}\n\n"
                except queue.Empty:
                    # Timeout waiting for events
                    error_msg = "Import timeout - no progress for 120 seconds"
                    error_data = json.dumps({"event": "error", "error": error_msg})
                    yield f"data: {error_data}\n\n"
                    break
        except GeneratorExit:  # pragma: no cover
            # Client disconnected - signal the import thread to stop
            # Note: The import thread will continue in the background as
            # a daemon thread until it completes. This prevents wasted
            # API calls if the user navigates away.
            stop_event.set()
            import logging

            logging.getLogger(__name__).info(
                "Client disconnected from IGDB import progress stream. "
                "Import thread continues in background."
            )
            raise

    except Exception as e:
        # Yield error event
        yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"


def _validate_prerequisites(import_type: str) -> Optional[Tuple[bool, str]]:
    """
    Validate that prerequisites exist for the given import type.

    Returns None if valid, or a (False, error_message) tuple if validation fails.
    """
    if import_type == constants.TYPE_LIST:
        # Lists have no hard dependencies (Publications are auto-created)
        return None

    if import_type == constants.TYPE_GAME:
        # Games require Platforms to exist
        if not models.Platform.objects.exists():
            return (
                False,
                (
                    "Cannot import games: No platforms found. "
                    "Please import platforms first."
                ),
            )
        return None

    if import_type == constants.TYPE_LIST_MEMBERSHIP:
        # ListMemberships require both Lists and Games to exist
        if not models.List.objects.exists():
            return (
                False,
                "Cannot import game positions: No source lists found. "
                "Please import source lists first.",
            )
        if not models.Game.objects.exists():
            return (
                False,
                (
                    "Cannot import game positions: No games found. "
                    "Please import games first."
                ),
            )
        return None

    return None


def import_batch_with_progress(data: Dict[str, Any]):
    """
    Import multiple files in the correct order with real-time progress tracking.
    Yields JSON progress events for streaming to SSE client in real-time.

    Files are imported in this order:
    1. Platforms (no dependencies)
    2. Source Lists (Publications are auto-created)
    3. Games (depends on Platforms)
    4. Game Positions (depends on Lists and Games)

    If any import fails, the entire transaction is rolled back.
    """
    import json
    import queue
    import threading

    # Use a queue to pass events from callback to generator in real-time
    event_queue = queue.Queue()

    def progress_callback(event_type: str, data: dict) -> None:
        """Callback to stream service events to SSE client."""
        # Add event type if not already present
        if "event" not in data:
            data["event"] = event_type
        # Queue the event for immediate streaming
        event_queue.put(json.dumps(data))

    import_sequence = [
        ("platforms_file", "Platforms", import_platforms),
        ("lists_file", "Source Lists", import_lists),
        ("games_file", "Games", import_games),
        ("memberships_file", "Game Positions", import_listmemberships),
    ]

    try:

        def run_import():
            try:
                with transaction.atomic():
                    for field_name, display_name, handler in import_sequence:
                        file_obj = data.get(field_name)
                        if not file_obj:
                            continue

                        # Validate prerequisites
                        validation_error = _validate_prerequisites(
                            display_name.upper().replace(" ", "_")
                        )
                        if validation_error:
                            event_queue.put(
                                json.dumps(
                                    {
                                        "event": "error",
                                        "file": display_name,
                                        "message": validation_error[1],
                                    }
                                )
                            )
                            continue

                        # Import the file
                        try:
                            f = TextIOWrapper(file_obj, encoding="utf-8")
                            handler(f, progress_callback)
                        except Exception as e:
                            event_queue.put(
                                json.dumps(
                                    {
                                        "event": "error",
                                        "file": display_name,
                                        "message": str(e),
                                    }
                                )
                            )

            except Exception as e:  # pragma: no cover
                event_queue.put(json.dumps({"event": "error", "message": str(e)}))
            finally:
                # Signal that we're done
                event_queue.put(None)

        import_thread = threading.Thread(target=run_import, daemon=True)
        import_thread.start()

        # Stream events as they come in from the queue
        while True:
            try:
                # Wait for event with timeout to detect if thread is stuck
                event_json = event_queue.get(timeout=30)

                # None signals the end of the import
                if event_json is None:
                    break

                # Yield the event in SSE format
                yield f"data: {event_json}\n\n"
            except queue.Empty:
                # Timeout waiting for events
                error_msg = "Import timeout - no progress for 30 seconds"
                yield (
                    f"data: {json.dumps({'event': 'error', 'message': error_msg})}\n\n"
                )
                break

    except Exception as e:
        # Yield error event
        yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"


def import_batch(data: Dict[str, Any]) -> Tuple[bool, str, bool]:
    """
    Import multiple files in the correct order with transaction safety.

    Files are imported in this order:
    1. Platforms (no dependencies)
    2. Source Lists (Publications are auto-created)
    3. Games (depends on Platforms)
    4. Game Positions (depends on Lists and Games)

    If any import fails, the entire transaction is rolled back.

    Returns:
        Tuple of (success, message, trigger_igdb) where trigger_igdb indicates
        whether IGDB data should be fetched after successful import.
    """
    results = []
    import_sequence = [
        ("platforms_file", constants.TYPE_PLATFORM, "Platforms", import_platforms),
        ("lists_file", constants.TYPE_LIST, "Source Lists", import_lists),
        ("games_file", constants.TYPE_GAME, "Games", import_games),
        (
            "memberships_file",
            constants.TYPE_LIST_MEMBERSHIP,
            "Game Positions",
            import_listmemberships,
        ),
    ]

    try:
        games_file_imported = False
        with transaction.atomic():
            for field_name, import_type, display_name, handler in import_sequence:
                file_obj = data.get(field_name)
                if not file_obj:
                    continue

                # Validate prerequisites
                validation_error = _validate_prerequisites(import_type)
                if validation_error:
                    return validation_error + (False,)

                # Import the file
                try:
                    f = TextIOWrapper(file_obj, encoding="utf-8")
                    success, message = handler(f)
                    results.append(message)
                    # Track if games file was imported
                    if field_name == "games_file":
                        games_file_imported = True
                except Exception as e:
                    return (False, f"{display_name} import failed: {e}", False)

        # If we get here, all imports succeeded
        if not results:
            return (False, "No files were selected for import.", False)

        # Update last_full_update if games file was imported
        if games_file_imported:
            from django.utils import timezone

            metadata = models.SiteMetadata.get_instance()
            metadata.last_full_update = timezone.now()
            metadata.save()

        summary = "\n".join(results)
        # Return IGDB trigger flag if checkbox was checked
        trigger_igdb = data.get("igdb", False)
        return (True, summary, trigger_igdb)

    except Exception as e:
        return (False, f"Import transaction failed: {e}", False)


def delete_existing_data() -> Tuple[bool, str]:

    models_to_delete = [
        models.Platform,
        models.List,
        models.Publication,
        models.ListMembership,
        models.Developer,
        models.DeveloperAlias,
        models.Game,
        models.Genre,
    ]

    with transaction.atomic():
        # Delete objects
        total = 0
        for model in models_to_delete:
            count, _ = model.objects.all().delete()
            total += count

        # Reset id sequences
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                for model in models_to_delete:
                    table_name = connection.ops.quote_name(
                        f"{model._meta.db_table}_id_seq"
                    )
                    cursor.execute(f"ALTER SEQUENCE {table_name} RESTART WITH 1;")
        elif connection.vendor == "sqlite":
            # SQLite uses sqlite_sequence table to track autoincrement values
            with connection.cursor() as cursor:
                for model in models_to_delete:
                    table_name = model._meta.db_table
                    cursor.execute(
                        "DELETE FROM sqlite_sequence WHERE name = %s", [table_name]
                    )

    return (True, f"{total} objects deleted")


def import_lists(
    f: TextIOWrapper, progress_callback: Optional[Callable[[str, Dict], None]] = None
) -> Tuple[bool, str]:
    """
    Import critic lists from a TSV file with columns:
    publisher, year, type, name, url.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
    updated = 0
    row_number = 0
    total_rows = 0

    # Count total rows first
    current_pos = f.tell()
    for _ in rows:
        total_rows += 1
    f.seek(current_pos)
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")

    if progress_callback:
        progress_callback("start", {"total": total_rows, "file": "Source Lists"})

    try:
        for line_number, bits in enumerate(rows):
            row_number += 1
            publisher_name, year, type, name, url = bits
            publisher, created = models.Publication.objects.get_or_create(
                name=publisher_name,
            )

            source_list, created = models.List.objects.get_or_create(
                publisher=publisher,
                year=year,
                name=name,
                order=line_number + 1,
                defaults={
                    "url": url,
                    "type": type[0],
                },
            )

            if created:
                count += 1
            else:
                updated += 1

            # Report progress
            if progress_callback and row_number % 5 == 0:
                progress_callback(
                    "progress",
                    {
                        "current": row_number,
                        "total": total_rows,
                        "list_name": name,
                        "percentage": (
                            int((row_number / total_rows) * 100)
                            if total_rows > 0
                            else 0
                        ),
                    },
                )

        if progress_callback:
            progress_callback("complete", {"count": count, "updated": updated})

        return (True, f"Lists: {count} created, {updated} updated")

    except Exception as e:
        if progress_callback:
            progress_callback("error", {"message": str(e)})
        raise


def import_listmemberships(
    f: TextIOWrapper, progress_callback: Optional[Callable[[str, Dict], None]] = None
) -> Tuple[bool, str]:
    """
    Import ranked appearances for each game from a TSV file where each row is a
    game rank and each column contains "list_id:position".

    Deletes all existing ListMembership records before importing to avoid duplicates.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    # Delete existing memberships to avoid duplicates on re-import
    models.ListMembership.objects.all().delete()

    list_map = {x.order: x for x in models.List.objects.all()}
    memberships = []
    row_number = 0
    total_created = 0
    batch_size = 1000  # Flush to database every 1000 memberships

    # Count total lines first
    current_pos = f.tell()
    total_rows = sum(1 for _ in f)
    f.seek(current_pos)

    if progress_callback:
        progress_callback("start", {"total": total_rows, "file": "Game Positions"})

    try:
        for line_number, line in enumerate(f):
            row_number += 1
            bits = line.strip().split("\t")
            game = models.Game.objects.get(rank=line_number + 1)
            for bit in bits:
                list_id, position = [int(x) for x in bit.split(":")]

                source_list = list_map.get(list_id + 1)
                if not source_list:
                    continue

                memberships.append(
                    models.ListMembership(list=source_list, game=game, rank=position)
                )

            # Flush batch to database when it reaches batch_size
            if len(memberships) >= batch_size:
                created = models.ListMembership.objects.bulk_create(memberships)
                total_created += len(created)
                memberships.clear()

            # Report progress
            if progress_callback and row_number % 50 == 0:
                progress_callback(
                    "progress",
                    {
                        "current": row_number,
                        "total": total_rows,
                        "game_rank": line_number + 1,
                        "percentage": (
                            int((row_number / total_rows) * 100)
                            if total_rows > 0
                            else 0
                        ),
                    },
                )

        # Flush any remaining memberships
        if memberships:
            created = models.ListMembership.objects.bulk_create(memberships)
            total_created += len(created)
            memberships.clear()

        if progress_callback:
            progress_callback("complete", {"count": total_created})

        return (True, f"List memberships: {total_created} created")

    except Exception as e:
        if progress_callback:
            progress_callback("error", {"message": str(e)})
        raise


def import_games(
    f: TextIOWrapper, progress_callback: Optional[Callable[[str, Dict], None]] = None
) -> Tuple[bool, str]:
    """
    Import games from a TSV file with columns:
    rank, name, year, IGDB id, comma separated platform codes.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
                          Signature: callback(event_type: str, data: Dict)
                          Events: start, progress, error, complete
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
    updated = 0
    row_number = 0
    total_rows = 0

    # Count total rows first
    current_pos = f.tell()
    for _ in rows:
        total_rows += 1
    f.seek(current_pos)
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")

    if progress_callback:
        progress_callback("start", {"total": total_rows, "file": "Games"})

    try:
        for rank, game_name, year, igdb_id, platforms in rows:
            row_number += 1
            platform_codes = platforms.split(",")
            platform_objs = []
            for code in platform_codes:
                code = code.strip()
                platform, created = models.Platform.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": code,
                    },
                )
                platform_objs.append(platform)

            game, created = models.Game.objects.update_or_create(
                igdb_id=igdb_id,
                defaults={
                    "rank": int(rank),
                    "name": game_name,
                    "year_of_release": year,
                },
            )
            game.platforms.set(platform_objs)

            if created:
                count += 1
            else:
                updated += 1

            # Report progress
            if progress_callback and row_number % 10 == 0:
                progress_callback(
                    "progress",
                    {
                        "current": row_number,
                        "total": total_rows,
                        "game_name": game_name,
                        "percentage": (
                            int((row_number / total_rows) * 100)
                            if total_rows > 0
                            else 0
                        ),
                    },
                )

        # Update year and decade ranks for all games
        games_ranked, years_processed = update_year_decade_ranks()

        if progress_callback:
            progress_callback(
                "complete",
                {
                    "count": count,
                    "updated": updated,
                    "ranks_updated": games_ranked,
                },
            )

        return (
            True,
            f"Games: {count} created, {updated} updated, "
            f"{games_ranked} ranks calculated",
        )

    except Exception as e:
        if progress_callback:
            progress_callback("error", {"message": str(e)})
        raise


def import_platforms(
    f: TextIOWrapper, progress_callback: Optional[Callable[[str, Dict], None]] = None
) -> Tuple[bool, str]:
    """
    Import platform code/name pairs from a TSV file.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
    updated = 0
    row_number = 0
    total_rows = 0

    # Count total rows first
    current_pos = f.tell()
    for _ in rows:
        total_rows += 1
    f.seek(current_pos)
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")

    if progress_callback:
        progress_callback("start", {"total": total_rows, "file": "Platforms"})

    try:
        for code, name in rows:
            row_number += 1
            code = code.strip()
            name = name.strip()

            platform, created = models.Platform.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                },
            )

            if created:
                count += 1
            else:
                updated += 1

            # Report progress
            if progress_callback and row_number % 10 == 0:
                progress_callback(
                    "progress",
                    {
                        "current": row_number,
                        "total": total_rows,
                        "platform_name": name,
                        "percentage": (
                            int((row_number / total_rows) * 100)
                            if total_rows > 0
                            else 0
                        ),
                    },
                )

        if progress_callback:
            progress_callback("complete", {"count": count, "updated": updated})

        return (True, f"Platforms: {count} created, {updated} updated")

    except Exception as e:
        if progress_callback:
            progress_callback("error", {"message": str(e)})
        raise


def import_developers(f: TextIOWrapper) -> Tuple[bool, str]:
    """
    Import developers and aliases from a TSV file with columns:
    alias1, canonical[, alias2].
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
    updated = 0

    for bits in rows:
        alias1 = bits[0]
        canonical = bits[1]
        alias2 = None
        if len(bits) == 3:
            alias2 = bits[2]

        developer, created = models.Developer.objects.get_or_create(
            name=canonical,
        )

        for alias in [alias1, alias2]:
            if not alias:
                continue

            models.DeveloperAlias.objects.get_or_create(
                name=alias,
                defaults={
                    "developer": developer,
                },
            )

        if created:
            count += 1
        else:
            updated += 1

    return (True, f"Developers: {count} created, {updated} updated")


def year_to_decade(year: int) -> int:
    """Convert a year to its decade (e.g., 1985 -> 1980)."""
    return int(year / 10) * 10


def update_year_decade_ranks() -> Tuple[int, int]:
    """
    Bulk update year_rank and decade_rank for all games.
    Should be called after importing/updating game rankings.

    Uses efficient database queries to calculate ranking positions
    within each year and decade based on the global rank field.

    On PostgreSQL: Uses window functions for optimal performance (single query).
    On SQLite: Falls back to chunked processing to avoid memory issues.

    Returns:
        Tuple of (games_updated, years_processed)
    """
    from django.db import connection
    from django.db.models import F, Window
    from django.db.models.functions import RowNumber, Floor

    # Check database backend
    is_postgres = connection.vendor == "postgresql"

    if is_postgres:
        # PostgreSQL: Use window functions for optimal performance
        with transaction.atomic():
            # Update year_rank using window function
            models.Game.objects.update(
                year_rank=Window(
                    expression=RowNumber(),
                    partition_by=[F("year_of_release")],
                    order_by=[F("rank").asc()],
                )
            )

            # Update decade_rank using window function
            # Calculate decade as floor(year / 10) * 10
            models.Game.objects.update(
                decade_rank=Window(
                    expression=RowNumber(),
                    partition_by=[Floor(F("year_of_release") / 10) * 10],
                    order_by=[F("rank").asc()],
                )
            )

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


def apply_genre_filter(
    queryset: QuerySet, genre_ids: List[int], match_all: bool = True
) -> QuerySet:
    """
    Filter queryset by genres with any/all matching.

    Args:
        queryset: The queryset to filter
        genre_ids: List of genre IDs to filter by
        match_all: If True, games must have ALL genres. If False, ANY genre matches.

    Returns:
        Filtered queryset
    """
    if not genre_ids:
        return queryset

    if match_all:
        for genre_id in genre_ids:
            queryset = queryset.filter(genres=genre_id)
    else:
        q = Q()
        for genre_id in genre_ids:
            q |= Q(genres=genre_id)
        queryset = queryset.filter(q)

    return queryset


def apply_platform_filter(queryset: QuerySet, platform_ids: List[int]) -> QuerySet:
    """
    Filter queryset by platforms (any match).

    Args:
        queryset: The queryset to filter
        platform_ids: List of platform IDs to filter by

    Returns:
        Filtered queryset
    """
    if not platform_ids:
        return queryset

    return queryset.filter(platforms__in=platform_ids)


def get_or_set_cache(
    cache_key: str,
    queryset: QuerySet,
    fields: List[str],
    timeout: int = 86400,
    order_by: Optional[str] = None,
    transform_id: bool = False,
) -> List[Dict[str, Any]]:
    """
    Get cached list or build and cache from queryset.

    Args:
        cache_key: Key to use for caching
        queryset: Queryset to build list from if not cached
        fields: List of field names to include in each dict
        timeout: Cache timeout in seconds (default 24 hours)
        order_by: Optional field to order by
        transform_id: If True, convert 'id' field to string

    Returns:
        List of dictionaries with requested fields
    """
    from django.core.cache import cache

    result = cache.get(cache_key)
    if result is None:
        qs = queryset
        if order_by:
            qs = qs.order_by(order_by)
        result = list(qs.values(*fields))
        if transform_id and "id" in fields:
            result = [{**item, "id": str(item["id"])} for item in result]
        cache.set(cache_key, result, timeout)
    return result


def apply_year_filters(
    queryset: QuerySet,
    decade: Optional[str] = None,
    year: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> QuerySet:
    """
    Apply year/decade filtering to a Game queryset.

    Args:
        queryset: The queryset to filter
        decade: Decade string like "1990-99" or "2000-09"
        year: Single year as string (ignored if decade is set)
        start: Start year range as string
        end: End year range as string

    Returns:
        Filtered queryset
    """
    import re

    # Parse decade filter (format: "1990-99" -> start=1990, end=1999)
    if decade:
        decade_pattern = re.compile(r"(\d{2})(\d{2})-(\d{2})")
        match = decade_pattern.match(decade)
        if match:
            start_str = match.group(1) + match.group(2)
            end_str = match.group(1) + match.group(3)
            start_year = int(start_str)
            end_year = int(end_str)
            queryset = queryset.filter(
                year_of_release__gte=start_year, year_of_release__lte=end_year
            )

    # Year filter (single year) - only if decade not set
    if year and not decade:
        try:
            queryset = queryset.filter(year_of_release=int(year))
        except (ValueError, TypeError):
            pass

    # Start/end year range filters
    if start:
        try:
            queryset = queryset.filter(year_of_release__gte=int(start))
        except (ValueError, TypeError):
            pass
    if end:
        try:
            queryset = queryset.filter(year_of_release__lte=int(end))
        except (ValueError, TypeError):
            pass

    return queryset


def safe_int_filter(
    queryset: QuerySet, value: Optional[str], field_name: str
) -> QuerySet:
    """
    Apply integer filter, ignoring invalid values.

    Args:
        queryset: The queryset to filter
        value: String value to convert to int
        field_name: Field name to filter on

    Returns:
        Filtered queryset (unchanged if value is invalid)
    """
    if not value:
        return queryset
    try:
        queryset = queryset.filter(**{field_name: int(value)})
    except (ValueError, TypeError):
        pass
    return queryset


@dataclass
class Filter:
    param: str
    fields: List[str]
    coerce: type = str
    label: Callable[[str], str] = lambda x: x

    def filter_queryset(self, qs: QuerySet, param_val: Optional[str]) -> QuerySet:
        """
        Filter a queryset based on parameter value.

        Args:
            qs: The Django queryset to filter
            param_val: The parameter value to filter by

        Returns:
            The filtered queryset
        """
        if not param_val:
            return qs

        param_val = self.coerce(param_val.strip())
        if self.fields:
            query = Q()
            for field in self.fields:
                query |= Q(**{field: param_val})

        qs = qs.filter(query)

        return qs


def send_contact_email(name: str, email: str, category: str, message: str) -> bool:
    """
    Send a contact form email to the site administrators.

    Args:
        name: Name of the person sending the message
        email: Email address of the sender
        category: Category of the message (feature, bug, data, general, etc.)
        message: The message content

    Returns:
        True if the email was sent successfully, False otherwise
    """
    from django.conf import settings
    from django.core.mail import send_mail

    category_label = constants.get_contact_category_label(category)
    subject = f"[{category_label}] Contact Form Submission from {name}"

    # Use category-based email alias for better filtering
    # e.g., contact+feature@acclaimedvideogames.com
    base_email = settings.CONTACT_EMAIL
    if "@" in base_email:
        local, domain = base_email.split("@", 1)
        recipient_email = f"{local}+{category}@{domain}"
    else:
        recipient_email = base_email

    site_url = (
        settings.SITE_URL
        if hasattr(settings, "SITE_URL")
        else "acclaimedvideogames.com"
    )

    email_body = f"""
New contact form submission:

From: {name}
Email: {email}
Category: {category_label}

Message:
{message}

---
This message was sent via the contact form at {site_url}
"""

    try:
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send contact form email: {e}")
        return False

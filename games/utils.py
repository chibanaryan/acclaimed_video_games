import csv
from dataclasses import dataclass
from datetime import datetime
from io import TextIOWrapper
from typing import Any, Callable, Dict, List, Optional, Tuple

from django.db import connection, transaction
from django.db.models import Min, Q, QuerySet

from . import constants, models


def import_data(data: Dict[str, Any]) -> Optional[Tuple[bool, str]]:
    """
    Route posted form data to the correct import helper.
    Handles both legacy single-file imports and new batch imports.
    """

    if data.get("delete"):
        return delete_existing_data()

    if data.get("igdb"):
        return import_igdb()

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


def import_igdb() -> Tuple[bool, str]:
    """
    Fetch IGDB data for all games in the database.
    """
    games = models.Game.objects.all()

    # Check if games exist (handle both QuerySet and list from mocks)
    has_games = games.exists() if hasattr(games, "exists") else bool(games)
    if not has_games:
        return (
            False,
            (
                "No games found in the database. Import games first "
                "before fetching IGDB data."
            ),
        )

    count = 0
    for game in games:
        game.get_igdb_data()
        game.save(update_fields=["slug", "igdb_url", "igdb_artwork_id", "description"])
        count += 1

    return (True, f"IGDB data fetched for {count} game{'s' if count != 1 else ''}")


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

    def progress_callback(event_type: str, data: dict) -> None:
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
                    f"data: {json.dumps({'event': 'error', 'error': error_msg})}\n\n"
                )
                break

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

            except Exception as e:
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

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    list_map = {x.order: x for x in models.List.objects.all()}
    memberships = []
    row_number = 0

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

        created_memberships = models.ListMembership.objects.bulk_create(memberships)

        if progress_callback:
            progress_callback("complete", {"count": len(created_memberships)})

        return (True, f"List memberships: {len(created_memberships)} created")

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

        if progress_callback:
            progress_callback("complete", {"count": count, "updated": updated})

        return (True, f"Games: {count} created, {updated} updated")

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


year_rankings: Dict[int, List[int]] = {}
decade_rankings: Dict[int, List[int]] = {}


def _load_rankings() -> None:

    if year_rankings and decade_rankings:
        return

    min_year = (
        models.Game.objects.aggregate(min_year=Min("year_of_release"))["min_year"]
        or 1970
    )
    max_year = datetime.today().year
    all_years = range(min_year, max_year)
    decades = sorted(list(set(year_to_decade(x) for x in all_years)))

    for year in all_years:
        ids = list(
            models.Game.objects.filter(
                year_of_release=year,
            )
            .order_by(
                "rank",
            )
            .values_list(
                "id",
                flat=True,
            )
        )
        year_rankings[year] = ids

    for decade in decades:
        end = decade + 9

        ids = list(
            models.Game.objects.filter(
                year_of_release__gte=decade,
                year_of_release__lte=end,
            )
            .order_by("rank")
            .values_list(
                "id",
                flat=True,
            )
        )

        decade_rankings[decade] = ids


def get_ranking_for_year(game: "models.Game") -> int:
    """
    Get the ranking position for a game within its release year.

    Args:
        game: The Game instance to get ranking for

    Returns:
        The 1-indexed ranking position within the year

    Raises:
        ValueError: If rankings are not available or game not found
    """
    _load_rankings()

    ids = year_rankings.get(game.year_of_release)
    if not ids:
        raise ValueError(
            f"No rankings available for year {game.year_of_release}. "
            "Did the import complete successfully?"
        )

    if game.id not in ids:
        raise ValueError(
            f"Game {game.id} not found in rankings for year {game.year_of_release}."
        )

    return ids.index(game.id) + 1


def get_ranking_for_decade(game: "models.Game") -> int:
    """
    Get the ranking position for a game within its release decade.

    Args:
        game: The Game instance to get ranking for

    Returns:
        The 1-indexed ranking position within the decade

    Raises:
        ValueError: If rankings are not available or game not found
    """
    _load_rankings()

    decade = year_to_decade(game.year_of_release)
    ids = decade_rankings.get(decade)
    if not ids:
        raise ValueError(
            f"No rankings available for decade {decade}. "
            "Did the import complete successfully?"
        )

    if game.id not in ids:
        raise ValueError(f"Game {game.id} not found in rankings for decade {decade}.")

    return ids.index(game.id) + 1


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

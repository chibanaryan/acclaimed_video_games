"""
Import handler service for Acclaimed Games.

Handles importing game data from TSV files including:
- Platforms
- Source Lists
- Games
- List Memberships (game positions)
- Developers

Also provides IGDB data fetching with progress tracking.
"""

import csv
from io import TextIOWrapper
from typing import Any, Callable, Dict, Optional, Tuple

from django.db import connection, transaction
from django.db.models import Q

from games import config, constants, models


def import_data(data: Dict[str, Any]) -> Optional[Tuple[bool, str]]:
    """
    Route posted form data to the correct import helper.
    Handles both legacy single-file imports and new batch imports.
    """

    if data.get("delete"):
        return delete_existing_data()

    if data.get("clear_igdb_metadata"):
        return clear_igdb_metadata()

    if data.get("clear_wikipedia_metadata"):
        return clear_wikipedia_metadata()

    # Check if this is a batch import (new form format)
    if any(
        [
            data.get(f)
            for f in ["platforms_file", "lists_file", "games_file", "memberships_file"]
        ]
    ):
        success, message = import_batch(data)
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


def import_igdb_with_progress(update_relationships: bool = False):
    """
    Fetch IGDB data for all games with progress updates.
    Yields JSON progress events for streaming to SSE client in real-time.

    Uses optimized IGDBImportService with concurrent + batched processing:
    - Default: batch_size=50 (free tier) or 500 (Pro tier)
    - Default: concurrency=8 workers
    - Performance: ~100 games/sec (25-500x faster than sequential)

    Args:
        update_relationships: If True, update Company/Studio/Genre relationships
            for games that already have IGDB metadata, without modifying the
            metadata records. Used after re-importing games.
    """
    import json
    import queue
    import threading

    from games import igdb
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
        if update_relationships:
            # Update relationships for games with existing IGDB data
            games = models.Game.objects.filter(
                primary_igdb_game_data__isnull=False
            ).order_by("rank")

            total_games = games.count()
            if total_games == 0:
                event_queue.put(
                    json.dumps(
                        {"event": "error", "error": "No games with IGDB data found"}
                    )
                )
                event_queue.put(None)
            else:
                # Run relationship update in a thread
                def run_update():
                    try:
                        api_client = igdb.get_api()
                        if not api_client:
                            event_queue.put(
                                json.dumps(
                                    {
                                        "event": "error",
                                        "error": "IGDB API unavailable",
                                    }
                                )
                            )
                            return

                        progress_callback("start", {"total": total_games})

                        success_count = 0
                        error_count = 0
                        processed_count = 0

                        # Use batch API calls like regular IGDB import for speed
                        # Process in batches based on tier (50 free, 500 Pro)
                        batch_size = api_client.max_batch_size
                        game_list = list(games)

                        for batch_start in range(0, len(game_list), batch_size):
                            batch_games = game_list[
                                batch_start : batch_start + batch_size
                            ]

                            # Collect IGDB IDs for this batch
                            igdb_ids = [g.igdb_id for g in batch_games if g.igdb_id]
                            if not igdb_ids:
                                continue

                            # Fetch all games in batch (single API call)
                            games_data = api_client.get_games_info_by_ids(
                                igdb_ids, cache_results=True
                            )

                            # Update relationships for each game in batch
                            for game in batch_games:
                                processed_count += 1

                                if not game.igdb_id or game.igdb_id not in games_data:
                                    error_count += 1
                                    progress_callback(
                                        "progress",
                                        {
                                            "current": processed_count,
                                            "total": total_games,
                                            "game": game.name,
                                            "successful": success_count,
                                            "failed": error_count,
                                        },
                                    )
                                    continue

                                try:
                                    # Update relationships using pre-fetched data
                                    game_data = games_data[game.igdb_id]
                                    game._update_relationships_from_data(game_data)
                                    success_count += 1
                                except Exception as game_error:
                                    error_count += 1
                                    logging.getLogger(__name__).error(
                                        "Error updating relationships for '%s': %s",
                                        game.name,
                                        game_error,
                                        exc_info=True,
                                    )

                                # Send progress update
                                progress_callback(
                                    "progress",
                                    {
                                        "current": processed_count,
                                        "total": total_games,
                                        "game": game.name,
                                        "successful": success_count,
                                        "failed": error_count,
                                    },
                                )

                        progress_callback(
                            "complete",
                            {
                                "total": total_games,
                                "successful": success_count,
                                "failed": error_count,
                            },
                        )
                    except Exception as e:
                        event_queue.put(json.dumps({"event": "error", "error": str(e)}))
                    finally:
                        event_queue.put(None)

                import_thread = threading.Thread(target=run_update, daemon=True)
                import_thread.start()
        else:
            # Standard IGDB data import
            # Create service with optimizations enabled
            service = IGDBImportService(
                concurrency=8,  # Use 8 concurrent workers for speed
                batch_size=None,  # Auto-detect from tier (50 free, 500 Pro)
                use_pro_tier=None,  # Auto-detect from settings
                progress_callback=progress_callback,
            )

            # Get games (only those without IGDB data)
            games = models.Game.objects.filter(
                primary_igdb_game_data__isnull=True
            ).order_by("rank")

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

                    # Yield the event in SSE format with padding to force flush
                    # Adding whitespace ensures the web server doesn't
                    # buffer the response
                    yield f"data: {event_json}\n\n" + (" " * 2048) + "\n"
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


def import_wikipedia_pages_with_progress(force_refresh: bool = False):
    """
    Fetch Wikipedia pages for all games with progress updates.
    Yields JSON progress events for streaming to SSE client in real-time.

    Args:
        force_refresh: If True, process all games. If False, only process
            games without page titles.

    Yields:
        SSE-formatted events with progress data
    """
    import json
    import queue
    import threading

    from games.services.wiki_page_lookup_service import WikiPageLookupService
    from games.services.wiki_genre_service import WikiGenreService

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
        # Create services
        service = WikiPageLookupService(progress_callback=progress_callback)
        genre_service = WikiGenreService()

        # Get games to process
        if force_refresh:
            # Process all games
            games_queryset = models.Game.objects.all().order_by("rank")
        else:
            # Only process games without Wikipedia page data
            # Matches the same filter used in views.py for consistency
            games_queryset = models.Game.objects.filter(
                Q(primary_wikipedia_game_data__isnull=True)
                | Q(primary_wikipedia_game_data__page_title="")
            ).order_by("rank")

        # Extract needed fields
        games_data = games_queryset.values_list(
            "id", "name", "wikidata_id", "year_of_release"
        )

        # Run lookup in a thread to avoid blocking the generator
        def run_lookup():
            try:
                total = len(games_data)
                progress_callback("start", {"total": total})

                successful_count = 0
                failed_count = 0

                for idx, (game_id, game_name, wikidata_id, year) in enumerate(
                    games_data, start=1
                ):
                    if stop_event.is_set():
                        break

                    # Wrap individual game lookup in try/except to prevent one failure
                    # from stopping the entire batch
                    try:
                        # Perform lookup
                        result = service.lookup_page(game_name, wikidata_id, year)

                        # Save to database if successful
                        if result.success:
                            # Get the game object
                            game = models.Game.objects.get(id=game_id)

                            # First, check for orphaned record with same page_title
                            orphaned_record = models.WikipediaGameData.objects.filter(
                                page_title=result.page_title,
                                game__isnull=True,
                                is_primary=True,
                            ).first()

                            if orphaned_record:
                                # Reconnect orphaned record
                                # Unset is_primary on any existing records for this game
                                models.WikipediaGameData.objects.filter(
                                    game=game, is_primary=True
                                ).update(is_primary=False)

                                # Reconnect the orphaned record
                                orphaned_record.game = game
                                orphaned_record.lookup_source = result.lookup_source
                                # Update wikidata_id if available
                                if wikidata_id:
                                    orphaned_record.wikidata_id = wikidata_id
                                orphaned_record.save(
                                    update_fields=[
                                        "game",
                                        "lookup_source",
                                        "wikidata_id",
                                    ]
                                )
                                wiki_game_data = orphaned_record
                            else:
                                # No orphaned record found, create or update
                                # Unset is_primary on any existing records
                                models.WikipediaGameData.objects.filter(
                                    game=game, is_primary=True
                                ).update(is_primary=False)

                                # Create or update WikipediaGameData record
                                defaults = {
                                    "lookup_source": result.lookup_source,
                                    "is_primary": True,
                                }
                                if wikidata_id:
                                    defaults["wikidata_id"] = wikidata_id

                                wiki_game_data, created = (
                                    models.WikipediaGameData.objects.update_or_create(
                                        game=game,
                                        page_title=result.page_title,
                                        defaults=defaults,
                                    )
                                )

                            # Scrape genres from the Wikipedia page
                            # Use the URL we already found to avoid duplicate searches
                            try:
                                # Construct Wikipedia URL from page title
                                wikipedia_url = (
                                    f"https://en.wikipedia.org/wiki/"
                                    f"{result.page_title.replace(' ', '_')}"
                                )
                                genre_result = genre_service.get_genre_from_url(
                                    game_name, wikipedia_url
                                )
                                if genre_result.primary_genre:
                                    # Capitalize first letter if lowercase
                                    def capitalize_first(name):
                                        return (
                                            name[0].upper() + name[1:]
                                            if name and name[0].islower()
                                            else name
                                        )

                                    # Capitalize all genre names
                                    capitalized_primary = capitalize_first(
                                        genre_result.primary_genre
                                    )
                                    capitalized_all = [
                                        capitalize_first(g)
                                        for g in genre_result.all_genres
                                    ]

                                    # Update the WikipediaGameData with genres
                                    wiki_game_data.primary_genre = capitalized_primary
                                    # Store all genres as pipe-separated string
                                    if capitalized_all:
                                        wiki_game_data.all_genres = " | ".join(
                                            capitalized_all
                                        )
                                    wiki_game_data.save(
                                        update_fields=["primary_genre", "all_genres"]
                                    )

                                    # Create WikipediaGenre objects and link to game
                                    if capitalized_all:
                                        wikipedia_genres = []
                                        for genre_name in capitalized_all:
                                            genre, _ = (
                                                models.WikipediaGenre.objects.get_or_create(
                                                    name=genre_name
                                                )
                                            )
                                            wikipedia_genres.append(genre)
                                        game.wikipedia_genres.set(wikipedia_genres)
                            except Exception as genre_error:
                                # Log genre errors but don't fail page lookup
                                import logging

                                logging.getLogger(__name__).warning(
                                    "Failed to scrape genres for '%s': %s",
                                    game_name,
                                    genre_error,
                                )

                            # Set primary relationship
                            game.primary_wikipedia_game_data = wiki_game_data
                            game.save(update_fields=["primary_wikipedia_game_data"])

                            successful_count += 1

                            # Emit progress event
                            progress_callback(
                                "progress",
                                {
                                    "current": idx,
                                    "total": total,
                                    "game_name": game_name,
                                    "page_title": result.page_title,
                                    "lookup_source": result.lookup_source,
                                    "successful": successful_count,
                                    "failed": failed_count,
                                },
                            )
                        else:
                            failed_count += 1
                            # Emit progress event with failure info
                            progress_callback(
                                "progress",
                                {
                                    "current": idx,
                                    "total": total,
                                    "game_name": game_name,
                                    "error": result.error_message,
                                    "successful": successful_count,
                                    "failed": failed_count,
                                },
                            )

                    except Exception as game_error:
                        # Log the error and continue to next game
                        failed_count += 1
                        import logging

                        logging.getLogger(__name__).error(
                            "Unexpected error processing game '%s': %s",
                            game_name,
                            game_error,
                            exc_info=True,
                        )

                        # Emit progress event with error
                        progress_callback(
                            "progress",
                            {
                                "current": idx,
                                "total": total,
                                "game_name": game_name,
                                "error": f"Unexpected error: {str(game_error)}",
                                "successful": successful_count,
                                "failed": failed_count,
                            },
                        )

                # Emit complete event with summary
                progress_callback(
                    "complete",
                    {
                        "total": total,
                        "successful": successful_count,
                        "failed": failed_count,
                    },
                )

            except Exception as e:
                event_queue.put(json.dumps({"event": "error", "error": str(e)}))
            finally:
                # Signal that we're done
                event_queue.put(None)

        lookup_thread = threading.Thread(target=run_lookup, daemon=True)
        lookup_thread.start()

        # Stream events as they come in from the queue
        try:
            no_progress_count = 0
            max_no_progress = 120  # 120 * 15s = 30 minutes max idle time

            while True:
                try:
                    # Wait for event with 15-second timeout for keepalive
                    # Send keepalive pings to prevent Heroku from closing idle connections
                    event_json = event_queue.get(timeout=15)

                    # None signals the end of the lookup
                    if event_json is None:
                        break

                    # Reset no-progress counter on successful event
                    no_progress_count = 0

                    # Yield the event in SSE format with padding to force flush
                    # Adding whitespace ensures the web server doesn't
                    # buffer the response
                    yield f"data: {event_json}\n\n" + (" " * 2048) + "\n"
                except queue.Empty:
                    # No event in 15 seconds - send keepalive ping
                    no_progress_count += 1

                    if no_progress_count >= max_no_progress:
                        # 30 minutes with no progress - likely stalled
                        error_msg = "Lookup timeout - no progress for 30 minutes"
                        error_data = json.dumps({"event": "error", "error": error_msg})
                        yield f"data: {error_data}\n\n"
                        break

                    # Send keepalive comment to prevent connection timeout
                    # SSE comments (lines starting with :) are ignored by client
                    yield ": keepalive\n\n"
        except GeneratorExit:  # pragma: no cover
            # Client disconnected - signal the lookup thread to stop
            stop_event.set()
            import logging

            logging.getLogger(__name__).info(
                "Client disconnected from Wikipedia page lookup progress stream. "
                "Lookup thread continues in background."
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


def import_batch(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Import multiple files in the correct order with transaction safety.

    Files are imported in this order:
    1. Platforms (no dependencies)
    2. Source Lists (Publications are auto-created)
    3. Games (depends on Platforms)
    4. Game Positions (depends on Lists and Games)

    If any import fails, the entire transaction is rolled back.

    Returns:
        Tuple of (success, message)
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
                    return validation_error

                # Import the file
                try:
                    f = TextIOWrapper(file_obj, encoding="utf-8")
                    success, message = handler(f)
                    results.append(message)
                    # Track if games file was imported
                    if field_name == "games_file":
                        games_file_imported = True
                except Exception as e:
                    return (False, f"{display_name} import failed: {e}")

        # If we get here, all imports succeeded
        if not results:
            return (False, "No files were selected for import.")

        # Update last_full_update if games file was imported
        if games_file_imported:
            from django.utils import timezone

            metadata = models.SiteMetadata.get_instance()
            metadata.last_full_update = timezone.now()
            metadata.save()

        summary = "\n".join(results)

        # Automatically fetch IGDB data and update relationships after importing games
        if games_file_imported:
            import logging

            logger = logging.getLogger(__name__)

            # Count games needing IGDB data
            games_needing_fetch = models.Game.objects.filter(
                primary_igdb_game_data__isnull=True
            ).count()

            # Count games with metadata that need relationship updates
            games_needing_relationships = models.Game.objects.filter(
                primary_igdb_game_data__isnull=False
            ).count()

            logger.info(
                f"Automatic IGDB processing: {games_needing_fetch} games need fetch, "
                f"{games_needing_relationships} games have metadata"
            )

            if games_needing_fetch > 0 or games_needing_relationships > 0:
                summary += "\n\nAutomatically fetching IGDB data and reconnecting relationships..."

                try:
                    from games import igdb

                    api_client = igdb.get_api()
                    if not api_client:
                        summary += "\n⚠ IGDB API unavailable - skipping metadata fetch"
                    else:
                        # Step 1: Fetch IGDB data for games without metadata
                        if games_needing_fetch > 0:
                            from games.services.igdb_importer import IGDBImportService

                            summary += f"\n→ Fetching IGDB data for {games_needing_fetch} games..."
                            service = IGDBImportService(
                                concurrency=8,
                                batch_size=None,  # Auto-detect from tier
                                use_pro_tier=None,  # Auto-detect from settings
                            )
                            games_to_fetch = models.Game.objects.filter(
                                primary_igdb_game_data__isnull=True
                            ).order_by("rank")

                            processed, errors, _ = service.import_games(games_to_fetch)
                            summary += (
                                f"\n  ✓ Fetched {processed} games ({errors} errors)"
                            )

                        # Step 2: Update relationships for games with reconnected metadata
                        # Refresh the count after fetch (some may have been fetched)
                        games_with_metadata = models.Game.objects.filter(
                            primary_igdb_game_data__isnull=False
                        )

                        # Only update relationships for games that have no studios/IGDB genres
                        # (reconnected metadata with cleared M2M relationships)
                        games_needing_relationships = [
                            g for g in games_with_metadata if not g.studios.exists()
                        ]

                        if games_needing_relationships:
                            summary += f"\n→ Reconnecting relationships for {len(games_needing_relationships)} games..."
                            updated_count = 0
                            error_count = 0
                            batch_size = api_client.max_batch_size

                            for batch_start in range(
                                0, len(games_needing_relationships), batch_size
                            ):
                                batch_games = games_needing_relationships[
                                    batch_start : batch_start + batch_size
                                ]

                                # Collect IGDB IDs for this batch
                                igdb_ids = [g.igdb_id for g in batch_games if g.igdb_id]
                                if not igdb_ids:
                                    continue

                                # Fetch all games in batch (single API call)
                                games_data = api_client.get_games_info_by_ids(
                                    igdb_ids, cache_results=True
                                )

                                # Update relationships for each game
                                for game in batch_games:
                                    if game.igdb_id and game.igdb_id in games_data:
                                        try:
                                            game._update_relationships_from_data(
                                                games_data[game.igdb_id]
                                            )
                                            updated_count += 1
                                        except Exception:
                                            error_count += 1

                            summary += f"\n  ✓ Reconnected {updated_count} relationships ({error_count} errors)"

                except Exception as e:
                    summary += f"\n⚠ Error during automatic IGDB processing: {e}"

        return (True, summary)

    except Exception as e:
        return (False, f"Import transaction failed: {e}")


def delete_existing_data() -> Tuple[bool, str]:
    """
    Delete all game-related data from the database.

    Preserves IGDBGameData, WikipediaGameData, Company, Studio, and Genre
    for reconnection when games are re-imported.
    """
    models_to_delete = [
        models.Platform,
        models.List,
        models.Publication,
        models.ListMembership,
        models.Game,
    ]

    with transaction.atomic():
        # Orphan metadata records before deleting games
        # This preserves IGDB and Wikipedia data for reconnection on re-import
        models.IGDBGameData.objects.all().update(game=None)
        models.WikipediaGameData.objects.all().update(game=None)

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


def clear_igdb_metadata() -> Tuple[bool, str]:
    """
    Delete all IGDB metadata records (both connected and orphaned).

    This clears all IGDBGameData records and removes Company, Studio, and IGDBGenre
    objects since they are derived from IGDB data.

    Returns:
        Tuple of (success, message)
    """
    with transaction.atomic():
        # Count records before deletion
        igdb_count = models.IGDBGameData.objects.count()
        company_count = models.Company.objects.count()
        studio_count = models.Studio.objects.count()
        genre_count = models.IGDBGenre.objects.count()

        # Clear primary relationships on games
        models.Game.objects.update(primary_igdb_game_data=None)

        # Clear M2M relationships before deleting objects
        # Use through model to delete efficiently without loading all games
        models.Game.studios.through.objects.all().delete()
        models.Game.genres.through.objects.all().delete()

        # Delete all IGDB metadata
        models.IGDBGameData.objects.all().delete()

        # Delete derived data (Company, Studio, IGDBGenre)
        models.Company.objects.all().delete()
        models.Studio.objects.all().delete()
        models.IGDBGenre.objects.all().delete()

    return (
        True,
        f"Cleared {igdb_count} IGDB records, {company_count} companies, "
        f"{studio_count} studios, {genre_count} genres",
    )


def clear_wikipedia_metadata() -> Tuple[bool, str]:
    """
    Delete all Wikipedia metadata records and derived data (both connected and orphaned).

    Returns:
        Tuple of (success, message)
    """
    with transaction.atomic():
        # Count records before deletion
        wiki_count = models.WikipediaGameData.objects.count()
        genre_count = models.WikipediaGenre.objects.count()

        # Clear primary relationships on games
        models.Game.objects.update(primary_wikipedia_game_data=None)

        # Clear M2M relationships before deleting objects
        # Use through model to delete efficiently without loading all games
        models.Game.wikipedia_genres.through.objects.all().delete()

        # Delete all Wikipedia metadata
        models.WikipediaGameData.objects.all().delete()

        # Delete derived data (WikipediaGenre)
        models.WikipediaGenre.objects.all().delete()

    return (
        True,
        f"Cleared {wiki_count} Wikipedia records, {genre_count} genres",
    )


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
            if (
                progress_callback
                and row_number % config.IMPORT_PROGRESS_INTERVAL_LISTS == 0
            ):
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
    batch_size = config.IMPORT_BATCH_SIZE

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
            if (
                progress_callback
                and row_number % config.IMPORT_PROGRESS_INTERVAL_MEMBERSHIPS == 0
            ):
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
    rank, name, year, platforms (comma-separated codes), IGDB id, Wikidata id.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
                          Signature: callback(event_type: str, data: Dict)
                          Events: start, progress, error, complete
    """
    # Import here to avoid circular import
    from games.services.ranking_service import update_year_decade_ranks

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
        for rank, game_name, year, platforms, igdb_id, wikidata_id in rows:
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

            # Handle Wikidata ID (take first if multiple, strip whitespace)
            wikidata_value = None
            if wikidata_id and wikidata_id.strip():
                # Split by comma and take first ID only
                wikidata_value = wikidata_id.split(",")[0].strip()

            game, created = models.Game.objects.update_or_create(
                igdb_id=igdb_id,
                defaults={
                    "rank": int(rank),
                    "name": game_name,
                    "year_of_release": year,
                    "wikidata_id": wikidata_value,
                },
            )
            game.platforms.set(platform_objs)

            # Reconnect to existing IGDB/Wikipedia metadata if not already connected
            # This handles both orphaned metadata (game=None) and metadata still
            # linked to this game but not set as primary
            needs_save = False
            update_fields = []

            # Reconnect IGDB data if available and not already linked
            if igdb_id and not game.primary_igdb_game_data:
                # Look for orphaned metadata (game=None) or metadata for this game
                igdb_data = (
                    models.IGDBGameData.objects.filter(igdb_id=igdb_id, is_primary=True)
                    .filter(Q(game__isnull=True) | Q(game=game))
                    .first()
                )
                if igdb_data:
                    # Reconnect to game
                    igdb_data.game = game
                    igdb_data.save(update_fields=["game"])
                    game.primary_igdb_game_data = igdb_data
                    update_fields.append("primary_igdb_game_data")
                    needs_save = True

            # Reconnect Wikipedia data if available and not already linked
            if wikidata_value and not game.primary_wikipedia_game_data:
                # Look for orphaned metadata (game=None) or metadata for this game
                wiki_data = (
                    models.WikipediaGameData.objects.filter(
                        wikidata_id=wikidata_value, is_primary=True
                    )
                    .filter(Q(game__isnull=True) | Q(game=game))
                    .first()
                )
                if wiki_data:
                    # Reconnect to game
                    wiki_data.game = game
                    wiki_data.save(update_fields=["game"])
                    game.primary_wikipedia_game_data = wiki_data
                    update_fields.append("primary_wikipedia_game_data")
                    needs_save = True

            # Save if we reconnected any metadata
            if needs_save:
                game.save(update_fields=update_fields)

            if created:
                count += 1
            else:
                updated += 1

            # Report progress
            if (
                progress_callback
                and row_number % config.IMPORT_PROGRESS_INTERVAL_GAMES == 0
            ):
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
            if (
                progress_callback
                and row_number % config.IMPORT_PROGRESS_INTERVAL_PLATFORMS == 0
            ):
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

        company, created = models.Company.objects.get_or_create(
            name=canonical,
        )

        for alias in [alias1, alias2]:
            if not alias:
                continue

            models.Studio.objects.get_or_create(
                name=alias,
                defaults={
                    "company": company,
                },
            )

        if created:
            count += 1
        else:
            updated += 1

    return (True, f"Developers: {count} created, {updated} updated")

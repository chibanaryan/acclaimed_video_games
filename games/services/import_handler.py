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
from games.services.genre_normalizer import get_or_create_genre, normalize_genre


def import_data(data: Dict[str, Any]) -> Optional[Tuple[bool, str]]:
    """
    Route posted form data to the correct import helper.
    Handles both legacy single-file imports and new batch imports.
    """

    # Uploaded batch files replace ranking data in a single transaction and take
    # precedence over maintenance flags that may also be present in the POST body.
    if any(
        [
            data.get(f)
            for f in ["platforms_file", "lists_file", "games_file", "memberships_file"]
        ]
    ):
        success, message = import_batch(data)
        return (success, message)

    if data.get("delete"):
        return delete_existing_data()

    if data.get("clear_igdb_metadata"):
        return clear_igdb_metadata()

    if data.get("clear_wikipedia_metadata"):
        return clear_wikipedia_metadata()

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
        update_relationships: If True, update Developer/Genre relationships
            for games that already have IGDB metadata, without modifying the
            metadata records. Used after re-importing games.
    """
    import json
    import queue
    import threading

    from games import igdb
    from games.services.igdb_importer import IGDBImportService

    # Use a bounded queue to prevent unbounded memory growth if the client is slow/disconnects
    event_queue = queue.Queue(maxsize=1000)

    # Event to signal when client disconnects
    stop_event = threading.Event()

    def _queue_event(payload) -> None:
        """Best-effort enqueue that drops oldest events if the queue is full."""
        if stop_event.is_set():
            return
        try:
            event_queue.put_nowait(payload)
        except queue.Full:
            try:
                event_queue.get_nowait()
            except queue.Empty:
                return
            try:
                event_queue.put_nowait(payload)
            except queue.Full:
                return

    def progress_callback(event_type: str, data: dict) -> None:  # pragma: no cover
        """Callback to stream service events to SSE client."""
        # Add event type if not already present
        if "event" not in data:
            data["event"] = event_type
        # Queue the event for immediate streaming
        _queue_event(json.dumps(data))

    try:
        if update_relationships:
            # Update relationships for games with existing IGDB data
            games = models.Game.objects.filter(
                primary_igdb_game_data__isnull=False
            ).order_by("rank")

            total_games = games.count()
            if total_games == 0:
                _queue_event(
                    json.dumps(
                        {"event": "error", "error": "No games with IGDB data found"}
                    )
                )
                _queue_event(None)
            else:
                # Run relationship update in a thread
                def run_update():
                    try:
                        api_client = igdb.get_api()
                        if not api_client:
                            _queue_event(
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
                        _queue_event(json.dumps({"event": "error", "error": str(e)}))
                    finally:
                        _queue_event(None)

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
                    _queue_event(json.dumps({"event": "error", "error": str(e)}))
                finally:
                    # Signal that we're done
                    _queue_event(None)

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

    # Use a bounded queue to prevent unbounded memory growth if the client is slow/disconnects
    event_queue = queue.Queue(maxsize=1000)

    # Event to signal when client disconnects
    stop_event = threading.Event()

    def _queue_event(payload) -> None:
        """Best-effort enqueue that drops oldest events if the queue is full."""
        if stop_event.is_set():
            return
        try:
            event_queue.put_nowait(payload)
        except queue.Full:
            try:
                event_queue.get_nowait()
            except queue.Empty:
                return
            try:
                event_queue.put_nowait(payload)
            except queue.Full:
                return

    def progress_callback(event_type: str, data: dict) -> None:  # pragma: no cover
        """Callback to stream service events to SSE client."""
        # Add event type if not already present
        if "event" not in data:
            data["event"] = event_type

        # Queue the event for immediate streaming
        _queue_event(json.dumps(data))

    # Initialize services to None for safe cleanup in finally block
    service = None
    genre_service = None

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
                                    # Store all genres as comma-separated string
                                    if capitalized_all:
                                        wiki_game_data.all_genres = ", ".join(
                                            capitalized_all
                                        )
                                    wiki_game_data.save(
                                        update_fields=["primary_genre", "all_genres"]
                                    )

                                    # Create WikipediaGenre objects and link to game
                                    if capitalized_all:
                                        wikipedia_genres = []
                                        seen_genres = set()

                                        for genre_name in capitalized_all:
                                            # Normalize the genre name to canonical form
                                            normalized_name = normalize_genre(
                                                genre_name
                                            )

                                            # Skip None (invalid genres) and duplicates
                                            if normalized_name is None:
                                                continue
                                            if normalized_name in seen_genres:
                                                continue
                                            seen_genres.add(normalized_name)

                                            # Get or create the normalized genre with hierarchy
                                            genre = get_or_create_genre(normalized_name)
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
                _queue_event(json.dumps({"event": "error", "error": str(e)}))
            finally:
                # Clean up services to release HTTP sessions
                if service:
                    service.close()
                if genre_service:
                    genre_service.close()
                # Signal that we're done
                _queue_event(None)

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

    # Use a bounded queue to prevent unbounded memory growth if the client is slow/disconnects
    event_queue = queue.Queue(maxsize=1000)

    # Event to signal when client disconnects
    stop_event = threading.Event()

    def _queue_event(payload) -> None:
        """Best-effort enqueue that drops oldest events if the queue is full."""
        if stop_event.is_set():
            return
        try:
            event_queue.put_nowait(payload)
        except queue.Full:
            try:
                event_queue.get_nowait()
            except queue.Empty:
                return
            try:
                event_queue.put_nowait(payload)
            except queue.Full:
                return

    def progress_callback(event_type: str, data: dict) -> None:
        """Callback to stream service events to SSE client."""
        # Add event type if not already present
        if "event" not in data:
            data["event"] = event_type
        # Queue the event for immediate streaming
        _queue_event(json.dumps(data))

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
                        # Best-effort cancellation between files if client disconnects.
                        if stop_event.is_set():
                            raise RuntimeError("Import canceled: client disconnected")
                        file_obj = data.get(field_name)
                        if not file_obj:
                            continue

                        # Validate prerequisites
                        validation_error = _validate_prerequisites(
                            display_name.upper().replace(" ", "_")
                        )
                        if validation_error:
                            _queue_event(
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
                            _queue_event(
                                json.dumps(
                                    {
                                        "event": "error",
                                        "file": display_name,
                                        "message": str(e),
                                    }
                                )
                            )

            except Exception as e:  # pragma: no cover
                _queue_event(json.dumps({"event": "error", "message": str(e)}))
            finally:
                # Signal that we're done
                _queue_event(None)

        import_thread = threading.Thread(target=run_import, daemon=True)
        import_thread.start()

        # Stream events as they come in from the queue
        try:
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
        except GeneratorExit:  # pragma: no cover
            stop_event.set()
            raise

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
        return (True, summary)

    except Exception as e:
        return (False, f"Import transaction failed: {e}")


def delete_existing_data() -> Tuple[bool, str]:
    """
    Delete all game-related data from the database.

    Deletes: Games, Lists, ListMemberships, Publications, Developers, Series,
             IGDBGameData, Platform.
    Preserves (orphaned): WikipediaGameData, HLTBGameData, WikipediaGenre.
    """
    models_to_delete = [
        models.List,
        models.Publication,
        models.ListMembership,
        models.Game,
        models.Developer,
        models.Series,
        models.IGDBGameData,
        models.Platform,
    ]

    with transaction.atomic():
        # Orphan metadata records before deleting games
        # This preserves Wikipedia and HLTB data for reconnection on re-import
        models.WikipediaGameData.objects.all().update(game=None)
        models.HLTBGameData.objects.all().update(game=None)

        # Clear primary IGDB relationship before deleting IGDBGameData
        models.Game.objects.update(primary_igdb_game_data=None)

        # Clear M2M relationships before deleting Developer, Series, Platform
        models.Game.developers.through.objects.all().delete()
        models.Game.series.through.objects.all().delete()
        models.Game.platforms.through.objects.all().delete()

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

    This clears all IGDBGameData records and removes Developer and Series
    objects since they are derived from IGDB data.

    Returns:
        Tuple of (success, message)
    """
    with transaction.atomic():
        # Count records before deletion
        igdb_count = models.IGDBGameData.objects.count()
        developer_count = models.Developer.objects.count()
        series_count = models.Series.objects.count()

        # Clear primary relationships on games
        models.Game.objects.update(primary_igdb_game_data=None)

        # Clear M2M relationships before deleting objects
        # Use through model to delete efficiently without loading all games
        models.Game.developers.through.objects.all().delete()
        models.Game.series.through.objects.all().delete()

        # Delete all IGDB metadata
        models.IGDBGameData.objects.all().delete()

        # Delete derived data (Developer, Series)
        models.Developer.objects.all().delete()
        models.Series.objects.all().delete()

    return (
        True,
        f"Cleared {igdb_count} IGDB records, {developer_count} developers, "
        f"{series_count} series",
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

    Deletes all existing lists and publications, then creates fresh ones
    from the import file.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
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
        # Delete all existing lists and publications before importing
        lists_deleted = models.List.objects.count()
        pubs_deleted = models.Publication.objects.count()
        models.List.objects.all().delete()
        models.Publication.objects.all().delete()

        for line_number, bits in enumerate(rows):
            row_number += 1
            publisher_name, year, type, name, url = bits
            publisher, _ = models.Publication.objects.get_or_create(
                name=publisher_name,
            )

            models.List.objects.create(
                publisher=publisher,
                year=year,
                name=name,
                order=line_number + 1,
                url=url,
                type=type[0],
            )
            count += 1

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
            progress_callback(
                "complete",
                {
                    "count": count,
                    "lists_deleted": lists_deleted,
                    "publications_deleted": pubs_deleted,
                },
            )

        return (
            True,
            f"Lists: {count} created (deleted {lists_deleted} old); "
            f"Publications: recreated (deleted {pubs_deleted} old)",
        )

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

    Deletes all existing games and creates fresh ones. Orphans user tracking
    (PlayedGame/WantToPlayGame) and metadata (Wikipedia/HLTB) before deleting,
    then reconnects them after creating new games.

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
        # Delete all existing games first
        # Orphan user tracking and metadata so they can be reconnected
        deleted_count = models.Game.objects.count()
        models.PlayedGame.objects.all().update(game=None)
        models.WantToPlayGame.objects.all().update(game=None)
        models.WikipediaGameData.objects.all().update(game=None)
        models.HLTBGameData.objects.all().update(game=None)
        models.IGDBGameData.objects.all().update(game=None)
        models.Game.objects.all().delete()

        for rank, game_name, year, platforms, igdb_id, wikidata_id in rows:
            row_number += 1
            platform_codes = platforms.split(",")
            platform_objs = []
            for code in platform_codes:
                code = code.strip()
                platform, _ = models.Platform.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": code,
                    },
                )
                platform_objs.append(platform)

            # Parse comma-separated IGDB IDs (first is primary)
            all_igdb_ids = []
            if igdb_id and igdb_id.strip():
                all_igdb_ids = [
                    int(x.strip())
                    for x in igdb_id.split(",")
                    if x.strip() and x.strip().isdigit()
                ]
            primary_igdb_id = all_igdb_ids[0] if all_igdb_ids else None

            # Parse comma-separated Wikidata IDs (first is primary)
            all_wikidata_ids = []
            if wikidata_id and wikidata_id.strip():
                all_wikidata_ids = [
                    x.strip() for x in wikidata_id.split(",") if x.strip()
                ]
            primary_wikidata_id = all_wikidata_ids[0] if all_wikidata_ids else None

            # Create game
            game = models.Game.objects.create(
                igdb_id=primary_igdb_id,
                rank=int(rank),
                name=game_name,
                year_of_release=year,
                wikidata_id=primary_wikidata_id,
                all_igdb_ids=all_igdb_ids,
                all_wikidata_ids=all_wikidata_ids,
            )
            game.platforms.set(platform_objs)
            count += 1

            # Reconnect orphaned PlayedGame and WantToPlayGame records
            # This also normalizes igdb_id to primary and handles duplicates
            if all_igdb_ids:
                from games.services.user_tracking_service import (
                    reconnect_tracking_records,
                )

                reconnect_tracking_records(
                    game=game,
                    igdb_ids=all_igdb_ids,
                    primary_igdb_id=primary_igdb_id,
                )

            # Reconnect to existing Wikipedia/HLTB metadata
            update_fields = []
            needs_save = False

            # Reconnect Wikipedia data - try all Wikidata IDs (primary first)
            if all_wikidata_ids:
                for wikidata_id_to_try in all_wikidata_ids:
                    wiki_data = models.WikipediaGameData.objects.filter(
                        wikidata_id=wikidata_id_to_try,
                        is_primary=True,
                        game__isnull=True,
                    ).first()
                    if wiki_data:
                        wiki_data.game = game
                        wiki_data.save(update_fields=["game"])
                        game.primary_wikipedia_game_data = wiki_data
                        update_fields.append("primary_wikipedia_game_data")
                        needs_save = True

                        # Restore wikipedia_genres from stored all_genres
                        if wiki_data.all_genres:
                            genre_names = [
                                g.strip() for g in wiki_data.all_genres.split(",")
                            ]
                            wikipedia_genres = []
                            seen_genres = set()
                            for genre_name in genre_names:
                                normalized = normalize_genre(genre_name)
                                if normalized is None or normalized in seen_genres:
                                    continue
                                seen_genres.add(normalized)
                                genre = get_or_create_genre(normalized)
                                wikipedia_genres.append(genre)
                            if wikipedia_genres:
                                game.wikipedia_genres.set(wikipedia_genres)
                        break

            # Reconnect HLTB data - try all IGDB IDs
            if all_igdb_ids:
                for igdb_id_to_try in all_igdb_ids:
                    hltb_data = models.HLTBGameData.objects.filter(
                        igdb_id=igdb_id_to_try, is_primary=True, game__isnull=True
                    ).first()
                    if hltb_data:
                        hltb_data.game = game
                        hltb_data.save(update_fields=["game"])
                        game.primary_hltb_game_data = hltb_data
                        update_fields.append("primary_hltb_game_data")
                        needs_save = True
                        break

            # Reconnect IGDB data - try all IGDB IDs (primary first)
            if all_igdb_ids:
                for igdb_id_to_try in all_igdb_ids:
                    igdb_data = models.IGDBGameData.objects.filter(
                        igdb_id=igdb_id_to_try, is_primary=True, game__isnull=True
                    ).first()
                    if igdb_data:
                        igdb_data.game = game
                        igdb_data.save(update_fields=["game"])
                        game.primary_igdb_game_data = igdb_data
                        update_fields.append("primary_igdb_game_data")
                        needs_save = True
                        break

            if needs_save:
                game.save(update_fields=update_fields)

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
                    "deleted": deleted_count,
                    "ranks_updated": games_ranked,
                },
            )

        return (
            True,
            f"Games: {count} created (deleted {deleted_count} old), "
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

    Updates existing platforms, creates new ones, and deletes platforms not in the import.
    Preserves year_start and year_end fields for existing platforms.

    Args:
        f: File object to read from
        progress_callback: Optional callback for progress updates
    """
    rows = csv.reader(f, delimiter="\t", lineterminator="\r\n")
    count = 0
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
        # Get existing platforms to preserve year_start/year_end
        existing_platforms = {p.code: p for p in models.Platform.objects.all()}
        imported_codes = set()

        for code, name in rows:
            row_number += 1
            code = code.strip()
            name = name.strip()
            imported_codes.add(code)

            # Update or create platform, preserving year_start/year_end
            platform, created = models.Platform.objects.get_or_create(
                code=code, defaults={"name": name}
            )
            if not created and platform.name != name:
                # Update name if changed
                platform.name = name
                platform.save(update_fields=["name"])
            count += 1

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

        # Delete platforms that are no longer in the import file
        deleted_count = 0
        for code, platform in existing_platforms.items():
            if code not in imported_codes:
                # Clear M2M relationships before deleting
                platform.games.clear()
                platform.delete()
                deleted_count += 1

        # Calculate statistics
        created_count = count - (len(existing_platforms) - deleted_count)
        updated_count = count - created_count

        if progress_callback:
            progress_callback(
                "complete",
                {
                    "count": count,
                    "created": created_count,
                    "updated": updated_count,
                    "deleted": deleted_count,
                },
            )

        return (
            True,
            f"Platforms: {created_count} created, {updated_count} updated (deleted {deleted_count} old)",
        )

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

        # Create root developer (canonical name)
        root_dev, created = models.Developer.objects.get_or_create(
            name=canonical,
            parent__isnull=True,
            defaults={"slug": None},  # Will be set via admin or IGDB
        )

        # Create alias developers as subsidiaries
        for alias in [alias1, alias2]:
            if not alias or alias == canonical:
                continue

            models.Developer.objects.get_or_create(
                name=alias,
                parent=root_dev,
            )

        if created:
            count += 1
        else:
            updated += 1

    return (True, f"Developers: {count} created, {updated} updated")

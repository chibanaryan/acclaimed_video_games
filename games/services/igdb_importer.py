"""
Shared IGDB import service for both management commands and web views.
Provides concurrent, batched IGDB data fetching with progress callbacks.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple

from django.db import IntegrityError
from django.utils.text import slugify

from games.igdb import get_api
from games.models import Developer, DeveloperAlias, Game, Genre


class IGDBImportService:
    """
    Service class for importing IGDB data with optimizations.
    Supports concurrent + batched processing with progress callbacks.

    Supports three execution modes (in priority order):
    1. Batching: Fetch multiple games per API request (fastest)
    2. Concurrent: Process multiple games simultaneously using ThreadPoolExecutor
    3. Sequential: Process one game at a time (slowest, compatibility mode)
    """

    def __init__(
        self,
        concurrency: int = 8,
        batch_size: Optional[int] = None,
        use_pro_tier: Optional[bool] = None,
        progress_callback: Optional[Callable[[str, Dict], None]] = None,
    ):
        """
        Initialize the IGDB import service.

        Args:
            concurrency: Number of concurrent workers (1-8, default: 8)
            batch_size: Games per API batch (auto from tier if None, default: 50 free, 500 Pro)
            use_pro_tier: Use Pro tier (reads from settings if None)
            progress_callback: Optional callback for progress updates
                              Signature: callback(event_type: str, data: Dict)
                              Events: start, progress, error, complete
        """
        # Initialize API client early to determine tier and batch size
        self.api_client = get_api(use_pro_tier=use_pro_tier)
        if not self.api_client:
            raise RuntimeError("Failed to initialize IGDB API client")

        # Validate and set concurrency
        self.concurrency = max(1, min(8, concurrency))

        # Auto-detect batch_size from tier if not explicitly set
        if batch_size is None:
            self.batch_size = self.api_client.max_batch_size
        else:
            # User explicitly set it, respect their choice but cap at tier limit
            self.batch_size = max(0, min(self.api_client.max_batch_size, batch_size))

        self.progress_callback = progress_callback

        # Thread-safe counters
        self.lock = threading.Lock()
        self.processed_count = 0
        self.error_count = 0

    def import_games(self, games_queryset) -> Tuple[int, int, float]:
        """
        Import IGDB data for games with optimizations.

        Automatically chooses execution mode:
        1. If batch_size > 0: Uses batching (fastest)
        2. Else if concurrency > 1: Uses concurrent processing
        3. Else: Uses sequential processing

        Args:
            games_queryset: QuerySet of Game objects to process

        Returns:
            Tuple of (processed_count, error_count, elapsed_seconds)
        """
        games_list = list(games_queryset)
        total_games = len(games_list)

        if total_games == 0:
            self._notify_progress("error", {"message": "No games found in database"})
            return (0, 0, 0.0)

        self.processed_count = 0
        self.error_count = 0
        start_time = time.time()

        # Notify start
        self._notify_progress("start", {"total": total_games})

        # Choose execution mode
        if self.batch_size > 0:
            self._import_batched(games_list, total_games, start_time)
        elif self.concurrency > 1:
            self._import_concurrent(games_list, total_games, start_time)
        else:
            self._import_sequential(games_list, total_games, start_time)

        elapsed = time.time() - start_time

        # Notify completion
        self._notify_progress(
            "complete",
            {
                "total": total_games,
                "processed": self.processed_count,
                "errors": self.error_count,
                "elapsed_seconds": int(elapsed),
            },
        )

        return (self.processed_count, self.error_count, elapsed)

    def _import_batched(self, games_list: List[Game], total_games: int, start_time: float) -> None:
        """
        Import games using multi-query batching (fastest mode).

        Fetches multiple games per API request.
        """
        batch_processed = 0

        for batch_idx in range(0, len(games_list), self.batch_size):
            batch = games_list[batch_idx : batch_idx + self.batch_size]
            batch_results = self._process_game_batch(batch)

            for success, game, error_msg in batch_results:
                current = self.processed_count + self.error_count + 1
                elapsed = time.time() - start_time

                if success:
                    self._notify_progress(
                        "progress",
                        {
                            "current": current,
                            "total": total_games,
                            "game_name": game.name,
                            "percentage": int((current / total_games) * 100),
                            "elapsed_seconds": int(elapsed),
                            "remaining_seconds": self._estimate_remaining(
                                current, total_games, elapsed
                            ),
                        },
                    )
                else:
                    self._notify_progress(
                        "error",
                        {
                            "current": current,
                            "game_name": game.name,
                            "message": error_msg,
                        },
                    )

                batch_processed += 1

    def _import_concurrent(self, games_list: List[Game], total_games: int, start_time: float) -> None:
        """
        Import games using concurrent processing (fast mode).

        Uses ThreadPoolExecutor to process multiple games simultaneously.
        """
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            future_to_game = {
                executor.submit(self._process_game, game): (idx, game)
                for idx, game in enumerate(games_list, 1)
            }

            for future in as_completed(future_to_game):
                idx, original_game = future_to_game[future]
                success, game, error_msg = future.result()
                current = self.processed_count + self.error_count
                elapsed = time.time() - start_time

                if success:
                    self._notify_progress(
                        "progress",
                        {
                            "current": current,
                            "total": total_games,
                            "game_name": game.name,
                            "percentage": int((current / total_games) * 100),
                            "elapsed_seconds": int(elapsed),
                            "remaining_seconds": self._estimate_remaining(
                                current, total_games, elapsed
                            ),
                        },
                    )
                else:
                    self._notify_progress(
                        "error",
                        {
                            "current": current,
                            "game_name": game.name,
                            "message": error_msg,
                        },
                    )

    def _import_sequential(self, games_list: List[Game], total_games: int, start_time: float) -> None:
        """
        Import games sequentially (compatibility mode, slowest).

        Processes one game at a time. Used when concurrency=1 and batch_size=0.
        """
        for idx, game in enumerate(games_list, 1):
            success, game, error_msg = self._process_game(game)
            elapsed = time.time() - start_time

            if success:
                self._notify_progress(
                    "progress",
                    {
                        "current": idx,
                        "total": total_games,
                        "game_name": game.name,
                        "percentage": int((idx / total_games) * 100),
                        "elapsed_seconds": int(elapsed),
                        "remaining_seconds": self._estimate_remaining(idx, total_games, elapsed),
                    },
                )
            else:
                self._notify_progress(
                    "error",
                    {
                        "current": idx,
                        "game_name": game.name,
                        "message": error_msg,
                    },
                )

    def _process_game(self, game: Game) -> Tuple[bool, Game, Optional[str]]:
        """
        Process a single game by fetching IGDB data.

        Returns:
            Tuple of (success: bool, game: Game, error_msg: Optional[str])
        """
        try:
            game.get_igdb_data()
            game.save(
                update_fields=["slug", "igdb_url", "igdb_artwork_id", "description"]
            )
            with self.lock:
                self.processed_count += 1
            return (True, game, None)
        except Exception as e:
            with self.lock:
                self.error_count += 1
            return (False, game, str(e))

    def _process_game_batch(self, games_batch: List[Game]) -> List[Tuple[bool, Game, Optional[str]]]:
        """
        Process a batch of games using multi-query.

        Fetches multiple games in a single API request.

        Args:
            games_batch: List of Game objects to process

        Returns:
            List of (success, game, error_msg) tuples
        """
        results = []

        # Get IGDB IDs for games that have them
        game_id_map = {}
        for game in games_batch:
            if game.igdb_id:
                game_id_map[game.igdb_id] = game

        if not game_id_map:
            # No games with IGDB IDs in this batch
            for game in games_batch:
                with self.lock:
                    self.error_count += 1
                results.append((False, game, "No IGDB ID"))
            return results

        # Batch fetch game data
        try:
            games_data = self.api_client.get_games_info_by_ids(list(game_id_map.keys()))

            # Apply data to each game
            for igdb_id, game in game_id_map.items():
                if igdb_id in games_data:
                    try:
                        # Apply IGDB data to game (same logic as Game.get_igdb_data())
                        data = games_data[igdb_id]
                        game.slug = slugify(data.get("slug"))
                        game.igdb_url = data.get("url")
                        game.igdb_artwork_id = data.get("cover")
                        game.description = "\n\n".join(
                            [
                                x
                                for x in [data.get("storyline"), data.get("summary")]
                                if x
                            ]
                        )

                        # Process developers
                        developer_aliases = []
                        for d in data.get("developers", []):
                            # This developer is a parent
                            if not d.get("parent"):
                                developer, created = Developer.objects.update_or_create(
                                    name=d["name"],
                                    defaults={
                                        "slug": d["slug"],
                                        "igdb_id": d["id"],
                                    },
                                )
                            # This developer has a parent
                            else:
                                parent_obj = d.get("parent")
                                if parent_obj:
                                    developer, created = (
                                        Developer.objects.update_or_create(
                                            name=parent_obj["name"],
                                            defaults={
                                                "slug": parent_obj["slug"],
                                                "igdb_id": parent_obj["id"],
                                            },
                                        )
                                    )
                                    # Ensure parent has an alias too
                                    try:
                                        DeveloperAlias.objects.update_or_create(
                                            developer=developer,
                                            name=parent_obj["name"],
                                            defaults={
                                                "igdb_id": parent_obj["id"],
                                            },
                                        )
                                    except IntegrityError:
                                        pass

                            try:
                                developer_alias, created = (
                                    DeveloperAlias.objects.update_or_create(
                                        developer=developer,
                                        name=d["name"],
                                        defaults={
                                            "igdb_id": d["id"],
                                        },
                                    )
                                )
                            except IntegrityError:
                                developer_alias = DeveloperAlias.objects.get(
                                    name=d["name"]
                                )

                            developer_aliases.append(developer_alias)

                        game.developers.set(developer_aliases)

                        # Process genres
                        genres = []
                        for genre_name in data.get("genres", []):
                            genre, created = Genre.objects.get_or_create(
                                name=genre_name
                            )
                            genres.append(genre)
                        game.genres.set(genres)

                        game.save(
                            update_fields=[
                                "slug",
                                "igdb_url",
                                "igdb_artwork_id",
                                "description",
                            ]
                        )

                        with self.lock:
                            self.processed_count += 1
                        results.append((True, game, None))
                    except Exception as e:
                        with self.lock:
                            self.error_count += 1
                        results.append((False, game, str(e)))
                else:
                    with self.lock:
                        self.error_count += 1
                    results.append((False, game, "Not found in IGDB response"))

        except Exception as e:
            # Batch fetch failed, mark all as errors
            for game in games_batch:
                with self.lock:
                    self.error_count += 1
                results.append((False, game, f"Batch fetch failed: {str(e)}"))

        return results

    def _estimate_remaining(self, current: int, total: int, elapsed: float) -> int:
        """Estimate remaining seconds based on current rate."""
        if elapsed <= 0:
            return 0
        rate = current / elapsed
        remaining_games = total - current
        remaining_seconds = remaining_games / rate if rate > 0 else 0
        return int(remaining_seconds)

    def _notify_progress(self, event_type: str, data: Dict) -> None:
        """Call progress callback if provided."""
        if self.progress_callback:
            self.progress_callback(event_type, data)

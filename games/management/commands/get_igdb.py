import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand

from games.models import Game
from games.igdb import get_api

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch game data from IGDB"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_lock = threading.Lock()
        self.processed_count = 0
        self.error_count = 0

    def _process_game(self, game):
        """
        Process a single game by fetching IGDB data.

        Returns:
            tuple: (success: bool, game: Game, error_msg: str or None)
        """
        try:
            game.get_igdb_data()
            game.save(
                update_fields=["slug", "igdb_url", "igdb_artwork_id", "description"]
            )
            with self.processed_lock:
                self.processed_count += 1
            return (True, game, None)
        except Exception as e:
            with self.processed_lock:
                self.error_count += 1
            return (False, game, str(e))

    def _process_game_batch(self, games_batch, api_client):
        """
        Process a batch of games using multi-query.

        Args:
            games_batch: List of Game objects to process
            api_client: IGDB API client instance

        Returns:
            list: List of (success, game, error_msg) tuples
        """
        from games.models import Developer, DeveloperAlias, Genre
        from django.utils.text import slugify
        from django.db import IntegrityError

        results = []

        # Get IGDB IDs for games that have them
        game_id_map = {}
        for game in games_batch:
            if game.igdb_id:
                game_id_map[game.igdb_id] = game

        if not game_id_map:
            # No games with IGDB IDs in this batch
            for game in games_batch:
                results.append((False, game, "No IGDB ID"))
            return results

        # Batch fetch game data
        try:
            games_data = api_client.get_games_info_by_ids(list(game_id_map.keys()))

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

                        with self.processed_lock:
                            self.processed_count += 1
                        results.append((True, game, None))
                    except Exception as e:
                        with self.processed_lock:
                            self.error_count += 1
                        results.append((False, game, str(e)))
                else:
                    with self.processed_lock:
                        self.error_count += 1
                    results.append((False, game, "Not found in IGDB response"))

        except Exception as e:
            # Batch fetch failed, mark all as errors
            for game in games_batch:
                with self.processed_lock:
                    self.error_count += 1
                results.append((False, game, f"Batch fetch failed: {str(e)}"))

        return results

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help=(
                "Additional delay in seconds between processing games "
                "(default: 0.0s). Rate limiting is automatically handled "
                "by the API client. Only increase this if you need extra "
                "throttling."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Number of games to process before a longer pause (default: 50). "
            "Helps with memory management and provides progress checkpoints.",
        )
        parser.add_argument(
            "--game",
            type=str,
            help="Update specific game by name (case-insensitive)",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Update specific game by slug",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Update specific game by database ID",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh even if game already has IGDB artwork data",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=8,
            help="Number of concurrent requests to make (default: 8, max: 8). "
            "IGDB allows up to 8 concurrent requests. Set to 1 to disable.",
        )
        parser.add_argument(
            "--batch-games",
            type=int,
            default=None,
            help=(
                "Batch size for multi-query mode (default: auto - 50 for free "
                "tier, 500 for Pro). Fetches multiple games per API request. "
                "Set to 0 to disable batching."
            ),
        )
        parser.add_argument(
            "--pro",
            action="store_true",
            help=(
                "Use IGDB Pro tier (3000 req/sec vs 4 req/sec). "
                "Requires Pro tier subscription. Can also set "
                "IGDB_USE_PRO_TIER=True in .env"
            ),
        )

    def handle(self, *args, **options):
        delay = options.get("delay", 0.0)
        batch_size = options.get("batch_size", 50)
        game_name = options.get("game")
        game_slug = options.get("slug")
        game_id = options.get("id")
        force = options.get("force", False)
        concurrency = max(1, min(8, options.get("concurrency", 8)))
        use_pro_tier = options.get("pro", False)

        # Initialize API client early to determine tier and batch size
        api_client = get_api(use_pro_tier=use_pro_tier)
        if not api_client:
            self.stdout.write(
                self.style.ERROR("Failed to initialize IGDB API client")
            )
            return

        # Auto-detect batch_games from tier if not explicitly set
        batch_games_option = options.get("batch_games")
        if batch_games_option is None:
            # Use tier's maximum batch size for optimal performance
            batch_games = api_client.max_batch_size
        else:
            # User explicitly set it, respect their choice but cap at tier limit
            batch_games = max(0, min(api_client.max_batch_size, batch_games_option))

        # Handle single game update
        if game_name or game_slug or game_id:
            try:
                if game_id:
                    game = Game.objects.get(id=game_id)
                elif game_slug:
                    game = Game.objects.get(slug=game_slug)
                elif game_name:
                    game = Game.objects.get(name__iexact=game_name)

                self.stdout.write(f"Updating game: {game.rank}. {game.name}")

                if not game.igdb_id:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Game '{game.name}' has no IGDB ID. Cannot fetch data."
                        )
                    )
                    return

                if game.igdb_artwork_id and not force:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Game '{game.name}' already has IGDB data. "
                            "Use --force to refresh."
                        )
                    )
                    return

                game.get_igdb_data()
                game.save(
                    update_fields=["slug", "igdb_url", "igdb_artwork_id", "description"]
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully updated '{game.name}'")
                )
                return

            except Game.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"Game not found with "
                        f"{'id=' + str(game_id) if game_id else ''}"
                        f"{'slug=' + game_slug if game_slug else ''}"
                        f"{'name=' + game_name if game_name else ''}"
                    )
                )
                return
            except Game.MultipleObjectsReturned:
                self.stdout.write(
                    self.style.ERROR(
                        f"Multiple games found matching '{game_name}'. "
                        "Please use --slug or --id instead."
                    )
                )
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error updating game: {str(e)}"))
                return

        # Handle batch update (original behavior)
        if force:
            games = Game.objects.exclude(igdb_id__isnull=True)
        else:
            games = Game.objects.filter(igdb_artwork_id__isnull=True)

        total_games = games.count()

        if total_games == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No games to fetch. All games already have IGDB data."
                )
            )
            return

        # Show tier being used
        tier_name = "Pro" if api_client.use_pro_tier else "Free"
        self.stdout.write(f"Using IGDB {tier_name} tier")

        mode_desc = []
        if batch_games > 0:
            mode_desc.append(f"batch_games={batch_games}")
        if concurrency > 1:
            mode_desc.append(f"concurrency={concurrency}")
        if delay > 0:
            mode_desc.append(f"delay={delay}s")
        mode_desc.append(f"checkpoint_size={batch_size}")

        self.stdout.write(f"Processing {total_games} games ({', '.join(mode_desc)})")

        self.processed_count = 0
        self.error_count = 0
        batch_processed = 0
        start_time = time.time()

        # Batch games mode - fetch multiple games per API request
        if batch_games > 0:
            games_list = list(games)
            total_batches = (len(games_list) + batch_games - 1) // batch_games

            for batch_idx in range(0, len(games_list), batch_games):
                batch = games_list[batch_idx : batch_idx + batch_games]
                current_batch_num = (batch_idx // batch_games) + 1

                self.stdout.write(
                    f"\nProcessing batch {current_batch_num}/{total_batches} "
                    f"({len(batch)} games)..."
                )

                batch_results = self._process_game_batch(batch, api_client)

                for success, game, error_msg in batch_results:
                    completed = self.processed_count + self.error_count
                    if success:
                        self.stdout.write(
                            f"[{completed}/{total_games}] {game.rank} - {game} updated"
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"[{completed}/{total_games}] "
                                f"{game.rank} - {game}: {error_msg}"
                            )
                        )

                    batch_processed += 1

                    # Checkpoint
                    if batch_processed >= batch_size:
                        elapsed = time.time() - start_time
                        completed = self.processed_count + self.error_count
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = total_games - completed
                        eta = remaining / rate if rate > 0 else 0
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Checkpoint: {self.processed_count}/{total_games} "
                                f"processed ({self.error_count} errors, "
                                f"{rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                            )
                        )
                        batch_processed = 0

        elif concurrency > 1:
            # Concurrent processing with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                # Submit all games as futures
                future_to_game = {
                    executor.submit(self._process_game, game): (idx, game)
                    for idx, game in enumerate(games, 1)
                }

                # Process completed futures as they finish
                for future in as_completed(future_to_game):
                    idx, original_game = future_to_game[future]
                    success, game, error_msg = future.result()

                    if success:
                        self.stdout.write(
                            f"[{self.processed_count}/{total_games}] "
                            f"{game.rank} - {game} updated"
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"[{self.processed_count + self.error_count}/"
                                f"{total_games}] {game.rank} - {game}: {error_msg}"
                            )
                        )

                    batch_processed += 1

                    # Batch checkpoint
                    if batch_processed >= batch_size:
                        elapsed = time.time() - start_time
                        completed = self.processed_count + self.error_count
                        rate = completed / elapsed if elapsed > 0 else 0
                        remaining = total_games - completed
                        eta = remaining / rate if rate > 0 else 0
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Checkpoint: {self.processed_count}/{total_games} "
                                f"processed ({self.error_count} errors, "
                                f"{rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                            )
                        )
                        batch_processed = 0

        else:
            # Sequential processing (original behavior)
            for idx, game in enumerate(games, 1):
                success, game, error_msg = self._process_game(game)

                if success:
                    self.stdout.write(
                        f"[{idx}/{total_games}] {game.rank} - {game} updated"
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[{idx}/{total_games}] {game.rank} - {game}: {error_msg}"
                        )
                    )

                batch_processed += 1

                # Batch checkpoint
                if batch_processed >= batch_size:
                    elapsed = time.time() - start_time
                    rate = self.processed_count / elapsed if elapsed > 0 else 0
                    remaining = total_games - idx
                    eta = remaining / rate if rate > 0 else 0
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Batch complete: {self.processed_count}/{total_games} "
                            f"processed ({self.error_count} errors, "
                            f"{rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                        )
                    )
                    batch_processed = 0

                # Delay between games (only for sequential mode)
                if delay > 0:
                    time.sleep(delay)

        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: {self.processed_count}/{total_games} games "
                f"processed successfully ({self.error_count} errors) "
                f"in {elapsed:.1f}s ({self.processed_count/elapsed:.2f} games/sec)"
            )
        )

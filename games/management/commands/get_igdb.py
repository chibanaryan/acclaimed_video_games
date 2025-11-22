import logging
import time

from django.core.management.base import BaseCommand

from games.models import Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch game data from IGDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Delay in seconds between processing games (default: 0.5s). "
            "Helps avoid rate limiting. Set to 0 to disable.",
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

    def handle(self, *args, **options):
        delay = options.get("delay", 0.5)
        batch_size = options.get("batch_size", 50)
        game_name = options.get("game")
        game_slug = options.get("slug")
        game_id = options.get("id")
        force = options.get("force", False)

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
                game.save()
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

        self.stdout.write(
            f"Processing {total_games} games (delay={delay}s, batch_size={batch_size})"
        )

        processed = 0
        batch_processed = 0
        start_time = time.time()

        for idx, game in enumerate(games, 1):
            try:
                game.get_igdb_data()
                game.save()
                processed += 1
                batch_processed += 1

                # Progress output
                self.stdout.write(f"[{idx}/{total_games}] {game.rank} - {game} updated")

                # Batch checkpoint
                if batch_processed >= batch_size:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = total_games - idx
                    eta = remaining / rate if rate > 0 else 0
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Batch complete: {processed}/{total_games} processed "
                            f"({rate:.2f} games/sec, ~{eta:.0f}s remaining)"
                        )
                    )
                    batch_processed = 0

                # Delay between games to respect rate limiting
                if delay > 0:
                    time.sleep(delay)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"[{idx}/{total_games}] {game.rank} - {game}: {str(e)}"
                    )
                )

        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted: {processed}/{total_games} games "
                f"processed in {elapsed:.1f}s"
            )
        )

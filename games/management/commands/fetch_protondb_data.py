"""
Management command to fetch ProtonDB Steam Deck compatibility data for games.

Uses the ProtonDB API to retrieve compatibility tier ratings for games
that have Steam AppIDs stored in WikipediaGameData.
"""

import asyncio
import logging
import time

import aiohttp
from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand

from games.models import Game, ProtonDBGameData

logger = logging.getLogger(__name__)

# ProtonDB API endpoint
PROTONDB_API_URL = (
    "https://www.protondb.com/api/v1/reports/summaries/{steam_app_id}.json"
)


class Command(BaseCommand):
    help = "Fetch ProtonDB Steam Deck compatibility data for games"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--game",
            type=str,
            help="Process specific game by name (case-insensitive)",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Process specific game by slug",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Process specific game by database ID",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of games to process",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Skip first N games (default: 0)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Delay between requests in seconds (default: 0.5)",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=5,
            help="Number of concurrent requests (default: 5)",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results to database (default: console only)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip games that already have ProtonDB data",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh all games (ignore existing data)",
        )

    def handle(self, *args, **options):
        self.start_time = time.time()

        # Get games to process
        games = self._get_games(options)

        if not games:
            self.stdout.write(self.style.ERROR("No games with Steam AppIDs found"))
            return

        game_count = len(games)
        self.stdout.write(f"\nProcessing {game_count} games with Steam AppIDs...")
        self.stdout.write(
            f"Concurrency: {options['concurrency']}, Delay: {options['delay']}s\n"
        )

        # Run async fetch
        success, failed, not_found = asyncio.run(self._async_fetch(games, options))

        # Summary
        elapsed = time.time() - self.start_time
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\nCompleted in {elapsed:.1f} seconds"))
        self.stdout.write(f"Total games processed: {game_count}")
        self.stdout.write(self.style.SUCCESS(f"ProtonDB data found: {success}"))
        if not_found > 0:
            self.stdout.write(self.style.WARNING(f"Not on ProtonDB: {not_found}"))
        if failed > 0:
            self.stdout.write(self.style.ERROR(f"Fetch errors: {failed}"))

        if options.get("save") and success > 0:
            self.stdout.write(self.style.SUCCESS("\n✓ Results saved to database"))

    def _get_games(self, options):
        """Get list of games with Steam AppIDs to process."""
        # Start with games that have Steam AppIDs in WikipediaGameData
        games_qs = (
            Game.objects.filter(primary_wikipedia_game_data__steam_app_id__isnull=False)
            .exclude(primary_wikipedia_game_data__steam_app_id="")
            .select_related(
                "primary_wikipedia_game_data",
                "primary_protondb_game_data",
            )
            .order_by("rank")
        )

        # Apply filters
        if options.get("game"):
            games_qs = games_qs.filter(name__iexact=options["game"])
        if options.get("slug"):
            games_qs = games_qs.filter(slug=options["slug"])
        if options.get("id"):
            games_qs = games_qs.filter(id=options["id"])

        # Skip existing (unless force)
        if options.get("skip_existing") and not options.get("force"):
            games_qs = games_qs.filter(primary_protondb_game_data__isnull=True)

        # Apply offset and limit
        if options.get("offset"):
            games_qs = games_qs[options["offset"] :]
        if options.get("limit"):
            games_qs = games_qs[: options["limit"]]

        # Convert to list with needed data
        games = []
        for game in games_qs:
            games.append(
                {
                    "id": game.id,
                    "igdb_id": game.igdb_id,
                    "name": game.name,
                    "steam_app_id": game.primary_wikipedia_game_data.steam_app_id,
                }
            )

        return games

    async def _async_fetch(self, games, options):
        """Async fetch ProtonDB data for all games."""
        delay = options.get("delay", 0.5)
        concurrency = options.get("concurrency", 5)
        save = options.get("save", False)

        semaphore = asyncio.Semaphore(concurrency)
        success = 0
        failed = 0
        not_found = 0
        total = len(games)

        async with aiohttp.ClientSession() as session:
            tasks = []
            for idx, game in enumerate(games, start=1):
                tasks.append(
                    self._fetch_game(session, semaphore, game, idx, total, delay, save)
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                elif result == "success":
                    success += 1
                elif result == "not_found":
                    not_found += 1
                else:
                    failed += 1

        return success, failed, not_found

    async def _fetch_game(self, session, semaphore, game, idx, total, delay, save):
        """Fetch ProtonDB data for a single game."""
        async with semaphore:
            steam_app_id = game["steam_app_id"]
            url = PROTONDB_API_URL.format(steam_app_id=steam_app_id)

            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        tier = data.get("tier", "pending")
                        trending_tier = data.get("trendingTier")
                        # ProtonDB returns total (count of reports)
                        report_count = data.get("total", 0)

                        # Format tier display
                        tier_display = tier.capitalize()
                        if tier in ("platinum", "gold"):
                            tier_display = self.style.SUCCESS(tier_display)
                        elif tier in ("silver", "bronze"):
                            tier_display = self.style.WARNING(tier_display)
                        elif tier == "borked":
                            tier_display = self.style.ERROR(tier_display)

                        self.stdout.write(
                            f"[{idx}/{total}] ✓ {game['name']}: {tier_display}"
                        )

                        if save:
                            await sync_to_async(self._save_protondb_data)(
                                game, steam_app_id, tier, trending_tier, report_count
                            )
                        return "success"

                    elif response.status == 404:
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{idx}/{total}] ✗ {game['name']}: Not on ProtonDB"
                            )
                        )
                        return "not_found"
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"[{idx}/{total}] ✗ {game['name']}: HTTP {response.status}"
                            )
                        )
                        return "error"

            except asyncio.TimeoutError:
                self.stdout.write(
                    self.style.ERROR(f"[{idx}/{total}] ✗ {game['name']}: Timeout")
                )
                return "error"
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{idx}/{total}] ✗ {game['name']}: {e}")
                )
                return "error"
            finally:
                await asyncio.sleep(delay)

    def _save_protondb_data(
        self, game, steam_app_id, tier, trending_tier, report_count
    ):
        """Save ProtonDB data to database."""
        game_obj = Game.objects.get(id=game["id"])

        # Unset existing primary
        ProtonDBGameData.objects.filter(game=game_obj, is_primary=True).update(
            is_primary=False
        )

        # Create or update
        protondb_data, created = ProtonDBGameData.objects.update_or_create(
            game=game_obj,
            steam_app_id=steam_app_id,
            defaults={
                "igdb_id": game["igdb_id"],
                "tier": tier,
                "trending_tier": trending_tier,
                "report_count": report_count,
                "is_primary": True,
            },
        )

        # Set as primary on game
        game_obj.primary_protondb_game_data = protondb_data
        game_obj.save(update_fields=["primary_protondb_game_data"])

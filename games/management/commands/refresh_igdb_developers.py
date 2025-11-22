import logging

from django.core.management.base import BaseCommand

from games.models import Game

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh IGDB data for games with missing developer information"

    def add_arguments(self, parser):
        parser.add_argument(
            "--game-id",
            type=int,
            help="Refresh IGDB data for a specific game ID",
        )
        parser.add_argument(
            "--game-slug",
            type=str,
            help="Refresh IGDB data for a specific game slug",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Refresh IGDB data for all games regardless of developer data",
        )

    def handle(self, *args, **kwargs):
        game_id = kwargs.get("game_id")
        game_slug = kwargs.get("game_slug")
        refresh_all = kwargs.get("all", False)

        # Determine which games to refresh
        if game_id:
            games = Game.objects.filter(id=game_id)
            if not games.exists():
                self.stdout.write(self.style.ERROR(f"No game found with ID {game_id}"))
                return
        elif game_slug:
            games = Game.objects.filter(slug=game_slug)
            if not games.exists():
                self.stdout.write(
                    self.style.ERROR(f"No game found with slug {game_slug}")
                )
                return
        elif refresh_all:
            # Refresh all games with IGDB IDs
            games = Game.objects.filter(igdb_id__isnull=False)
        else:
            # Find games with IGDB IDs but missing developer IGDB data
            games = (
                Game.objects.filter(igdb_id__isnull=False)
                .exclude(developers__igdb_id__isnull=False)
                .distinct()
            )

        total = games.count()
        self.stdout.write(self.style.SUCCESS(f"Found {total} games to refresh"))

        success_count = 0
        error_count = 0

        for i, game in enumerate(games, 1):
            try:
                game.get_igdb_data(cache_results=False)
                game.save()

                # Check if developers were added
                dev_count = game.developers.filter(igdb_id__isnull=False).count()

                status = f"{game.rank} - {game}"
                if dev_count > 0:
                    status += f" ({dev_count} developers with IGDB data)"

                self.stdout.write(self.style.SUCCESS(f"[{i}/{total}] {status}"))
                success_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{i}/{total}] {game.rank} - {game}: {str(e)}")
                )
                error_count += 1
                logger.error(f"{game.rank} - {game}: {str(e)}")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Completed: {success_count} successful, {error_count} failed"
            )
        )

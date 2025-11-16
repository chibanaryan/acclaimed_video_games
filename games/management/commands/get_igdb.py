from django.core.management.base import BaseCommand

from games.models import Game


class Command(BaseCommand):
    help = "Fetch game data from IGDB"

    def handle(self, *args, **kwargs):
        for game in Game.objects.filter(igdb_artwork_id__isnull=True):
            try:
                game.get_igdb_data()
                game.save()
                print(f"{game.rank} - {game} updated")
            except Exception as e:
                print(str(e))

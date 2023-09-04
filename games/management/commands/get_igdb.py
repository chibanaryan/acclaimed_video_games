
from django.core.management.base import BaseCommand

from games.models import Game
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetch game data from IGDB'

    def handle(self, *args, **kwargs):
        for game in Game.objects.all():
            try:
                game.get_igdb_data()
                game.save()
                logger.info(f'{game} updated')
            except Exception as e:
                logger.error(str(e))

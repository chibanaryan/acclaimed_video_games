from ..models import Game
import csv


def run(*args):
    txt_path = args[0]
    rows = csv.reader(open(txt_path), delimiter='\t', lineterminator='\r\n')
    for rank, name, year in rows:
        game, _ = Game.objects.update_or_create(
            name=name,
            year_of_release=int(year),
            defaults={
                'rank': int(rank)
            }
        )
        print(game)

from .. import models
import csv

# 1	The Legend of Zelda: Breath of the Wild	2017	Nintendo	WiiU,SW


def run(*args):
    txt_path = args[0]
    rows = csv.reader(open(txt_path), delimiter='\t', lineterminator='\r\n')
    for rank, game_name, year, developers, platforms in rows:
        developer_names = developers.split(',')
        platform_codes = platforms.split(',')

        developer_aliases = []
        for name in developer_names:
            try:
                developer_alias = models.DeveloperAlias.objects.get(
                    name=name
                )
            except models.DeveloperAlias.DoesNotExist:
                developer, created = models.Developer.objects.get_or_create(
                    name=name
                )
                developer_alias = models.DeveloperAlias.objects.create(
                    developer=developer,
                    name=name
                )

            developer_aliases.append(developer_alias)

        platforms = []
        for code in platform_codes:
            platform, created = models.Platform.objects.get_or_create(
                code=code,
                defaults={
                    'name': code,
                }
            )
            platforms.append(platform)

        game, _ = models.Game.objects.update_or_create(
            name=game_name,
            year_of_release=int(year),
            defaults={
                'rank': int(rank)
            }
        )
        game.developers.set(developer_aliases)
        game.platforms.set(platforms)

        print(game)

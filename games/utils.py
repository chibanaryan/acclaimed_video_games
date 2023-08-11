import csv
from io import TextIOWrapper

from django.db import connection

from . import constants, models


def import_data(data):

    if data.get('delete'):
        return delete_existing_data()

    if data.get('file'):
        f = TextIOWrapper(data['file'], encoding='utf-8')
        import_type = data['type']

        functions = {
            constants.TYPE_GAME: import_games,
            constants.TYPE_PLATFORM: import_platforms,
            constants.TYPE_LIST: import_lists,
            constants.TYPE_LIST_MEMBERSHIP: import_listmemberships,
            constants.TYPE_DEVELOPER: import_developers,
        }

        try:
            return functions.get(import_type)(f)
        except Exception as e:
            return (False, f"Could not process uploaded file: {e}")


def delete_existing_data():

    models_to_delete = [
        models.Platform,
        models.List,
        models.Publication,
        models.ListMembership,
        models.Developer,
        models.DeveloperAlias,
        models.Game,
    ]

    # Delete objects
    total = 0
    for model in models_to_delete:
        count, _ = model.objects.all().delete()
        total += count

    # Reset id sequences
    with connection.cursor() as cursor:
        for model in models_to_delete:
            cursor.execute(
                f'ALTER SEQUENCE {model._meta.db_table}_id_seq RESTART WITH 1;')

    return (True, f'{total} objects deleted')


def import_lists(f):

    rows = csv.reader(f, delimiter='\t', lineterminator='\r\n')
    count = 0
    updated = 0

    for line_number, bits in enumerate(rows):
        publisher_name, year, type, name, url = bits
        publisher, created = models.Publication.objects.get_or_create(
            name=publisher_name,
        )

        list, created = models.List.objects.get_or_create(
            publisher=publisher,
            year=year,
            name=name,
            order=line_number + 1,
            defaults={
                'url': url,
                'type': type[0],
            }
        )

        if created:
            count += 1
        else:
            updated += 1

    return (True, f'Lists: {count} created, {updated} updated')


def import_listmemberships(f):

    list_map = {x.order: x for x in models.List.objects.all()}
    memberships = []

    for line_number, line in enumerate(f):
        bits = line.strip().split('\t')
        game = models.Game.objects.get(rank=line_number + 1)
        for bit in bits:
            list_id, position = [int(x) for x in bit.split(':')]

            source_list = list_map.get(list_id + 1)
            if not source_list:
                continue

            memberships.append(
                models.ListMembership(
                    list=source_list, game=game, rank=position)
            )

    objects = models.ListMembership.objects.bulk_create(memberships)

    return (True, f'List memberships: {len(objects)} created')


def import_games(f):

    rows = csv.reader(f, delimiter='\t', lineterminator='\r\n')
    count = 0
    updated = 0

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

        game, created = models.Game.objects.update_or_create(
            name=game_name,
            year_of_release=int(year),
            defaults={
                'rank': int(rank)
            }
        )
        game.developers.set(developer_aliases)
        game.platforms.set(platforms)

        if created:
            count += 1
        else:
            updated += 1

    return (True, f'Games: {count} created, {updated} updated')


def import_platforms(f):

    rows = csv.reader(f, delimiter='\t', lineterminator='\r\n')
    count = 0
    updated = 0

    for code, name in rows:
        platform, created = models.Platform.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
            }
        )

        if created:
            count += 1

        if created:
            count += 1
        else:
            updated += 1

    return (True, f'Platforms: {count} created, {updated} updated')


def import_developers(f):

    rows = csv.reader(f, delimiter='\t', lineterminator='\r\n')
    count = 0
    updated = 0

    for bits in rows:
        alias1 = bits[0]
        canonical = bits[1]
        alias2 = None
        if len(bits) == 3:
            alias2 = bits[2]

        developer, created = models.Developer.objects.get_or_create(
            name=canonical,
        )

        for alias in [alias1, alias2]:
            if not alias:
                continue

            models.DeveloperAlias.objects.get_or_create(
                name=alias,
                defaults={
                    'developer': developer,
                }
            )

        if created:
            count += 1
        else:
            updated += 1

    return (True, f'Developers: {count} created, {updated} updated')

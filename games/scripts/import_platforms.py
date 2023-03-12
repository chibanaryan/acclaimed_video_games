from .. import models
import csv

# 3DS	Nintendo 3DS


def run(*args):
    txt_path = args[0]
    rows = csv.reader(open(txt_path), delimiter='\t', lineterminator='\r\n')
    for code, name in rows:
        platform, created = models.Platform.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
            }
        )
        print(platform)
        
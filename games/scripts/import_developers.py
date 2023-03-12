from .. import models
import csv

# 1-Up Studio	1-Up Studio	Brownie Brown


def run(*args):
    txt_path = args[0]
    rows = csv.reader(open(txt_path), delimiter='\t', lineterminator='\r\n')
    for bits in rows:
        alias1 = bits[0]
        canonical = bits[1]
        alias2 = None
        if len(bits) == 3:
            alias2 = bits[2]

        developer, created = models.Developer.objects.get_or_create(
            name=canonical,
        )

        if created:
            print(developer)

        for alias in [alias1, alias2]:
            if not alias:
                continue

            models.DeveloperAlias.objects.get_or_create(
                name=alias,
                defaults={
                    'developer': developer,
                }
            )

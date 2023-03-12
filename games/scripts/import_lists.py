from .. import models
import csv

#Ars Technica	2001	EOY	The first annual Game.Ars Über Game of the Year Awards (2000)	https://arstechnica.com/gaming/2001/01/gars-01092001/


def run(*args):
    txt_path = args[0]
    rows = csv.reader(open(txt_path), delimiter='\t', lineterminator='\r\n')
    for publisher_name, year, _, name, url in rows:
        publisher, created = models.Publication.objects.get_or_create(
            name=publisher_name,
        )

        list, created = models.List.objects.get_or_create(
            publisher=publisher,
            year=year,
            name=name,
            url=url,
        )

        print(list)
        
"""
Data migration: Create "Tactical First-Person Shooter" genre under Shooter
and reassign Counter-Strike games from "Tactical Shooter" to it.
"""

from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    Game = apps.get_model("games", "Game")

    # Ensure Shooter parent exists
    try:
        shooter = WikipediaGenre.objects.get(name="Shooter")
    except WikipediaGenre.DoesNotExist:
        return

    # Create the new genre
    tactical_fps, created = WikipediaGenre.objects.get_or_create(
        name="Tactical First-Person Shooter",
        defaults={
            "slug": slugify("Tactical First-Person Shooter"),
            "parent": shooter,
            "level": 1,
            "path": "Shooter > Tactical First-Person Shooter",
        },
    )

    # Reassign CS games from Tactical Shooter to Tactical First-Person Shooter
    try:
        tactical_shooter = WikipediaGenre.objects.get(name="Tactical Shooter")
    except WikipediaGenre.DoesNotExist:
        return

    cs_names = [
        "Counter-Strike / Counter-Strike 1.6",
        "Counter-Strike: Global Offensive",
        "Counter-Strike: Source",
    ]
    for game in Game.objects.filter(
        name__in=cs_names, wikipedia_genres=tactical_shooter
    ):
        game.wikipedia_genres.remove(tactical_shooter)
        game.wikipedia_genres.add(tactical_fps)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0096_remove_tactical_genre"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

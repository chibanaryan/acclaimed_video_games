"""
Data migration: Merge "Tactical First-Person Shooter" back into
"Tactical Shooter" and delete the redundant genre.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    Game = apps.get_model("games", "Game")

    try:
        tactical_fps = WikipediaGenre.objects.get(name="Tactical First-Person Shooter")
    except WikipediaGenre.DoesNotExist:
        return

    tactical_shooter = WikipediaGenre.objects.get(name="Tactical Shooter")

    for game in Game.objects.filter(wikipedia_genres=tactical_fps):
        game.wikipedia_genres.remove(tactical_fps)
        game.wikipedia_genres.add(tactical_shooter)

    tactical_fps.delete()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0097_add_tactical_fps_genre"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

"""
Data migration: Remove "Tactical" genre (under Strategy) and reassign
Counter-Strike games to "Tactical Shooter" (under Shooter).

The "Tactical" genre was created from Wikipedia's split rendering of
"Tactical first-person shooter" into two separate <a> tags. Only 3
Counter-Strike games ever had this genre.
"""

from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    try:
        tactical = WikipediaGenre.objects.get(name="Tactical")
    except WikipediaGenre.DoesNotExist:
        return

    # Ensure "Tactical Shooter" exists (it should already)
    tactical_shooter, _ = WikipediaGenre.objects.get_or_create(
        name="Tactical Shooter",
        defaults={
            "slug": slugify("Tactical Shooter"),
            "parent": WikipediaGenre.objects.get(name="Shooter"),
            "level": 1,
            "path": "Shooter > Tactical Shooter",
        },
    )

    # Move games from Tactical to Tactical Shooter
    Game = apps.get_model("games", "Game")
    for game in Game.objects.filter(wikipedia_genres=tactical):
        game.wikipedia_genres.remove(tactical)
        game.wikipedia_genres.add(tactical_shooter)

    # Delete the Tactical genre
    tactical.delete()


def backwards(apps, schema_editor):
    # No reverse needed - re-running Wikipedia fetch would recreate if needed
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0095_alter_list_name_alter_publication_name_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

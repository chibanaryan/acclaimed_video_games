"""
Data migration to rename Puzzle Platformer to Puzzle-Platformer.

Fixes hyphenation to be consistent with other compound genres (Action-Adventure, etc.).
"""

import sys

from django.db import migrations
from django.utils.text import slugify

TEST_MODE = "test" in sys.argv


def forward_migration(apps, schema_editor):
    """Rename Puzzle Platformer to Puzzle-Platformer."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    try:
        genre = WikipediaGenre.objects.get(name="Puzzle Platformer")
        genre.name = "Puzzle-Platformer"
        genre.slug = slugify("Puzzle-Platformer")
        genre.path = "Puzzle > Puzzle-Platformer"
        genre.save()
        if not TEST_MODE:
            print("Renamed 'Puzzle Platformer' to 'Puzzle-Platformer'")
    except WikipediaGenre.DoesNotExist:
        # Genre doesn't exist yet or already renamed
        pass


def reverse_migration(apps, schema_editor):
    """Revert to Puzzle Platformer."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    try:
        genre = WikipediaGenre.objects.get(name="Puzzle-Platformer")
        genre.name = "Puzzle Platformer"
        genre.slug = slugify("Puzzle Platformer")
        genre.path = "Puzzle > Puzzle Platformer"
        genre.save()
        if not TEST_MODE:
            print("Reverted 'Puzzle-Platformer' to 'Puzzle Platformer'")
    except WikipediaGenre.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0088_reparent_genre_hierarchy"),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_migration),
    ]

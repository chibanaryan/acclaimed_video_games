"""
Data migration to add Driving and Space Simulation genres.

- Driving: separate from Racing for truck sims, etc. (Euro Truck Simulator)
- Space Simulation: separate from Space Combat for exploration/trading (Elite Dangerous)
"""

import sys

from django.db import migrations
from django.utils.text import slugify

TEST_MODE = "test" in sys.argv

NEW_GENRES = [
    ("Driving", "Simulation"),
    ("Space Simulation", "Simulation"),
]


def forward_migration(apps, schema_editor):
    """Create new genres."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    try:
        simulation = WikipediaGenre.objects.get(name="Simulation", parent=None)
    except WikipediaGenre.DoesNotExist:
        if not TEST_MODE:
            print("Warning: Simulation parent genre not found")
        return

    for genre_name, parent_name in NEW_GENRES:
        genre, created = WikipediaGenre.objects.get_or_create(
            name=genre_name,
            defaults={
                "slug": slugify(genre_name),
                "parent": simulation,
                "level": 1,
                "path": f"Simulation > {genre_name}",
                "display_order": 0,
            },
        )
        if created and not TEST_MODE:
            print(f"Created '{genre_name}' under Simulation")


def reverse_migration(apps, schema_editor):
    """Remove new genres."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    for genre_name, _ in NEW_GENRES:
        WikipediaGenre.objects.filter(name=genre_name).delete()
        if not TEST_MODE:
            print(f"Deleted '{genre_name}'")


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0089_rename_puzzle_platformer"),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_migration),
    ]

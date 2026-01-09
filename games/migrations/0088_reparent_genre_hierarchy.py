"""
Data migration to re-parent genres based on corrected categorizations.

This migration fixes genre categorizations:
- Maze: Puzzle → Action (arcade action games like Pac-Man)
- Platform: Adventure → Action (reflex-based gameplay)
- Metroidvania: Adventure → Action (action-exploration games)
- Racing: Simulation → Action (fast-paced arcade racing)
- Kart Racing: Simulation → Action (arcade racing like Mario Kart)
- Pinball: Simulation → Party & Casual (casual arcade game)
- Hack and Slash: NEW under Action (distinct from Beat 'em Up)
- Extreme Sports: NEW under Sports (distinct from Snowboarding)
"""

import sys

from django.db import migrations
from django.utils.text import slugify

# Suppress print statements during tests
TEST_MODE = "test" in sys.argv

# Genres to move: (genre_name, new_parent_name)
GENRES_TO_REPARENT = [
    ("Maze", "Action"),
    ("Platform", "Action"),
    ("Metroidvania", "Action"),
    ("Racing", "Action"),
    ("Kart Racing", "Action"),
    ("Pinball", "Party & Casual"),
]

# New genres to create: (genre_name, parent_name)
NEW_GENRES = [
    ("Hack and Slash", "Action"),
    ("Extreme Sports", "Sports"),
    ("Puzzle-Platformer", "Puzzle"),
]


def forward_migration(apps, schema_editor):
    """Re-parent genres to correct categories."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # Get parent genres
    parents = {}
    for parent_name in ["Action", "Sports", "Party & Casual", "Puzzle"]:
        try:
            parents[parent_name] = WikipediaGenre.objects.get(
                name=parent_name, parent=None
            )
        except WikipediaGenre.DoesNotExist:
            if not TEST_MODE:
                print(f"Warning: Parent genre '{parent_name}' not found")

    # Re-parent existing genres
    for genre_name, new_parent_name in GENRES_TO_REPARENT:
        try:
            genre = WikipediaGenre.objects.get(name=genre_name)
            new_parent = parents.get(new_parent_name)
            if new_parent:
                genre.parent = new_parent
                genre.level = 1
                genre.path = f"{new_parent_name} > {genre_name}"
                genre.save()
                if not TEST_MODE:
                    print(f"Re-parented '{genre_name}' → {new_parent_name}")
        except WikipediaGenre.DoesNotExist:
            if not TEST_MODE:
                print(f"Genre '{genre_name}' not found, skipping")

    # Create new genres
    for genre_name, parent_name in NEW_GENRES:
        parent = parents.get(parent_name)
        if parent:
            genre, created = WikipediaGenre.objects.get_or_create(
                name=genre_name,
                defaults={
                    "slug": slugify(genre_name),
                    "parent": parent,
                    "level": 1,
                    "path": f"{parent_name} > {genre_name}",
                    "display_order": 0,
                },
            )
            if created and not TEST_MODE:
                print(f"Created new genre '{genre_name}' under {parent_name}")
            elif not created:
                # Update existing genre if needed
                if genre.parent != parent:
                    genre.parent = parent
                    genre.level = 1
                    genre.path = f"{parent_name} > {genre_name}"
                    genre.save()
                    if not TEST_MODE:
                        print(f"Updated existing genre '{genre_name}' → {parent_name}")

    if not TEST_MODE:
        print("Genre hierarchy re-parenting complete!")


def reverse_migration(apps, schema_editor):
    """Revert genres to original parents (best effort)."""
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # Original parent mappings
    ORIGINAL_PARENTS = {
        "Maze": "Puzzle",
        "Platform": "Adventure",
        "Metroidvania": "Adventure",
        "Racing": "Simulation",
        "Kart Racing": "Simulation",
        "Pinball": "Simulation",
    }

    for genre_name, original_parent_name in ORIGINAL_PARENTS.items():
        try:
            genre = WikipediaGenre.objects.get(name=genre_name)
            original_parent = WikipediaGenre.objects.get(
                name=original_parent_name, parent=None
            )
            genre.parent = original_parent
            genre.level = 1
            genre.path = f"{original_parent_name} > {genre_name}"
            genre.save()
            if not TEST_MODE:
                print(f"Reverted '{genre_name}' → {original_parent_name}")
        except WikipediaGenre.DoesNotExist:
            if not TEST_MODE:
                print(f"Could not revert '{genre_name}'")

    # Delete new genres that were created
    for genre_name, _ in NEW_GENRES:
        WikipediaGenre.objects.filter(name=genre_name).delete()
        if not TEST_MODE:
            print(f"Deleted '{genre_name}'")


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0087_remove_list_media_type"),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_migration),
    ]

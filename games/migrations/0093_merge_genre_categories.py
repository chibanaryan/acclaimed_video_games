"""
Data migration to merge genre categories:
1. Racing + Sports → "Racing & Sports"
2. Puzzle + Party & Casual → "Puzzle & Casual"

This creates new parent categories and reparents existing genres as sub-genres.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # ============================================================
    # PART 1: Create "Racing & Sports" and merge Sports + Racing
    # ============================================================

    # Create new "Racing & Sports" root category
    sports_racing_root = WikipediaGenre.objects.create(
        name="Racing & Sports",
        slug="racing-sports",
        level=0,
        path="Racing & Sports",
        parent=None,
    )

    # Get existing Sports and Racing roots
    sports_root = WikipediaGenre.objects.filter(
        name="Sports", parent__isnull=True
    ).first()
    racing_root = WikipediaGenre.objects.filter(
        name="Racing", parent__isnull=True
    ).first()

    # Reparent Sports (was root) as sub-genre
    if sports_root:
        # First, move all Sports children to the new parent
        for child in WikipediaGenre.objects.filter(parent=sports_root):
            child.parent = sports_racing_root
            child.path = f"Racing & Sports > {child.name}"
            child.save()

        # Then make Sports itself a sub-genre
        sports_root.parent = sports_racing_root
        sports_root.level = 1
        sports_root.path = "Racing & Sports > Sports"
        sports_root.save()

    # Reparent Racing (was root) as sub-genre
    if racing_root:
        # First, move all Racing children to the new parent
        for child in WikipediaGenre.objects.filter(parent=racing_root):
            child.parent = sports_racing_root
            child.path = f"Racing & Sports > {child.name}"
            child.save()

        # Then make Racing itself a sub-genre
        racing_root.parent = sports_racing_root
        racing_root.level = 1
        racing_root.path = "Racing & Sports > Racing"
        racing_root.save()

    # ============================================================
    # PART 2: Create "Puzzle & Casual" and merge Puzzle + Party & Casual
    # ============================================================

    # Create new "Puzzle & Casual" root category
    puzzle_casual_root = WikipediaGenre.objects.create(
        name="Puzzle & Casual",
        slug="puzzle-casual",
        level=0,
        path="Puzzle & Casual",
        parent=None,
    )

    # Get existing Puzzle and Party & Casual roots
    puzzle_root = WikipediaGenre.objects.filter(
        name="Puzzle", parent__isnull=True
    ).first()
    party_casual_root = WikipediaGenre.objects.filter(
        name="Party & Casual", parent__isnull=True
    ).first()

    # Reparent Puzzle (was root) as sub-genre
    if puzzle_root:
        # First, move all Puzzle children to the new parent
        for child in WikipediaGenre.objects.filter(parent=puzzle_root):
            child.parent = puzzle_casual_root
            child.path = f"Puzzle & Casual > {child.name}"
            child.save()

        # Then make Puzzle itself a sub-genre
        puzzle_root.parent = puzzle_casual_root
        puzzle_root.level = 1
        puzzle_root.path = "Puzzle & Casual > Puzzle"
        puzzle_root.save()

    # Reparent Party & Casual children to new parent, then delete the old root
    if party_casual_root:
        # Move all Party & Casual children to the new parent
        for child in WikipediaGenre.objects.filter(parent=party_casual_root):
            child.parent = puzzle_casual_root
            child.path = f"Puzzle & Casual > {child.name}"
            child.save()

        # Delete the old "Party & Casual" root (it's now redundant)
        party_casual_root.delete()


def backwards(apps, schema_editor):
    """
    Reverse the migration - restore original category structure.
    """
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # ============================================================
    # Restore Sports and Racing as separate roots
    # ============================================================

    sports_racing_root = WikipediaGenre.objects.filter(
        name="Racing & Sports", parent__isnull=True
    ).first()

    if sports_racing_root:
        # Find Sports and Racing sub-genres
        sports = WikipediaGenre.objects.filter(
            name="Sports", parent=sports_racing_root
        ).first()
        racing = WikipediaGenre.objects.filter(
            name="Racing", parent=sports_racing_root
        ).first()

        # Promote Sports back to root
        if sports:
            sports.parent = None
            sports.level = 0
            sports.path = "Sports"
            sports.save()

            # Move sports-related children back under Sports
            for name in ["Football (American)", "Football (Association)", "Snowboarding"]:
                child = WikipediaGenre.objects.filter(
                    name=name, parent=sports_racing_root
                ).first()
                if child:
                    child.parent = sports
                    child.path = f"Sports > {name}"
                    child.save()

        # Promote Racing back to root
        if racing:
            racing.parent = None
            racing.level = 0
            racing.path = "Racing"
            racing.save()

            # Move racing-related children back under Racing
            kart_racing = WikipediaGenre.objects.filter(
                name="Kart Racing", parent=sports_racing_root
            ).first()
            if kart_racing:
                kart_racing.parent = racing
                kart_racing.path = "Racing > Kart Racing"
                kart_racing.save()

        # Delete Racing & Sports root
        sports_racing_root.delete()

    # ============================================================
    # Restore Puzzle and Party & Casual as separate roots
    # ============================================================

    puzzle_casual_root = WikipediaGenre.objects.filter(
        name="Puzzle & Casual", parent__isnull=True
    ).first()

    if puzzle_casual_root:
        # Find Puzzle sub-genre
        puzzle = WikipediaGenre.objects.filter(
            name="Puzzle", parent=puzzle_casual_root
        ).first()

        # Promote Puzzle back to root
        if puzzle:
            puzzle.parent = None
            puzzle.level = 0
            puzzle.path = "Puzzle"
            puzzle.save()

            # Move puzzle-related children back under Puzzle
            for name in ["Puzzle-Platformer", "Match-Three"]:
                child = WikipediaGenre.objects.filter(
                    name=name, parent=puzzle_casual_root
                ).first()
                if child:
                    child.parent = puzzle
                    child.path = f"Puzzle > {name}"
                    child.save()

        # Recreate Party & Casual as root
        party_casual_root_new = WikipediaGenre.objects.create(
            name="Party & Casual",
            slug="party-casual",
            level=0,
            path="Party & Casual",
            parent=None,
        )

        # Move casual-related children under Party & Casual
        for name in ["Party", "Music", "Educational"]:
            child = WikipediaGenre.objects.filter(
                name=name, parent=puzzle_casual_root
            ).first()
            if child:
                child.parent = party_casual_root_new
                child.path = f"Party & Casual > {name}"
                child.save()

        # Delete Puzzle & Casual root
        puzzle_casual_root.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0092_racing_category"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

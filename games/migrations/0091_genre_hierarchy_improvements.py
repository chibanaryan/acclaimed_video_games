"""
Data migration for genre hierarchy improvements:
1. Consolidate single-game genres (21 genres with only 1 game)
2. Create new Shooter category and move shooter genres from Action
3. Redistribute Hybrid & Specialized genres and delete the category
"""

from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    Game = apps.get_model("games", "Game")

    # Part 1: Consolidate single-game genres
    # These genres have only 1 game each, so we move games to parent and delete the genre
    consolidations = {
        "Casual": "Party & Casual",
        "Digital Card Game": "Party & Casual",
        "Exercise": "Party & Casual",
        "Pinball": "Party & Casual",
        "Social Deduction": "Party & Casual",
        "Location-Based": "Adventure",
        "Block Breaker": "Puzzle",
        "Incremental": "Puzzle",
        "Driving": "Simulation",
        "Business Simulation": "Simulation",
        "Vehicle Simulation": "Simulation",
        "Basketball": "Sports",
        "Baseball": "Sports",
        "Ice Hockey": "Sports",
        "Boxing": "Sports",
        "Sports Management": "Sports",
        "Extreme Sports": "Sports",
        "Escape Room": "Adventure",
        "Immersive Sim": "Adventure",
        "Dungeon Management": "Role-Playing",
        "Tower Defense": "Strategy",
    }

    for old_name, parent_name in consolidations.items():
        old_genre = WikipediaGenre.objects.filter(name=old_name).first()
        parent_genre = WikipediaGenre.objects.filter(
            name=parent_name, parent__isnull=True
        ).first()
        if old_genre and parent_genre:
            # Move games from old genre to parent
            for game in Game.objects.filter(wikipedia_genres=old_genre):
                game.wikipedia_genres.remove(old_genre)
                game.wikipedia_genres.add(parent_genre)
            # Delete the old genre
            old_genre.delete()

    # Part 2: Create/promote Shooter category and reparent shooter genres
    # The "Shooter" genre may already exist as a child - promote it to root
    shooter_root = WikipediaGenre.objects.filter(name="Shooter").first()
    if shooter_root:
        # Promote existing Shooter genre to root category
        shooter_root.parent = None
        shooter_root.level = 0
        shooter_root.path = "Shooter"
        shooter_root.save()
    else:
        # Create new Shooter root category
        shooter_root = WikipediaGenre.objects.create(
            name="Shooter",
            slug="shooter",
            level=0,
            path="Shooter",
            parent=None,
        )

    shooter_child_genres = [
        "First-Person Shooter",
        "Third-Person Shooter",
        "Light Gun Shooter",
        "Tactical Shooter",
        "Run and Gun",
    ]

    for genre_name in shooter_child_genres:
        genre = WikipediaGenre.objects.filter(name=genre_name).first()
        if genre:
            genre.parent = shooter_root
            genre.level = 1
            genre.path = f"Shooter > {genre.name}"
            genre.save()

    # Part 3: Redistribute Hybrid & Specialized genres to better-fitting categories
    redistributions = {
        "Horror": "Adventure",
        "Survival": "Action",
        "Sandbox": "Simulation",
        "Massively Multiplayer": "Role-Playing",
    }

    for genre_name, new_parent_name in redistributions.items():
        genre = WikipediaGenre.objects.filter(name=genre_name).first()
        new_parent = WikipediaGenre.objects.filter(
            name=new_parent_name, parent__isnull=True
        ).first()
        if genre and new_parent:
            genre.parent = new_parent
            genre.level = 1
            genre.path = f"{new_parent.name} > {genre.name}"
            genre.save()

    # Delete the empty Hybrid & Specialized category
    WikipediaGenre.objects.filter(name="Hybrid & Specialized").delete()


def backwards(apps, schema_editor):
    """
    Reverse the migration - recreate Hybrid & Specialized and move genres back.
    Note: This doesn't restore the deleted single-game genres.
    """
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # Recreate Hybrid & Specialized category
    hybrid_root = WikipediaGenre.objects.create(
        name="Hybrid & Specialized",
        slug="hybrid-specialized",
        level=0,
        path="Hybrid & Specialized",
        parent=None,
    )

    # Move genres back to Hybrid & Specialized
    reverse_redistributions = {
        "Horror": "Adventure",
        "Survival": "Action",
        "Sandbox": "Simulation",
        "Massively Multiplayer": "Role-Playing",
    }

    for genre_name in reverse_redistributions.keys():
        genre = WikipediaGenre.objects.filter(name=genre_name).first()
        if genre:
            genre.parent = hybrid_root
            genre.level = 1
            genre.path = f"Hybrid & Specialized > {genre.name}"
            genre.save()

    # Move shooter genres back to Action
    action_root = WikipediaGenre.objects.filter(
        name="Action", parent__isnull=True
    ).first()
    shooter_genres = [
        "First-Person Shooter",
        "Third-Person Shooter",
        "Shooter",
        "Light Gun Shooter",
        "Tactical Shooter",
        "Run and Gun",
    ]

    for genre_name in shooter_genres:
        genre = WikipediaGenre.objects.filter(name=genre_name).first()
        if genre and action_root:
            genre.parent = action_root
            genre.level = 1
            genre.path = f"Action > {genre.name}"
            genre.save()

    # Delete Shooter category
    WikipediaGenre.objects.filter(name="Shooter", parent__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0090_add_driving_space_simulation"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

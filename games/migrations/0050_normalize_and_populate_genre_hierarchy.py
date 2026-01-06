"""
Data migration to normalize existing Wikipedia genres and populate hierarchy.

This migration:
1. Normalizes existing WikipediaGenre records using GENRE_MAPPING
2. Consolidates duplicate genres (e.g., "MMORPG" and "Massively multiplayer...")
3. Updates Game.wikipedia_genres M2M relationships
4. Creates root categories and assigns genres to hierarchy
5. Populates slugs, paths, levels, and display_order for all genres
"""

import sys

from django.db import migrations
from django.utils.text import slugify

# Suppress print statements during tests
TEST_MODE = "test" in sys.argv


# Genre normalization mapping (imported from genre_normalizer.py concept)
GENRE_MAPPING = {
    # Action genres
    "Action": "Action",
    "Beat 'em up": "Beat 'em Up",
    "Beat em up": "Beat 'em Up",
    "Hack and slash": "Beat 'em Up",
    "Fighting": "Fighting",
    "First-person shooter": "First-Person Shooter",
    "First-person hero shooter": "First-Person Shooter",
    "Hero shooter": "First-Person Shooter",
    "Third-person shooter": "Third-Person Shooter",
    "Light gun shooter": "Light Gun Shooter",
    "Shooter": "Shooter",
    "Shoot 'em up": "Shooter",
    "Scrolling shooter": "Shooter",
    "Side-scrolling shooter": "Shooter",
    "Multi-directional shooter": "Shooter",
    "Multidirectional shooter": "Shooter",
    "Top-down shooter": "Shooter",
    "Twin-stick shooter": "Shooter",
    "Fixed shooter": "Shooter",
    "Rail shooter": "Shooter",
    "Tube shooter": "Shooter",
    "Run and gun": "Run and Gun",
    "Stealth": "Stealth",
    "Tactical shooter": "Tactical Shooter",
    "Battle royale": "Battle Royale",
    "Battle Royale": "Battle Royale",
    "MOBA": "MOBA",
    "Vehicular combat": "Vehicular Combat",
    # Adventure genres
    "Action-adventure": "Action-Adventure",
    "Action adventure": "Action-Adventure",
    "Action role-playing": "Action RPG",
    "Action RPG": "Action RPG",
    "Platform-adventure": "Action-Adventure",
    "Adventure": "Adventure",
    "Adventure game": "Adventure",
    "Point-and-click adventure": "Point-and-Click",
    "Point-and-click": "Point-and-Click",
    "Interactive drama": "Interactive Drama",
    "Interactive fiction": "Interactive Drama",
    "Interactive film": "Interactive Drama",
    "Interactive movie": "Interactive Drama",
    "Interactive novel": "Interactive Drama",
    "Visual novel": "Visual Novel",
    "Walking simulator": "Walking Simulator",
    "Escape the room": "Escape Room",
    "Metroidvania": "Metroidvania",
    "Dungeon crawl": "Dungeon Crawler",
    "Platform": "Platform",
    "Platformer": "Platform",
    "Platform game": "Platform",
    "Cinematic platform": "Platform",
    "Cinematic platformer": "Platform",
    "Puzzle-platform": "Platform",
    "Immersive sim": "Immersive Sim",
    # Role-playing genres
    "Role-playing": "Role-Playing",
    "RPG": "Role-Playing",
    "Tactical role-playing": "Tactical RPG",
    "Tactical RPG": "Tactical RPG",
    "MMORPG": "MMORPG",
    "Massively multiplayer online role-playing": "MMORPG",
    "Massively multiplayer online role-playing game": "MMORPG",
    "Roguelike": "Roguelike",
    "Roguelike deck-building": "Roguelike",
    "Dungeon management game": "Dungeon Management",
    # Strategy genres
    "Strategy": "Strategy",
    "Real-time strategy": "Real-Time Strategy",
    "Real-Time Strategy": "Real-Time Strategy",
    "RTS": "Real-Time Strategy",
    "Real-time tactics": "Real-Time Tactics",
    "Real-Time Tactics": "Real-Time Tactics",
    "Turn-based strategy": "Turn-Based Strategy",
    "Turn-Based Strategy": "Turn-Based Strategy",
    "TBS": "Turn-Based Strategy",
    "Turn-based tactics": "Turn-Based Tactics",
    "Turn-Based Tactics": "Turn-Based Tactics",
    "4X": "4X Strategy",
    "4X Strategy": "4X Strategy",
    "Grand strategy": "Grand Strategy",
    "Tower defense": "Tower Defense",
    "Tactical": "Tactical",
    # Simulation genres
    "Simulation": "Simulation",
    "Life simulation": "Life Simulation",
    "Business simulation": "Business Simulation",
    "Business simulation game": "Business Simulation",
    "City-building": "City Building",
    "City-building game": "City Building",
    "Construction and management sim": "Construction & Management",
    "Construction and management simulation": "Construction & Management",
    "Flight simulation": "Flight Simulation",
    "Amateur flight simulation": "Flight Simulation",
    "Arcade flight": "Flight Simulation",
    "Combat flight simulator": "Flight Simulation",
    "Space flight simulation": "Flight Simulation",
    "Space combat": "Space Combat",
    "Space combat simulation": "Space Combat",
    "Space combat simulator": "Space Combat",
    "Space simulation": "Space Combat",
    "Space trading and combat": "Space Combat",
    "Space trading and combat simulator": "Space Combat",
    "Vehicle simulation game": "Vehicle Simulation",
    "Driving": "Racing",
    "Racing": "Racing",
    "Sim racing": "Racing",
    "Racing simulation": "Racing",
    "Racing simulator": "Racing",
    "Simulation racing game": "Racing",
    "Kart racing": "Kart Racing",
    "Pinball": "Pinball",
    "Social simulation": "Life Simulation",
    "Social simulator": "Life Simulation",
    "Farm life sim": "Life Simulation",
    "Farm simulation": "Life Simulation",
    "God game": "God Game",
    # Sports genres
    "Sports": "Sports",
    "Sports game": "Sports",
    "American football": "Football (American)",
    "Football": "Football (American)",
    "Association football": "Football (Association)",
    "Basketball": "Basketball",
    "Baseball": "Baseball",
    "Ice hockey": "Ice Hockey",
    "Boxing": "Boxing",
    "Snowboarding": "Snowboarding",
    "Extreme sports": "Snowboarding",
    "Sports management": "Sports Management",
    # Puzzle genres
    "Puzzle": "Puzzle",
    "Match-three": "Match-Three",
    "Match three": "Match-Three",
    "Tile-matching": "Match-Three",
    "Block breaker": "Block Breaker",
    "Maze": "Maze",
    "Incremental": "Incremental",
    # Party & Casual genres
    "Party": "Party",
    "Music": "Music",
    "Rhythm": "Music",
    "Casual": "Casual",
    "Digital collectible card game": "Digital Card Game",
    "Educational": "Educational",
    "Edutainment": "Educational",
    "Exercise": "Exercise",
    # Hybrid & Specialized genres
    "Sandbox": "Sandbox",
    "Survival": "Survival",
    "Horror": "Horror",
    "Psychological horror": "Horror",
    "Survival horror": "Horror",
    "Massively multiplayer online": "Massively Multiplayer",
    "MMOG": "Massively Multiplayer",
    "MMO": "Massively Multiplayer",
    "Social deduction": "Social Deduction",
    "Location-based game": "Location-Based",
    # Party & Casual additions
    "Rhythm game": "Music",
    "Karaoke": "Music",
    # Additional adventure variants
    "Graphic adventure": "Point-and-Click",
    "Exploration": "Walking Simulator",
    # Invalid/removed entries (map to None)
    "(minigame)": None,
    "Minigames": None,
    "Various": None,
    "Snake": None,
    "Art": None,
    "Art game": None,
    "Augmented reality": None,
    "Artillery": None,
}

# Hierarchy structure: category -> list of child genres
GENRE_HIERARCHY = {
    "Action": [
        "Action",
        "Beat 'em Up",
        "Fighting",
        "First-Person Shooter",
        "Third-Person Shooter",
        "Light Gun Shooter",
        "Shooter",
        "Run and Gun",
        "Stealth",
        "Tactical Shooter",
        "Battle Royale",
        "MOBA",
        "Vehicular Combat",
    ],
    "Adventure": [
        "Action-Adventure",
        "Adventure",
        "Point-and-Click",
        "Interactive Drama",
        "Visual Novel",
        "Walking Simulator",
        "Escape Room",
        "Metroidvania",
        "Dungeon Crawler",
        "Platform",
        "Immersive Sim",
    ],
    "Role-Playing": [
        "Role-Playing",
        "Action RPG",
        "Tactical RPG",
        "MMORPG",
        "Roguelike",
        "Dungeon Management",
    ],
    "Strategy": [
        "Strategy",
        "Real-Time Strategy",
        "Real-Time Tactics",
        "Turn-Based Strategy",
        "Turn-Based Tactics",
        "4X Strategy",
        "Grand Strategy",
        "Tower Defense",
        "Tactical",
    ],
    "Simulation": [
        "Simulation",
        "Life Simulation",
        "Business Simulation",
        "City Building",
        "Construction & Management",
        "Flight Simulation",
        "Space Combat",
        "Vehicle Simulation",
        "Racing",
        "Kart Racing",
        "Pinball",
        "God Game",
    ],
    "Sports": [
        "Sports",
        "Football (American)",
        "Football (Association)",
        "Basketball",
        "Baseball",
        "Ice Hockey",
        "Boxing",
        "Snowboarding",
        "Sports Management",
    ],
    "Puzzle": [
        "Puzzle",
        "Match-Three",
        "Block Breaker",
        "Maze",
        "Incremental",
    ],
    "Party & Casual": [
        "Party",
        "Music",
        "Casual",
        "Digital Card Game",
        "Educational",
        "Exercise",
    ],
    "Hybrid & Specialized": [
        "Sandbox",
        "Survival",
        "Horror",
        "Massively Multiplayer",
        "Social Deduction",
        "Location-Based",
    ],
}

# Display order for root categories
ROOT_DISPLAY_ORDER = {
    "Action": 1,
    "Adventure": 2,
    "Role-Playing": 3,
    "Strategy": 4,
    "Simulation": 5,
    "Sports": 6,
    "Puzzle": 7,
    "Party & Casual": 8,
    "Hybrid & Specialized": 9,
}


def normalize_genre(name):
    """Normalize a genre name to canonical form."""
    if not name or not name.strip():
        return None
    name = name.strip()
    if name in GENRE_MAPPING:
        return GENRE_MAPPING[name]
    return name


def forward_migration(apps, schema_editor):
    """
    Normalize existing genres and populate hierarchy.

    Steps:
    1. Build mapping of old genre IDs to canonical names
    2. Create canonical genres with hierarchy structure
    3. Update Game M2M relationships to use canonical genres
    4. Delete old non-canonical genres
    """
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    Game = apps.get_model("games", "Game")

    # Step 1: Get all existing genres and their game relationships
    existing_genres = list(WikipediaGenre.objects.all())
    if not TEST_MODE:
        print(f"\nFound {len(existing_genres)} existing Wikipedia genres")

    # Build mapping: old_genre_id -> canonical_name
    old_to_canonical = {}
    for genre in existing_genres:
        canonical = normalize_genre(genre.name)
        old_to_canonical[genre.id] = canonical

    # Step 2: Get all game-genre relationships before we modify anything
    game_genre_relations = []
    for game in Game.objects.prefetch_related("wikipedia_genres").all():
        for genre in game.wikipedia_genres.all():
            canonical = old_to_canonical.get(genre.id)
            if canonical:  # Only keep valid genres
                game_genre_relations.append((game.id, canonical))

    if not TEST_MODE:
        print(f"Captured {len(game_genre_relations)} game-genre relationships")

    # Step 3: Clear all existing genres (we'll recreate them with hierarchy)
    WikipediaGenre.objects.all().delete()
    if not TEST_MODE:
        print("Cleared existing genres")

    # Step 4: Create root categories
    root_genres = {}
    for category_name, display_order in ROOT_DISPLAY_ORDER.items():
        genre = WikipediaGenre.objects.create(
            name=category_name,
            slug=slugify(category_name),
            parent=None,
            level=0,
            display_order=display_order,
            path=category_name,
        )
        root_genres[category_name] = genre
    if not TEST_MODE:
        print(f"Created {len(root_genres)} root categories")

    # Step 5: Create child genres with hierarchy
    all_genres = {}  # name -> genre object
    all_genres.update(root_genres)

    for category_name, child_names in GENRE_HIERARCHY.items():
        parent = root_genres[category_name]
        for idx, child_name in enumerate(child_names, start=1):
            # Skip if this genre name is same as category (root already exists)
            if child_name == category_name:
                continue

            # Check if genre already created
            # (some genres might appear in multiple categories)
            if child_name in all_genres:
                continue

            genre = WikipediaGenre.objects.create(
                name=child_name,
                slug=slugify(child_name),
                parent=parent,
                level=1,
                display_order=idx,
                path=f"{category_name} > {child_name}",
            )
            all_genres[child_name] = genre

    if not TEST_MODE:
        print(f"Created {len(all_genres)} total genres in hierarchy")

    # Step 6: Restore game-genre relationships using canonical names
    games_updated = 0
    for game_id, canonical_name in game_genre_relations:
        if canonical_name in all_genres:
            try:
                game = Game.objects.get(id=game_id)
                game.wikipedia_genres.add(all_genres[canonical_name])
                games_updated += 1
            except Game.DoesNotExist:
                continue

    if not TEST_MODE:
        print(f"Restored {games_updated} game-genre relationships")
        print("Migration complete!\n")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration - flatten hierarchy back to simple list.

    Note: This won't perfectly restore the original state since we've
    normalized genre names. The original duplicate names are lost.
    """
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # Clear all hierarchy data
    WikipediaGenre.objects.update(
        parent=None,
        level=0,
        path="",
        display_order=0,
    )
    if not TEST_MODE:
        print("Flattened genre hierarchy (hierarchy data cleared)")


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0049_add_wikipedia_genre_hierarchy"),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_migration),
    ]

"""
Data migration to normalize WikipediaGameData primary_genre and all_genres fields.

This ensures the text fields stored in WikipediaGameData use canonical genre names
matching the WikipediaGenre hierarchy, preventing inconsistencies between the stored
metadata and the M2M genre relationships.
"""

from django.db import migrations


# Genre normalization mapping - must match games/services/genre_normalizer.py
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
    "Rhythm game": "Music",
    "Karaoke": "Music",
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
    # Additional adventure variants
    "Graphic adventure": "Point-and-Click",
    "Exploration": "Walking Simulator",
    # Invalid/removed entries (map to None - will be filtered out)
    "(minigame)": None,
    "Minigames": None,
    "Various": None,
    "Snake": None,
    "Art": None,
    "Art game": None,
    "Augmented reality": None,
    "Artillery": None,
}


def normalize_genre(name):
    """Normalize a single genre name to canonical form."""
    if not name or not name.strip():
        return None
    name = name.strip()
    if name in GENRE_MAPPING:
        return GENRE_MAPPING[name]
    return name  # Return as-is if not in mapping


def normalize_genres_list(genres_str):
    """
    Normalize a genre string that may be comma-separated or pipe-separated.

    Wikipedia genres can be stored as:
    - Single genre: "Action"
    - Comma-separated: "Action, Platform"
    - Pipe-separated: "Action | Platform"
    - Combined: "Action, Platform | Puzzle"

    Returns the normalized comma-separated string with duplicates removed.
    """
    if not genres_str:
        return genres_str

    # Split on both pipe and comma separators
    # First replace pipes with commas, then split
    genres_str = genres_str.replace("|", ",")
    genres = [g.strip() for g in genres_str.split(",") if g.strip()]
    normalized = []
    seen = set()

    for genre in genres:
        canonical = normalize_genre(genre)
        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

    return ", ".join(normalized)


def forward_migration(apps, schema_editor):
    """Normalize WikipediaGameData primary_genre and all_genres fields."""
    WikipediaGameData = apps.get_model("games", "WikipediaGameData")

    records = WikipediaGameData.objects.all()
    total = records.count()
    updated = 0

    print(f"\nNormalizing {total} WikipediaGameData records...")

    for record in records:
        changed = False

        # Normalize primary_genre
        if record.primary_genre:
            normalized_primary = normalize_genre(record.primary_genre)
            if normalized_primary != record.primary_genre:
                record.primary_genre = normalized_primary or ""
                changed = True

        # Normalize all_genres (comma-separated list)
        if record.all_genres:
            normalized_all = normalize_genres_list(record.all_genres)
            if normalized_all != record.all_genres:
                record.all_genres = normalized_all
                changed = True

        if changed:
            record.save(update_fields=["primary_genre", "all_genres"])
            updated += 1

    print(f"Updated {updated} records")
    print("WikipediaGameData normalization complete!\n")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration is a no-op.

    We can't restore the original non-canonical names since we don't store
    the original values. The migration is essentially one-way for the text
    fields (the M2M relationships are handled by migration 0050).
    """
    print("\nReverse migration for WikipediaGameData is a no-op.")
    print("Original non-canonical genre names cannot be restored.\n")


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0050_normalize_and_populate_genre_hierarchy"),
    ]

    operations = [
        migrations.RunPython(forward_migration, reverse_migration),
    ]

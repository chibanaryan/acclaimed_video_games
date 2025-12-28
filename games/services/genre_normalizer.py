"""
Genre normalization service for Wikipedia genres.

This module provides mapping from all Wikipedia genre variants to canonical names,
ensuring consistent genre representation across the application.

Usage:
    from games.services.genre_normalizer import normalize_genre, normalize_genres

    # Normalize a single genre
    canonical = normalize_genre("Massively multiplayer online role-playing game")
    # Returns: "MMORPG"

    # Normalize a list of genres (removes duplicates)
    genres = ["MMORPG", "Massively multiplayer online role-playing game", "Platform"]
    normalized = normalize_genres(genres)
    # Returns: ["MMORPG", "Platform"]
"""

from typing import List, Optional

# Comprehensive mapping from all Wikipedia genre variants to canonical names
# This mapping consolidates 146 Wikipedia genres into ~80 canonical genres
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
    "Bullet hell": "Shooter",
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
    "Roguelite": "Roguelike",
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
    "Graphic adventure": "Point-and-Click",  # Classic adventure games
    "Exploration": "Walking Simulator",  # Exploration games
    # Invalid/removed entries (map to None)
    "(minigame)": None,
    "Minigame": "Interactive Drama",
    "Minigames": None,
    "Various": None,  # Too vague (UFO 50)
    "Snake": None,  # Too specific (single game type)
    "Art": None,  # Too vague
    "Art game": None,  # Too vague
    "Augmented reality": None,  # Platform, not genre
    "Artillery": None,  # Too specific
}

# Hierarchy structure: category -> list of child genres
# Used to assign proper parent when creating new genres
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

# Build reverse mapping: genre -> parent category
_GENRE_TO_PARENT = {}
for category, children in GENRE_HIERARCHY.items():
    for child in children:
        if child != category:  # Don't map category to itself
            _GENRE_TO_PARENT[child] = category


def get_genre_parent_name(genre_name: str) -> Optional[str]:
    """
    Get the parent category name for a genre.

    Args:
        genre_name: Canonical genre name

    Returns:
        Parent category name, or None if genre is a root category or unknown
    """
    return _GENRE_TO_PARENT.get(genre_name)


def get_or_create_genre(genre_name: str):
    """
    Get or create a WikipediaGenre with proper hierarchy.

    If the genre doesn't exist, creates it with the correct parent,
    level, path, and slug based on GENRE_HIERARCHY.

    Args:
        genre_name: Canonical genre name

    Returns:
        WikipediaGenre instance
    """
    from django.utils.text import slugify
    from games.models import WikipediaGenre

    # Try to get existing genre first
    try:
        return WikipediaGenre.objects.get(name=genre_name)
    except WikipediaGenre.DoesNotExist:
        pass

    # Genre doesn't exist, create with proper hierarchy
    parent_name = get_genre_parent_name(genre_name)
    parent = None
    level = 0
    path = genre_name

    if parent_name:
        # Recursively ensure parent exists
        parent = get_or_create_genre(parent_name)
        level = parent.level + 1
        path = f"{parent.path} > {genre_name}"

    return WikipediaGenre.objects.create(
        name=genre_name,
        slug=slugify(genre_name),
        parent=parent,
        level=level,
        path=path,
    )


def normalize_genre(name: str) -> Optional[str]:
    """
    Normalize a single Wikipedia genre name to its canonical form.

    Args:
        name: Raw genre name from Wikipedia

    Returns:
        Canonical genre name, or None if genre should be removed

    Examples:
        >>> normalize_genre("Massively multiplayer online role-playing game")
        'MMORPG'

        >>> normalize_genre("Platform")
        'Platform'

        >>> normalize_genre("(minigame)")
        None
    """
    # Strip whitespace and handle empty strings
    if not name or not name.strip():
        return None

    name = name.strip()

    # Check if we have a mapping for this genre
    if name in GENRE_MAPPING:
        return GENRE_MAPPING[name]

    # If no mapping exists, return the name as-is (unknown genre)
    # This allows for graceful handling of new genres not in our mapping
    return name


def normalize_genres(names: List[str]) -> List[str]:
    """
    Normalize a list of Wikipedia genre names, removing duplicates and invalid genres.

    Args:
        names: List of raw genre names from Wikipedia

    Returns:
        List of canonical genre names (duplicates removed, order preserved)

    Examples:
        >>> normalize_genres(["MMORPG", "Massively multiplayer online",
        ...                   "Action RPG"])
        ['MMORPG', 'Action RPG']

        >>> normalize_genres(["Platform", "Platformer", "Platform game"])
        ['Platform']

        >>> normalize_genres(["Action", "(minigame)", "Adventure"])
        ['Action', 'Adventure']
    """
    normalized = []
    seen = set()

    for name in names:
        canonical = normalize_genre(name)

        # Skip None values (invalid genres) and duplicates
        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

    return normalized


# Statistics about the mapping
def get_mapping_stats() -> dict:
    """
    Get statistics about the genre mapping.

    Returns:
        Dictionary with mapping statistics
    """
    valid_mappings = {k: v for k, v in GENRE_MAPPING.items() if v is not None}
    invalid_mappings = {k: v for k, v in GENRE_MAPPING.items() if v is None}

    # Count unique canonical genres
    canonical_genres = set(valid_mappings.values())

    return {
        "total_variants": len(GENRE_MAPPING),
        "valid_mappings": len(valid_mappings),
        "invalid_mappings": len(invalid_mappings),
        "canonical_genres": len(canonical_genres),
        "canonical_list": sorted(canonical_genres),
    }

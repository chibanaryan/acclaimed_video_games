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
    "Beat'em up": "Beat 'em Up",  # Alternate spacing
    "Hack and slash": "Hack and Slash",
    "Fighting": "Fighting",
    "First-person shooter": "First-Person Shooter",
    "First-person hero shooter": "First-Person Shooter",
    "Hero shooter": "First-Person Shooter",
    "Third-person shooter": "Third-Person Shooter",
    "Light gun shooter": "Light Gun Shooter",
    "Shooter": "Shooter",
    "Extraction shooter": "Shooter",  # Consolidated: only 1 game
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
    "Tactical first-person shooter": "Tactical Shooter",
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
    "Puzzle-adventure": "Adventure",  # Consolidated: only 1 game
    "Point-and-click adventure": "Point-and-Click",
    "Point-and-click": "Point-and-Click",
    "Interactive drama": "Interactive Drama",
    "Interactive fiction": "Interactive Drama",
    "Interactive film": "Interactive Drama",
    "Interactive movie": "Interactive Drama",
    "Interactive novel": "Interactive Drama",
    "Visual novel": "Visual Novel",
    "Walking simulator": "Walking Simulator",
    "Escape the room": "Adventure",  # Consolidated: only 1 game
    "Metroidvania": "Metroidvania",
    "Dungeon crawl": "Dungeon Crawler",
    "Platform": "Platform",
    "Platformer": "Platform",
    "Platform game": "Platform",
    "Cinematic platform": "Platform",
    "Cinematic platformer": "Platform",
    "Puzzle-platform": "Puzzle-Platformer",
    "Puzzle platformer": "Puzzle-Platformer",
    "Immersive sim": "Adventure",  # Consolidated: only 1 game
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
    "Dungeon management game": "Role-Playing",  # Consolidated: only 1 game
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
    "Tower defense": "Strategy",  # Consolidated: only 1 game
    # Simulation genres
    "Simulation": "Simulation",
    "Life simulation": "Life Simulation",
    "Business simulation": "Simulation",  # Consolidated: only 1 game
    "Business simulation game": "Simulation",  # Consolidated: only 1 game
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
    "Space simulation": "Space Simulation",
    "Space trading and combat": "Space Combat",
    "Space trading and combat simulator": "Space Combat",
    "Vehicle simulation game": "Simulation",  # Consolidated: only 1 game
    "Driving": "Simulation",  # Consolidated: only 1 game
    "Racing": "Racing",
    "Sim racing": "Racing",
    "Racing simulation": "Racing",
    "Racing simulator": "Racing",
    "Simulation racing game": "Racing",
    "Kart racing": "Kart Racing",
    "Pinball": "Party",  # Consolidated: only 1 game, under Puzzle & Casual
    "Social simulation": "Life Simulation",
    "Social simulator": "Life Simulation",
    "Farm life sim": "Life Simulation",
    "Farm simulation": "Life Simulation",
    "God game": "God Game",
    # Sports genres
    "Sports": "Sports",
    "Sports game": "Sports",
    "American football": "Football (American)",
    "Football": "Football (Association)",
    "Association football": "Football (Association)",
    "Soccer": "Football (Association)",
    "Basketball": "Sports",  # Consolidated: only 1 game
    "Baseball": "Sports",  # Consolidated: only 1 game
    "Ice hockey": "Sports",  # Consolidated: only 1 game
    "Boxing": "Sports",  # Consolidated: only 1 game
    "Snowboarding": "Snowboarding",  # Keep: 3 games
    "Extreme sports": "Sports",  # Consolidated: only 1 game
    "Sports management": "Sports",  # Consolidated: only 1 game
    # Puzzle genres
    "Puzzle": "Puzzle",
    "Match-three": "Match-Three",
    "Match three": "Match-Three",
    "Tile-matching": "Match-Three",
    "Block breaker": "Puzzle",  # Consolidated: only 1 game
    "Maze": "Maze",
    "Incremental": "Puzzle",  # Consolidated: only 1 game
    # Puzzle & Casual genres (Party, Music, Educational are children of Puzzle & Casual)
    "Party": "Party",
    "Music": "Music",
    "Rhythm": "Music",
    "Rhythm game": "Music",
    "Karaoke": "Music",
    "Casual": "Party",  # Consolidated: only 1 game, under Puzzle & Casual
    # Consolidated: only 1 game, under Puzzle & Casual.
    "Digital collectible card game": "Party",
    "Educational": "Educational",  # Keep: 2 games
    "Edutainment": "Educational",  # Keep: maps to Educational
    "Exercise": "Party",  # Consolidated: only 1 game, under Puzzle & Casual
    # Redistributed genres (formerly Hybrid & Specialized)
    "Sandbox": "Sandbox",  # Moved to Simulation
    "Survival": "Survival",  # Moved to Action
    "Horror": "Horror",  # Moved to Adventure
    "Psychological horror": "Horror",  # Moved to Adventure
    "Survival horror": "Horror",  # Moved to Adventure
    "Massively multiplayer online": "Massively Multiplayer",  # Moved to Role-Playing
    "MMOG": "Massively Multiplayer",  # Moved to Role-Playing
    "MMO": "Massively Multiplayer",  # Moved to Role-Playing
    "Social deduction": "Party",  # Consolidated: only 1 game, under Puzzle & Casual
    "Location-based game": "Adventure",  # Consolidated: only 1 game
    # Additional adventure variants
    "Graphic adventure": "Point-and-Click",  # Classic adventure games
    "Exploration": "Walking Simulator",  # Only 1 game (Edith Finch) - walking sim fits
    # Invalid/removed entries (map to None)
    "Dystopian": None,  # Setting, not genre
    "(minigame)": None,
    "Minigame": None,  # Not a meaningful genre classification
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
    "Shooter": [  # NEW: Broken out from Action
        "Shooter",
        "First-Person Shooter",
        "Third-Person Shooter",
        "Light Gun Shooter",
        "Tactical Shooter",
        "Run and Gun",
    ],
    "Racing & Sports": [
        "Racing",  # Was root, now sub-genre
        "Sports",  # Was root, now sub-genre
        "Kart Racing",
        "Football (American)",
        "Football (Association)",
        "Snowboarding",
    ],
    "Puzzle & Casual": [
        "Puzzle",  # Was root, now sub-genre
        "Puzzle-Platformer",
        "Match-Three",
        "Party",
        "Music",
        "Educational",
    ],
    "Action": [
        "Action",
        "Beat 'em Up",
        "Hack and Slash",
        "Fighting",
        "Stealth",
        "Battle Royale",
        "MOBA",
        "Vehicular Combat",
        "Maze",
        "Platform",
        "Metroidvania",
        "Survival",  # Moved from Hybrid & Specialized
    ],
    "Adventure": [
        "Action-Adventure",
        "Adventure",
        "Point-and-Click",
        "Interactive Drama",
        "Visual Novel",
        "Walking Simulator",
        "Dungeon Crawler",
        "Horror",  # Moved from Hybrid & Specialized
    ],
    "Role-Playing": [
        "Role-Playing",
        "Action RPG",
        "Tactical RPG",
        "MMORPG",
        "Roguelike",
        "Massively Multiplayer",  # Moved from Hybrid & Specialized
    ],
    "Strategy": [
        "Strategy",
        "Real-Time Strategy",
        "Real-Time Tactics",
        "Turn-Based Strategy",
        "Turn-Based Tactics",
        "4X Strategy",
        "Grand Strategy",
    ],
    "Simulation": [
        "Simulation",
        "Life Simulation",
        "City Building",
        "Construction & Management",
        "Flight Simulation",
        "Space Combat",
        "Space Simulation",
        "God Game",
        "Sandbox",  # Moved from Hybrid & Specialized
    ],
    # REMOVED: "Hybrid & Specialized" - genres redistributed to other categories
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

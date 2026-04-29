"""
Enforce canonical top-level Wikipedia genre categories.

This migration cleans up root genres that leaked in from Wikipedia metadata
after the main hierarchy was established. Known variants are moved to clean
canonical genres; any remaining root genre with games is reparented under
"Other" so future historical data cannot appear as a new top-level category.
"""

from django.db import migrations
from django.utils.text import slugify


ALLOWED_ROOTS = [
    "Action",
    "Adventure",
    "Role-Playing",
    "Shooter",
    "Racing & Sports",
    "Puzzle & Casual",
    "Strategy",
    "Simulation",
]

ROOT_DISPLAY_ORDER = {
    "Action": 1,
    "Adventure": 2,
    "Role-Playing": 3,
    "Shooter": 4,
    "Racing & Sports": 5,
    "Puzzle & Casual": 6,
    "Strategy": 7,
    "Simulation": 8,
    "Other": 99,
}

TARGET_PARENT = {
    "Maze": "Action",
    "Interactive Drama": "Adventure",
    "Puzzle": "Puzzle & Casual",
    "Construction & Management": "Simulation",
}

CANONICAL_CHILD_PARENT = {
    "Shooter": [
        "First-Person Shooter",
        "Third-Person Shooter",
        "Light Gun Shooter",
        "Tactical Shooter",
        "Run and Gun",
    ],
    "Racing & Sports": [
        "Racing",
        "Sports",
        "Kart Racing",
        "Football (American)",
        "Football (Association)",
        "Snowboarding",
    ],
    "Puzzle & Casual": [
        "Puzzle",
        "Puzzle-Platformer",
        "Match-Three",
        "Party",
        "Music",
        "Educational",
    ],
    "Action": [
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
        "Survival",
    ],
    "Adventure": [
        "Action-Adventure",
        "Point-and-Click",
        "Interactive Drama",
        "Visual Novel",
        "Walking Simulator",
        "Dungeon Crawler",
        "Horror",
    ],
    "Role-Playing": [
        "Action RPG",
        "Tactical RPG",
        "MMORPG",
        "Roguelike",
        "Massively Multiplayer",
    ],
    "Strategy": [
        "Real-Time Strategy",
        "Real-Time Tactics",
        "Turn-Based Strategy",
        "Turn-Based Tactics",
        "4X Strategy",
        "Grand Strategy",
    ],
    "Simulation": [
        "Life Simulation",
        "Management Simulation",
        "City Building",
        "Construction & Management",
        "Flight Simulation",
        "Space Combat",
        "Space Simulation",
        "Vehicle Simulation",
        "God Game",
        "Sandbox",
    ],
}

KNOWN_CHILD_PARENT = {
    child_name: parent_name
    for parent_name, child_names in CANONICAL_CHILD_PARENT.items()
    for child_name in child_names
}

GENRE_REMAP = {
    "art": "Adventure",
    "art game": "Adventure",
    "electronic literature": "Interactive Drama",
    "puzzle game": "Puzzle",
    "snake": "Maze",
    "vehicle construction": "Construction & Management",
}


def _normalize_key(value):
    if not value:
        return ""
    return " ".join(value.strip().casefold().split())


def _find_genre_by_name_or_slug(WikipediaGenre, name):
    slug = slugify(name)
    return (
        WikipediaGenre.objects.filter(name=name).first()
        or WikipediaGenre.objects.filter(slug=slug).first()
    )


def _ensure_root_genre(WikipediaGenre, name):
    genre = _find_genre_by_name_or_slug(WikipediaGenre, name)
    if genre is None:
        genre = WikipediaGenre.objects.create(
            name=name,
            slug=slugify(name),
            parent=None,
            level=0,
            path=name,
            display_order=ROOT_DISPLAY_ORDER.get(name, 0),
        )

    update_fields = []
    if genre.name != name:
        genre.name = name
        update_fields.append("name")
    if genre.slug != slugify(name):
        genre.slug = slugify(name)
        update_fields.append("slug")
    if genre.parent_id is not None:
        genre.parent = None
        update_fields.append("parent")
    if genre.level != 0:
        genre.level = 0
        update_fields.append("level")
    if genre.path != name:
        genre.path = name
        update_fields.append("path")
    display_order = ROOT_DISPLAY_ORDER.get(name, genre.display_order)
    if genre.display_order != display_order:
        genre.display_order = display_order
        update_fields.append("display_order")

    if update_fields:
        genre.save(update_fields=update_fields)

    return genre


def _ensure_child_genre(WikipediaGenre, parent, name):
    expected_path = f"{parent.name} > {name}"
    genre = _find_genre_by_name_or_slug(WikipediaGenre, name)
    if genre is None:
        genre = WikipediaGenre.objects.create(
            name=name,
            slug=slugify(name),
            parent=parent,
            level=1,
            path=expected_path,
            display_order=0,
        )

    update_fields = []
    if genre.name != name:
        genre.name = name
        update_fields.append("name")
    if genre.slug != slugify(name):
        genre.slug = slugify(name)
        update_fields.append("slug")
    if genre.parent_id != parent.id:
        genre.parent = parent
        update_fields.append("parent")
    if genre.level != 1:
        genre.level = 1
        update_fields.append("level")
    if genre.path != expected_path:
        genre.path = expected_path
        update_fields.append("path")

    if update_fields:
        genre.save(update_fields=update_fields)

    return genre


def _ensure_genre(WikipediaGenre, name):
    parent_name = TARGET_PARENT.get(name) or KNOWN_CHILD_PARENT.get(name)
    if not parent_name:
        return _ensure_root_genre(WikipediaGenre, name)
    parent = _ensure_root_genre(WikipediaGenre, parent_name)
    return _ensure_child_genre(WikipediaGenre, parent, name)


def _move_game_links(Game, source_genre, target_genre):
    if source_genre.id == target_genre.id:
        return

    for game in Game.objects.filter(wikipedia_genres=source_genre).iterator():
        game.wikipedia_genres.remove(source_genre)
        game.wikipedia_genres.add(target_genre)

    if not source_genre.children.exists():
        source_genre.delete()


def _canonicalize_genre_name(value):
    if not value:
        return None
    stripped = value.strip()
    return GENRE_REMAP.get(_normalize_key(stripped), stripped)


def _normalize_metadata(WikipediaGameData):
    for metadata in WikipediaGameData.objects.all().iterator():
        update_fields = []

        source_tokens = []
        if metadata.all_genres:
            source_tokens = [
                token.strip()
                for token in metadata.all_genres.replace("|", ",").split(",")
                if token.strip()
            ]
        if not source_tokens and metadata.primary_genre:
            source_tokens = [metadata.primary_genre]

        normalized_tokens = []
        seen = set()
        for token in source_tokens:
            canonical = _canonicalize_genre_name(token)
            if canonical is None:
                continue
            key = _normalize_key(canonical)
            if key in seen:
                continue
            seen.add(key)
            normalized_tokens.append(canonical)

        normalized_primary = _canonicalize_genre_name(metadata.primary_genre)
        if normalized_primary is None:
            normalized_primary = normalized_tokens[0] if normalized_tokens else None
        elif all(
            _normalize_key(normalized_primary) != _normalize_key(token)
            for token in normalized_tokens
        ):
            normalized_tokens.insert(0, normalized_primary)

        normalized_all = ", ".join(normalized_tokens)

        if metadata.primary_genre != normalized_primary:
            metadata.primary_genre = normalized_primary
            update_fields.append("primary_genre")
        if (metadata.all_genres or "") != normalized_all:
            metadata.all_genres = normalized_all
            update_fields.append("all_genres")

        if update_fields:
            metadata.save(update_fields=update_fields)


def _set_root_display_order(WikipediaGenre):
    for root_name in ALLOWED_ROOTS:
        root = WikipediaGenre.objects.filter(
            name=root_name, parent__isnull=True
        ).first()
        if root and root.display_order != ROOT_DISPLAY_ORDER[root_name]:
            root.display_order = ROOT_DISPLAY_ORDER[root_name]
            root.save(update_fields=["display_order"])


def _update_descendant_paths(genre):
    for child in genre.children.all():
        expected_level = genre.level + 1
        expected_path = f"{genre.path} > {child.name}"
        update_fields = []
        if child.level != expected_level:
            child.level = expected_level
            update_fields.append("level")
        if child.path != expected_path:
            child.path = expected_path
            update_fields.append("path")
        if update_fields:
            child.save(update_fields=update_fields)
        _update_descendant_paths(child)


def _reparent_remaining_orphan_roots(WikipediaGenre):
    orphan_roots = list(
        WikipediaGenre.objects.filter(parent__isnull=True)
        .exclude(name__in=ALLOWED_ROOTS)
        .exclude(name="Other")
        .order_by("name")
    )

    if not orphan_roots:
        return

    other = None
    for genre in orphan_roots:
        parent_name = KNOWN_CHILD_PARENT.get(genre.name)
        if parent_name:
            parent = _ensure_root_genre(WikipediaGenre, parent_name)
        else:
            if other is None:
                other = _ensure_root_genre(WikipediaGenre, "Other")
            parent = other
        expected_path = f"{parent.path} > {genre.name}"
        genre.parent = parent
        genre.level = 1
        genre.path = expected_path
        genre.save(update_fields=["parent", "level", "path"])
        _update_descendant_paths(genre)


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    WikipediaGameData = apps.get_model("games", "WikipediaGameData")
    Game = apps.get_model("games", "Game")

    _set_root_display_order(WikipediaGenre)

    for source_key, target_name in GENRE_REMAP.items():
        target_genre = _ensure_genre(WikipediaGenre, target_name)
        source_genres = [
            genre
            for genre in WikipediaGenre.objects.all()
            if _normalize_key(genre.name) == source_key
        ]
        for source_genre in source_genres:
            _move_game_links(Game, source_genre, target_genre)

    _normalize_metadata(WikipediaGameData)
    _reparent_remaining_orphan_roots(WikipediaGenre)


def backwards(apps, schema_editor):
    # Irreversible cleanup migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0101_populate_remaining_platform_metadata"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

"""
Clean up orphan Wikipedia genre roots and normalize stored metadata.

This migration:
1. Creates a small set of durable canonical leaf genres under existing roots.
2. Reassigns games from orphan root genres to canonical targets or drops
   descriptor-only labels.
3. Applies the same canonicalization to WikipediaGameData text fields.
"""

from django.db import migrations
from django.utils.text import slugify


NEW_LEAF_GENRES = {
    "Simulation": ["Management Simulation", "Vehicle Simulation"],
}

GENRE_REMAP = {
    "Action platformer": "Platform",
    "Action puzzle": "Puzzle",
    "Action-adventure": "Action-Adventure",
    "Action role-playing": "Action RPG",
    "Action role-playing game": "Action RPG",
    "Air combat simulation": "Flight Simulation",
    "Auto battler": "Strategy",
    "Dungeon management": "Management Simulation",
    "Dungeon management game": "Management Simulation",
    "Electronic literature": "Interactive Drama",
    "Factory simulation": "Management Simulation",
    "Falling block puzzle": "Puzzle",
    "First-person shooter": "First-Person Shooter",
    "Fighting game": "Fighting",
    "Interactive fiction": "Interactive Drama",
    "Interactive movie": "Interactive Drama",
    "Management simulation": "Management Simulation",
    "Monster tamer": "Role-Playing",
    "Music video game": "Music",
    "Platforming": "Platform",
    "Point-and-click adventure game": "Point-and-Click",
    "Puzzle adventure": "Adventure",
    "Puzzle game": "Puzzle",
    "Racing game": "Racing",
    "Real-time strategy": "Real-Time Strategy",
    "Real-time tactics": "Real-Time Tactics",
    "Role-playing": "Role-Playing",
    "RPG": "Role-Playing",
    "Sport": "Sports",
    "Space flight simulation": "Flight Simulation",
    "Submarine simulator": "Vehicle Simulation",
    "Tennis": "Sports",
    "Third-person shooter": "Third-Person Shooter",
    "Turn-based": "Strategy",
    "Vehicle simulation": "Vehicle Simulation",
    "Vehicle simulation game": "Vehicle Simulation",
    "Wargame": "Strategy",
}

DESCRIPTOR_GENRES = {
    "Art tool",
    "Cooking",
    "First-person",
    "Hacking",
    "Level editor",
    "Lunar Lander",
    "Vehicle construction",
}

ART_TOOL_FALLBACK = "Puzzle & Casual"


def _normalize_key(value):
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


REMAPPED_KEYS = {
    _normalize_key(source): target for source, target in GENRE_REMAP.items()
}
DESCRIPTOR_KEYS = {_normalize_key(source) for source in DESCRIPTOR_GENRES}


def _canonicalize_genre_name(value):
    if not value:
        return None

    stripped = value.strip()
    key = _normalize_key(stripped)

    if key in DESCRIPTOR_KEYS:
        return None
    if key in REMAPPED_KEYS:
        return REMAPPED_KEYS[key]
    return stripped


def _ensure_root_genre(WikipediaGenre, name):
    genre, _ = WikipediaGenre.objects.get_or_create(
        name=name,
        defaults={
            "slug": slugify(name),
            "parent": None,
            "level": 0,
            "path": name,
            "display_order": 0,
        },
    )

    update_fields = []
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

    if update_fields:
        genre.save(update_fields=update_fields)

    return genre


def _ensure_child_genre(WikipediaGenre, parent, name):
    expected_path = f"{parent.name} > {name}"
    genre, _ = WikipediaGenre.objects.get_or_create(
        name=name,
        defaults={
            "slug": slugify(name),
            "parent": parent,
            "level": 1,
            "path": expected_path,
            "display_order": 0,
        },
    )

    update_fields = []
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


def _ensure_canonical_genres(WikipediaGenre):
    roots = {}
    canonical_genres = {}

    for root_name, child_names in NEW_LEAF_GENRES.items():
        root = _ensure_root_genre(WikipediaGenre, root_name)
        roots[root_name] = root
        for child_name in child_names:
            canonical_genres[child_name] = _ensure_child_genre(
                WikipediaGenre, root, child_name
            )

    roots[ART_TOOL_FALLBACK] = _ensure_root_genre(WikipediaGenre, ART_TOOL_FALLBACK)

    for canonical_name in set(GENRE_REMAP.values()):
        canonical_genres[canonical_name] = WikipediaGenre.objects.filter(
            name=canonical_name
        ).first() or canonical_genres.get(canonical_name)

    return roots, canonical_genres


def _move_or_drop_genre(Game, source_genre, target_genre=None, fallback_genre=None):
    if target_genre is not None and source_genre.id == target_genre.id:
        return

    for game in Game.objects.filter(wikipedia_genres=source_genre).iterator():
        game.wikipedia_genres.remove(source_genre)

        if target_genre is not None:
            game.wikipedia_genres.add(target_genre)

        if fallback_genre is not None and not game.wikipedia_genres.exists():
            game.wikipedia_genres.add(fallback_genre)

    if not source_genre.children.exists():
        source_genre.delete()


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


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    WikipediaGameData = apps.get_model("games", "WikipediaGameData")
    Game = apps.get_model("games", "Game")

    roots, canonical_genres = _ensure_canonical_genres(WikipediaGenre)
    fallback_genre = roots[ART_TOOL_FALLBACK]

    for source_name, target_name in GENRE_REMAP.items():
        source_genre = WikipediaGenre.objects.filter(name=source_name).first()
        target_genre = (
            canonical_genres.get(target_name)
            or WikipediaGenre.objects.filter(name=target_name).first()
        )
        if source_genre and target_genre:
            _move_or_drop_genre(Game, source_genre, target_genre=target_genre)

    for source_name in DESCRIPTOR_GENRES:
        source_genre = WikipediaGenre.objects.filter(name=source_name).first()
        if not source_genre:
            continue
        _move_or_drop_genre(
            Game,
            source_genre,
            fallback_genre=fallback_genre if source_name == "Art tool" else None,
        )

    _normalize_metadata(WikipediaGameData)


def backwards(apps, schema_editor):
    # Irreversible cleanup migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0099_cleanup_tactical_and_delivery_sim"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

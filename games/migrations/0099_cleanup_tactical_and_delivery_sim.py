"""
Cleanup migration for tactical/delivery-sim genre normalization.

This migration:
1. Ensures canonical target genres exist:
   - Shooter (root)
   - Tactical Shooter (child of Shooter)
   - Simulation (root)
2. Reassigns game relationships from obsolete genres:
   - Tactical -> Tactical Shooter
   - Delivery sim variants -> Simulation
3. Normalizes stored Wikipedia metadata text fields so reconnect/import
   paths continue using canonical names.
"""

from django.db import migrations
from django.db.models import Q
from django.utils.text import slugify


TACTICAL_KEYS = {
    "tactical",
    "tactical shooter",
    "tactical first-person shooter",
}

DELIVERY_SIM_KEYS = {
    "delivery sim",
    "delivery simulation",
    "delivery simulator",
}


def _normalized_key(value):
    """Lowercase + collapse whitespace for reliable matching."""
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def _canonicalize_genre_name(value):
    """
    Map tactical/delivery-sim variants to canonical labels.

    Returns the original value (trimmed) for non-targeted genres.
    """
    if not value:
        return value

    key = _normalized_key(value)
    if key in TACTICAL_KEYS:
        return "Tactical Shooter"
    if key in DELIVERY_SIM_KEYS:
        return "Simulation"
    return value.strip()


def _ensure_root_genre(WikipediaGenre, name):
    """Ensure a root genre exists with expected hierarchy fields."""
    genre, _ = WikipediaGenre.objects.get_or_create(
        name=name,
        defaults={
            "slug": slugify(name),
            "parent": None,
            "level": 0,
            "path": name,
        },
    )

    updates = []
    if not genre.slug:
        genre.slug = slugify(name)
        updates.append("slug")
    if genre.parent_id is not None:
        genre.parent = None
        updates.append("parent")
    if genre.level != 0:
        genre.level = 0
        updates.append("level")
    if genre.path != name:
        genre.path = name
        updates.append("path")

    if updates:
        genre.save(update_fields=updates)

    return genre


def _ensure_tactical_shooter(WikipediaGenre, shooter):
    """Ensure Tactical Shooter exists as a child of Shooter."""
    name = "Tactical Shooter"
    expected_path = f"{shooter.name} > {name}"
    genre, _ = WikipediaGenre.objects.get_or_create(
        name=name,
        defaults={
            "slug": slugify(name),
            "parent": shooter,
            "level": 1,
            "path": expected_path,
        },
    )

    updates = []
    if not genre.slug:
        genre.slug = slugify(name)
        updates.append("slug")
    if genre.parent_id != shooter.id:
        genre.parent = shooter
        updates.append("parent")
    if genre.level != 1:
        genre.level = 1
        updates.append("level")
    if genre.path != expected_path:
        genre.path = expected_path
        updates.append("path")

    if updates:
        genre.save(update_fields=updates)

    return genre


def _move_genre_relationships(Game, source_genres, target_genre):
    """Move game M2M links from source genres to the canonical target genre."""
    for source_genre in source_genres:
        if source_genre.id == target_genre.id:
            continue

        for game in Game.objects.filter(wikipedia_genres=source_genre).iterator():
            game.wikipedia_genres.remove(source_genre)
            game.wikipedia_genres.add(target_genre)

        # Avoid deleting parent genres that have children.
        has_children = source_genre.children.exists()
        if not has_children:
            source_genre.delete()


def _normalize_wikipedia_game_data(WikipediaGameData):
    """Normalize targeted variants in WikipediaGameData text fields."""
    for metadata in WikipediaGameData.objects.all().iterator():
        update_fields = []

        if metadata.primary_genre:
            normalized_primary = _canonicalize_genre_name(metadata.primary_genre)
            if normalized_primary != metadata.primary_genre:
                metadata.primary_genre = normalized_primary
                update_fields.append("primary_genre")

        if metadata.all_genres:
            raw_tokens = metadata.all_genres.replace("|", ",").split(",")
            normalized_tokens = []
            seen = set()

            for token in raw_tokens:
                token = token.strip()
                if not token:
                    continue
                canonical = _canonicalize_genre_name(token)
                key = _normalized_key(canonical)
                if canonical and key not in seen:
                    normalized_tokens.append(canonical)
                    seen.add(key)

            normalized_all_genres = ", ".join(normalized_tokens)
            if normalized_all_genres != metadata.all_genres:
                metadata.all_genres = normalized_all_genres
                update_fields.append("all_genres")

        if update_fields:
            metadata.save(update_fields=update_fields)


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    Game = apps.get_model("games", "Game")
    WikipediaGameData = apps.get_model("games", "WikipediaGameData")

    shooter = _ensure_root_genre(WikipediaGenre, "Shooter")
    tactical_shooter = _ensure_tactical_shooter(WikipediaGenre, shooter)
    simulation = _ensure_root_genre(WikipediaGenre, "Simulation")

    tactical_source_genres = list(WikipediaGenre.objects.filter(name__iexact="Tactical"))
    delivery_source_genres = list(
        WikipediaGenre.objects.filter(
            Q(name__iexact="Delivery sim")
            | Q(name__iexact="Delivery simulation")
            | Q(name__iexact="Delivery simulator")
        )
    )

    _move_genre_relationships(Game, tactical_source_genres, tactical_shooter)
    _move_genre_relationships(Game, delivery_source_genres, simulation)
    _normalize_wikipedia_game_data(WikipediaGameData)


def backwards(apps, schema_editor):
    # Irreversible cleanup migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0098_merge_tactical_fps_into_tactical_shooter"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

"""
Remap stray Wikipedia genres that leaked under the "Other" fallback root.

Metadata refreshes after 0102 created "Other > and" (a conjunction split out
of Super Mario Maker's infobox), "Other > Clicker" and "Other > MMOFPS".
The normalizer now maps these, so move existing game links and metadata to
the canonical genres and delete the strays.
"""

from django.db import migrations
from django.utils.text import slugify

# Casefolded stray name -> (canonical genre, its root) or None to drop
GENRE_REMAP = {
    "and": None,
    "or": None,
    "&": None,
    "clicker": ("Puzzle", "Puzzle & Casual"),
    "mmofps": ("First-Person Shooter", "Shooter"),
}


def _normalize_key(value):
    if not value:
        return ""
    return " ".join(value.strip().casefold().split())


def _get_or_create(WikipediaGenre, name, parent=None):
    genre = (
        WikipediaGenre.objects.filter(name=name).first()
        or WikipediaGenre.objects.filter(slug=slugify(name)).first()
    )
    if genre is not None:
        return genre
    return WikipediaGenre.objects.create(
        name=name,
        slug=slugify(name),
        parent=parent,
        level=parent.level + 1 if parent else 0,
        path=f"{parent.path} > {name}" if parent else name,
    )


def _resolve_target(WikipediaGenre, target):
    if target is None:
        return None
    name, root_name = target
    root = _get_or_create(WikipediaGenre, root_name)
    return _get_or_create(WikipediaGenre, name, parent=root)


def _remap_token(token):
    key = _normalize_key(token)
    if key in GENRE_REMAP:
        target = GENRE_REMAP[key]
        return target[0] if target else None
    return token.strip()


def _normalize_metadata(WikipediaGameData):
    for metadata in WikipediaGameData.objects.all().iterator():
        source_tokens = [
            token.strip()
            for token in (metadata.all_genres or "").split(",")
            if token.strip()
        ]
        primary_key = _normalize_key(metadata.primary_genre)
        if primary_key not in GENRE_REMAP and not any(
            _normalize_key(token) in GENRE_REMAP for token in source_tokens
        ):
            continue

        normalized_tokens = []
        seen = set()
        for token in source_tokens:
            canonical = _remap_token(token)
            if canonical is None or _normalize_key(canonical) in seen:
                continue
            seen.add(_normalize_key(canonical))
            normalized_tokens.append(canonical)

        primary = (
            _remap_token(metadata.primary_genre) if metadata.primary_genre else None
        )
        if primary is None:
            primary = normalized_tokens[0] if normalized_tokens else None
        elif _normalize_key(primary) not in seen:
            normalized_tokens.insert(0, primary)

        metadata.primary_genre = primary
        metadata.all_genres = ", ".join(normalized_tokens)
        metadata.save(update_fields=["primary_genre", "all_genres"])


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")
    WikipediaGameData = apps.get_model("games", "WikipediaGameData")
    Game = apps.get_model("games", "Game")

    strays = [
        genre
        for genre in WikipediaGenre.objects.all()
        if _normalize_key(genre.name) in GENRE_REMAP
    ]
    for stray in strays:
        target = _resolve_target(
            WikipediaGenre, GENRE_REMAP[_normalize_key(stray.name)]
        )
        for game in Game.objects.filter(wikipedia_genres=stray).iterator():
            game.wikipedia_genres.remove(stray)
            if target is not None:
                game.wikipedia_genres.add(target)
        if not stray.children.exists():
            stray.delete()

    _normalize_metadata(WikipediaGameData)


def backwards(apps, schema_editor):
    # Irreversible cleanup migration.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0111_restore_individual_platform_slugs"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

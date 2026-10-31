"""Artist slugs: from the current name, disambiguated the way Wikipedia does.

Every artist's slug is rebuilt from its name - by each import, and by each
metadata run, which is when new artists get their Wikipedia titles - so a
renamed act's URL follows its name. Nothing redirects a replaced slug yet, by
decision, so a renamed act's old links 404.

Most names are unique and get the plain slug. Where two acts' names slugify
alike, the English Wikipedia titles their Wikidata ids point to tell them
apart, as Wikipedia's own readable URLs do: the act whose title is the bare
name is the primary topic and keeps the plain slug - failing that, the
lowest provider id does - and the others take their titles: "Nirvana
(British band)" is "nirvana-british-band". An act with no title, or one
that still clashes, is numbered in provider-id order, so the same data
always gives the same slugs.
"""

from collections import defaultdict
from typing import Dict, Iterable, List, NamedTuple, Tuple

from django.utils import timezone
from django.utils.text import slugify
from unidecode import unidecode

from music import models

#: Room for a "-N" tail inside Artist.slug's 210 characters.
_MAX_BASE_LENGTH = 200


class SlugSource(NamedTuple):
    """What an artist's slug is made from."""

    source_id: int
    name: str
    wikipedia_title: str = ""


def _slug(text: str) -> str:
    """Through unidecode, as ``name_normalized`` is: "Røyksopp" is
    "royksopp", not "rykssopp", and a name in another script reads as itself.
    Trimmed, since transliteration can make it several times the name's
    length."""
    return slugify(unidecode(text or ""))[:_MAX_BASE_LENGTH].strip("-")


def plan_artist_slugs(entries: Iterable[SlugSource]) -> Dict[int, str]:
    """Each artist's slug, by provider id."""
    entries = sorted(entries, key=lambda entry: entry.source_id)
    bases = {entry.source_id: _slug(entry.name) or "artist" for entry in entries}
    natural = set(bases.values())
    groups: Dict[str, List[SlugSource]] = defaultdict(list)
    for entry in entries:
        groups[bases[entry.source_id]].append(entry)

    slugs: Dict[int, str] = {}
    taken = set()
    rest: List[SlugSource] = []
    for base, members in groups.items():
        primary = [
            member
            for member in members
            if len(members) == 1 or _slug(member.wikipedia_title) == base
        ]
        # The bare-name title is the primary topic; with none (or two), the
        # lowest provider id keeps the plain slug, so it is never left empty.
        keeper = primary[0] if len(primary) == 1 else members[0]
        slugs[keeper.source_id] = base
        taken.add(base)
        rest.extend(member for member in members if member is not keeper)

    # Wikipedia titles first, so a numbered tail never takes one; a title
    # may not take another artist's own plain slug either.
    numbered = []
    for entry in sorted(rest, key=lambda entry: entry.source_id):
        title = _slug(entry.wikipedia_title)
        if title and title not in taken and title not in natural:
            slugs[entry.source_id] = title
            taken.add(title)
        else:
            numbered.append(entry)

    for entry in numbered:
        base = bases[entry.source_id]
        slug, suffix = base, 2
        while slug in taken or (slug != base and slug in natural):
            slug = f"{base}-{suffix}"
            suffix += 1
        slugs[entry.source_id] = slug
        taken.add(slug)
    return slugs


def rebuild_artist_slugs() -> List[Tuple[int, str, str]]:
    """Re-plan every stored artist's slug; ``(source_id, old, new)`` changed."""
    artists = list(models.Artist.objects.filter(source_id__isnull=False))
    slugs = plan_artist_slugs(
        SlugSource(artist.source_id, artist.name, artist.wikipedia_title)
        for artist in artists
    )
    changed, updated = [], []
    for artist in artists:
        new = slugs[artist.source_id]
        if artist.slug != new:
            changed.append((artist.source_id, artist.slug, new))
            artist.slug = new
            updated.append(artist)
    models.Artist.objects.bulk_update(updated, ["slug"])
    if updated:
        # `/api/music/all/` names artists by slug, and its version follows
        # the albums' `modified`: without this a browser's stored copy would
        # keep linking and filtering by the old slugs.
        models.Album.objects.filter(artists__in=updated).update(modified=timezone.now())
    return changed

"""Backfill Platform.slug with SEO-friendly URL identifiers.

Most platforms use slugify(name), but a curated overrides dict (keyed by
platform code) picks the wording people actually search for, e.g.
"best pc games" rather than "best windows-pc games".
"""

from django.db import migrations
from django.utils.text import slugify

# Platform code -> preferred slug where slugify(name) is poor for search.
SLUG_OVERRIDES = {
    "WIN": "pc",
    "MAC": "mac",
    "C64": "commodore-64",
    "GEN": "sega-genesis",
    "AST": "atari-st",
    "XBXS": "xbox-series-x",
    "SNES": "snes",
    "NES": "nes",
    "TG16": "turbografx-16",
    "3DO": "3do",
    "GW": "game-and-watch",
    "D32": "dragon-32",
    "T80": "trs-80",
    "TCC": "tandy-color-computer",
}


def forwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for platform in Platform.objects.all():
        slug = SLUG_OVERRIDES.get(platform.code) or slugify(platform.name)
        if platform.slug != slug:
            platform.slug = slug
            platform.save(update_fields=["slug"])


def backwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    Platform.objects.update(slug=None)


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0107_platform_slug"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

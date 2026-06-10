"""Restore the original platform slugs; family pages were dropped.

Reverts migration 0110's renames: the manufacturer-family pages
(/games/pc/ etc.) are removed in favor of individual platform pages for
every qualifying platform, so the platforms take their slugs back.
"""

from django.db import migrations

RESTORES = {
    # code: (family_era_slug, restored_slug)
    "WIN": ("windows", "pc"),
    "PS": ("playstation-1", "playstation"),
    "Xbox": ("original-xbox", "xbox"),
}


def forwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for code, (old_slug, new_slug) in RESTORES.items():
        Platform.objects.filter(code=code, slug=old_slug).update(slug=new_slug)


def backwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for code, (old_slug, new_slug) in RESTORES.items():
        Platform.objects.filter(code=code, slug=new_slug).update(slug=old_slug)


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0110_platform_slug_family_renames"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

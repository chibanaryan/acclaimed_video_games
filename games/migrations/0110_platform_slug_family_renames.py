"""Free up family slugs by renaming the individual platforms that held them.

The /games/pc/, /games/playstation/, and /games/xbox/ SEO pages become
manufacturer-family pages (matching the UI's platform groups and search
intent), so the individual platforms move to more specific slugs.
"""

from django.db import migrations

RENAMES = {
    # code: (old_slug, new_slug)
    "WIN": ("pc", "windows"),
    "PS": ("playstation", "playstation-1"),
    "Xbox": ("xbox", "original-xbox"),
}


def forwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for code, (old_slug, new_slug) in RENAMES.items():
        Platform.objects.filter(code=code, slug=old_slug).update(slug=new_slug)


def backwards(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")
    for code, (old_slug, new_slug) in RENAMES.items():
        Platform.objects.filter(code=code, slug=new_slug).update(slug=old_slug)


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0109_site_domain_www"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

"""Align the Sites framework domain with the canonical host.

The sitemap builds absolute URLs from Site.domain, but every page's
canonical tag (and SITE_URL) uses www.acclaimedvideogames.com. The Site
record held the bare apex domain, so the sitemap submitted URLs that
didn't match the canonicals Google sees on-page.
"""

from django.db import migrations

CANONICAL_DOMAIN = "www.acclaimedvideogames.com"
APEX_DOMAIN = "acclaimedvideogames.com"


def forwards(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(domain=APEX_DOMAIN).update(domain=CANONICAL_DOMAIN)


def backwards(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(domain=CANONICAL_DOMAIN).update(domain=APEX_DOMAIN)


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0108_populate_platform_slugs"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

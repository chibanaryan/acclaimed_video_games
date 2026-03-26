from django.db import migrations


PLATFORM_YEAR_RANGES = {
    "D32": (1982, 1987),
    "GW": (1980, 1991),
    "MIC": (1973, None),
    "TT": (1982, 1985),
    "VECT": (1982, 1984),
}


def populate_remaining_platform_years(apps, schema_editor):
    Platform = apps.get_model("games", "Platform")

    for code, (year_start, year_end) in PLATFORM_YEAR_RANGES.items():
        Platform.objects.filter(code=code).update(
            year_start=year_start,
            year_end=year_end,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0100_cleanup_orphan_wikipedia_genres"),
    ]

    operations = [
        migrations.RunPython(
            populate_remaining_platform_years,
            migrations.RunPython.noop,
        ),
    ]

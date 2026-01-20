"""
Migration to add multi-ID support for IGDB and Wikidata.

Adds JSONField arrays to store all IDs (first is primary), with a data
migration to populate from existing single ID fields for backwards compatibility.
"""

from django.db import migrations, models


def populate_all_ids_from_primary(apps, schema_editor):
    """
    Populate the new JSONField arrays from existing primary ID fields.

    This ensures backwards compatibility - existing games will have
    their single ID stored in the new array field.
    """
    Game = apps.get_model("games", "Game")
    games_to_update = []

    for game in Game.objects.all():
        ids_changed = False
        if game.igdb_id and not game.all_igdb_ids:
            game.all_igdb_ids = [game.igdb_id]
            ids_changed = True
        if game.wikidata_id and not game.all_wikidata_ids:
            game.all_wikidata_ids = [game.wikidata_id]
            ids_changed = True
        if ids_changed:
            games_to_update.append(game)

    # Bulk update for efficiency
    if games_to_update:
        Game.objects.bulk_update(
            games_to_update, ["all_igdb_ids", "all_wikidata_ids"], batch_size=500
        )


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0093_merge_genre_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="all_igdb_ids",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="All IGDB IDs for this game (first is primary)",
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="all_wikidata_ids",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text="All Wikidata IDs for this game (first is primary)",
            ),
        ),
        migrations.RunPython(
            populate_all_ids_from_primary,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

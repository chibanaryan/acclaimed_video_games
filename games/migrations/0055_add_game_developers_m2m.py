# Generated manually for Company -> Developer refactor
# Add Game.developers M2M and migrate data from Game.studios

import sys

from django.db import migrations, models

# Suppress print statements during tests
TEST_MODE = "test" in sys.argv


def rename_m2m_table_if_needed(apps, schema_editor):
    """
    SQLite's RenameField doesn't rename M2M through tables.
    After migration 0044 renamed developers->studios, the table is still
    games_game_developers. We need to rename it to games_game_studios
    before adding the new developers M2M field.
    """
    connection = schema_editor.connection
    # Check if we're on SQLite
    if connection.vendor == "sqlite":
        cursor = connection.cursor()
        # Check if games_game_developers exists (old name from 0001)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='games_game_developers'"
        )
        if cursor.fetchone():
            # Check if it has developeralias_id (old structure) vs developer_id (new)
            cursor.execute("PRAGMA table_info(games_game_developers)")
            columns = [row[1] for row in cursor.fetchall()]
            # If the table exists and doesn't have developer_id, it's the old table
            # that needs to be renamed to make room for the new developers M2M
            if "developer_id" not in columns:
                # Drop old indexes first (SQLite doesn't auto-rename them)
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='games_game_developers' AND name NOT LIKE 'sqlite_%'"
                )
                for (index_name,) in cursor.fetchall():
                    cursor.execute(f"DROP INDEX IF EXISTS {index_name}")
                # Rename the table
                cursor.execute(
                    "ALTER TABLE games_game_developers RENAME TO games_game_studios"
                )


def migrate_game_studios_to_developers(apps, schema_editor):
    """
    Migrate Game.studios M2M relationships to Game.developers.

    For each Game:
    1. Get all related Studio records
    2. Find the corresponding Developer record (by igdb_id or name)
    3. Add the Developer to Game.developers
    """
    Game = apps.get_model("games", "Game")
    Studio = apps.get_model("games", "Studio")  # noqa: F841 - accessed via relationship
    Developer = apps.get_model("games", "Developer")

    # Build Studio igdb_id -> Developer mapping
    # First, map by igdb_id for accuracy
    dev_by_igdb_id = {}
    for dev in Developer.objects.filter(igdb_id__isnull=False):
        dev_by_igdb_id[dev.igdb_id] = dev

    # Also map by name for studios without igdb_id
    dev_by_name = {}
    for dev in Developer.objects.all():
        dev_by_name[dev.name] = dev

    # Process each game
    games_updated = 0
    for game in Game.objects.prefetch_related("studios"):
        developers_to_add = []

        for studio in game.studios.all():
            # Try to find Developer by igdb_id first
            if studio.igdb_id and studio.igdb_id in dev_by_igdb_id:
                developers_to_add.append(dev_by_igdb_id[studio.igdb_id])
            elif studio.name in dev_by_name:
                developers_to_add.append(dev_by_name[studio.name])
            # else: Studio has no matching Developer
            # (shouldn't happen after migration 0054)

        if developers_to_add:
            game.developers.set(developers_to_add)
            games_updated += 1

    if not TEST_MODE:
        print(f"Migrated developers for {games_updated} games")


def reverse_game_developers(apps, schema_editor):
    """
    Reverse migration: Clear Game.developers relationships.
    Note: Original Game.studios relationships are preserved until cleanup migration.
    """
    Game = apps.get_model("games", "Game")
    for game in Game.objects.all():
        game.developers.clear()
    if not TEST_MODE:
        print("Cleared game.developers relationships")


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0054_migrate_studio_to_developer"),
    ]

    operations = [
        # Step 0: Rename old M2M table if on SQLite (PostgreSQL handles this automatically)
        migrations.RunPython(rename_m2m_table_if_needed, migrations.RunPython.noop),
        # Step 1: Add Game.developers M2M field
        migrations.AddField(
            model_name="game",
            name="developers",
            field=models.ManyToManyField(
                blank=True,
                help_text="Game developers (from IGDB involved_companies)",
                related_name="developed_games",
                to="games.developer",
            ),
        ),
        # Step 2: Migrate data from Game.studios to Game.developers
        migrations.RunPython(
            migrate_game_studios_to_developers,
            reverse_game_developers,
        ),
    ]

# Generated manually for Company -> Developer refactor
# Cleanup migration: Remove Studio model and Game.studios M2M field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0055_add_game_developers_m2m"),
    ]

    operations = [
        # Step 1: Remove Game.studios M2M field
        migrations.RemoveField(
            model_name="game",
            name="studios",
        ),
        # Step 2: Delete Studio model
        migrations.DeleteModel(
            name="Studio",
        ),
    ]

# Migration to rename Genre to IGDBGenre and create WikipediaGenre model
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0047_remove_igdbgamedata_unique_primary_igdb_per_game_and_more"),
    ]

    operations = [
        # Step 1: Rename Genre → IGDBGenre
        migrations.RenameModel(
            old_name="Genre",
            new_name="IGDBGenre",
        ),
        # Step 2: Update IGDBGenre Meta options
        migrations.AlterModelOptions(
            name="igdbgenre",
            options={
                "ordering": ["name"],
                "verbose_name": "IGDB Genre",
                "verbose_name_plural": "IGDB Genres",
            },
        ),
        migrations.AlterModelTable(
            name="igdbgenre",
            table="games_igdbgenre",
        ),
        # Step 3: Create WikipediaGenre model
        migrations.CreateModel(
            name="WikipediaGenre",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "Wikipedia Genre",
                "verbose_name_plural": "Wikipedia Genres",
            },
        ),
        # Step 4: Add index to WikipediaGenre
        migrations.AddIndex(
            model_name="wikipediagenre",
            index=models.Index(fields=["name"], name="games_wikip_name_idx"),
        ),
        # Step 5: Add wikipedia_genres M2M field to Game
        migrations.AddField(
            model_name="game",
            name="wikipedia_genres",
            field=models.ManyToManyField(
                blank=True,
                related_name="games_with_wikipedia_genre",
                to="games.wikipediagenre",
            ),
        ),
    ]

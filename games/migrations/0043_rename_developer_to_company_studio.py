# Generated migration to rename Developer/DeveloperAlias to Company/Studio
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0042_migrate_igdb_wikipedia_data"),
    ]

    operations = [
        # Step 1: Rename Developer → Company
        migrations.RenameModel(
            old_name="Developer",
            new_name="Company",
        ),
        # Step 2: Rename DeveloperAlias → Studio
        migrations.RenameModel(
            old_name="DeveloperAlias",
            new_name="Studio",
        ),
        # Step 3: Update Company Meta options
        migrations.AlterModelOptions(
            name="company",
            options={"ordering": ["name"], "verbose_name_plural": "Companies"},
        ),
        # Step 4: Update Studio Meta options
        migrations.AlterModelOptions(
            name="studio",
            options={"ordering": ["name"], "verbose_name_plural": "Studios"},
        ),
        # Step 5: Rename Studio.developer → Studio.company
        migrations.RenameField(
            model_name="studio",
            old_name="developer",
            new_name="company",
        ),
        # Step 6: Update Studio.company FK to make it nullable
        migrations.AlterField(
            model_name="studio",
            name="company",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Parent company that owns this studio "
                    "(optional for independent studios)"
                ),
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="studios",
                to="games.company",
            ),
        ),
    ]

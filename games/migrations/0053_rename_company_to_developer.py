# Generated manually for Company -> Developer refactor

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0052_add_series_model"),
    ]

    operations = [
        # Step 1: Rename Company model to Developer
        migrations.RenameModel(
            old_name="Company",
            new_name="Developer",
        ),
        # Step 2: Add parent FK (self-referential) for hierarchy
        migrations.AddField(
            model_name="developer",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subsidiaries",
                to="games.developer",
                help_text="Parent developer/company in the ownership hierarchy",
            ),
        ),
        # Step 3: Make name unique (will be needed after merging Studios)
        # Note: We'll handle uniqueness after data migration
    ]

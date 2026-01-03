from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("games", "0067_add_article_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="SavedFilterSet",
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
                (
                    "name",
                    models.CharField(
                        help_text="User-defined or auto-generated filter name",
                        max_length=100,
                    ),
                ),
                (
                    "filters",
                    models.JSONField(
                        help_text="Filter configuration (q, start, end, genres, platforms, series, sort, played)"
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("modified", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="saved_filter_sets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-modified"],
            },
        ),
        migrations.AddIndex(
            model_name="savedfilterset",
            index=models.Index(
                fields=["user", "-modified"], name="games_saved_user_id_8a2f3c_idx"
            ),
        ),
    ]

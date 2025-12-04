# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0038_post_notification_sent_alter_post_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="wikipedia_page_title",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Wikipedia page title (e.g., 'The Legend of Zelda: Breath of the Wild')",
                max_length=300,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="game",
            name="wikipedia_lookup_source",
            field=models.CharField(
                blank=True,
                help_text="Method used: wikidata, opensearch_year, opensearch_basic, opensearch_fallback",
                max_length=50,
                null=True,
            ),
        ),
    ]

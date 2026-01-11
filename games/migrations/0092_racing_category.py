"""
Data migration to create Racing as its own root category.
Moves Racing and Kart Racing from Action to the new Racing category.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    # Get or create Racing as a root category
    # The "Racing" genre already exists as a child of Action - promote it to root
    racing_root = WikipediaGenre.objects.filter(name="Racing").first()
    if racing_root:
        # Promote existing Racing genre to root category
        racing_root.parent = None
        racing_root.level = 0
        racing_root.path = "Racing"
        racing_root.save()
    else:
        # Create new Racing root category (shouldn't happen, but just in case)
        racing_root = WikipediaGenre.objects.create(
            name="Racing",
            slug="racing",
            level=0,
            path="Racing",
            parent=None,
        )

    # Move Kart Racing under the Racing category
    kart_racing = WikipediaGenre.objects.filter(name="Kart Racing").first()
    if kart_racing:
        kart_racing.parent = racing_root
        kart_racing.level = 1
        kart_racing.path = "Racing > Kart Racing"
        kart_racing.save()


def backwards(apps, schema_editor):
    """
    Reverse the migration - move Racing genres back under Action.
    """
    WikipediaGenre = apps.get_model("games", "WikipediaGenre")

    action_root = WikipediaGenre.objects.filter(
        name="Action", parent__isnull=True
    ).first()

    if not action_root:
        return

    # Move Racing back under Action
    racing = WikipediaGenre.objects.filter(name="Racing").first()
    if racing:
        racing.parent = action_root
        racing.level = 1
        racing.path = "Action > Racing"
        racing.save()

    # Move Kart Racing back under Action
    kart_racing = WikipediaGenre.objects.filter(name="Kart Racing").first()
    if kart_racing:
        kart_racing.parent = action_root
        kart_racing.level = 1
        kart_racing.path = "Action > Kart Racing"
        kart_racing.save()


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0091_genre_hierarchy_improvements"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

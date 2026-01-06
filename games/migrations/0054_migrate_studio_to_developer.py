# Generated manually for Company -> Developer refactor
# Data migration: Migrate Studio records into Developer model

import sys

from django.db import migrations
from django.utils.text import slugify

# Suppress print statements during tests
TEST_MODE = "test" in sys.argv


def migrate_studios_to_developers(apps, schema_editor):
    """
    Migrate Studio records into Developer model.

    Three types of studios:
    1. Primary studio (name == company.name): Map to existing Developer record
    2. Subsidiary studio (has company, different name): Create new Developer with parent
    3. Independent studio (no company): Create new Developer as root

    Creates a mapping table for later M2M migration.
    """
    Studio = apps.get_model("games", "Studio")
    Developer = apps.get_model("games", "Developer")

    # Track Studio ID -> Developer ID mapping for M2M migration
    # We'll store this in a simple way: update Studio.igdb_id temporarily
    # Actually, we'll create a helper field or just iterate again

    # Create lists to track mappings
    studio_to_developer_id = {}

    for studio in Studio.objects.select_related("company").all():
        if studio.company:
            # Check if this is a primary studio (same name as parent company)
            is_primary = studio.name == studio.company.name

            if is_primary:
                # Primary studio: map to the Developer record that came from Company
                # The Company was renamed to Developer, so we find it by igdb_id or name
                parent_dev = Developer.objects.filter(
                    igdb_id=studio.company.igdb_id
                ).first()
                if not parent_dev:
                    parent_dev = Developer.objects.filter(
                        name=studio.company.name
                    ).first()

                if parent_dev:
                    studio_to_developer_id[studio.id] = parent_dev.id
                    # Update the Developer record with Studio's igdb_id if different
                    if studio.igdb_id and (
                        not parent_dev.igdb_id or parent_dev.igdb_id != studio.igdb_id
                    ):
                        parent_dev.igdb_id = studio.igdb_id
                        parent_dev.save(update_fields=["igdb_id"])
            else:
                # Subsidiary studio: create new Developer with parent FK
                parent_dev = Developer.objects.filter(
                    igdb_id=studio.company.igdb_id
                ).first()
                if not parent_dev:
                    parent_dev = Developer.objects.filter(
                        name=studio.company.name
                    ).first()

                # Check if a Developer with this name already exists
                existing_dev = Developer.objects.filter(name=studio.name).first()
                if existing_dev:
                    # Update existing Developer with parent relationship
                    if not existing_dev.parent:
                        existing_dev.parent = parent_dev
                        existing_dev.igdb_id = studio.igdb_id
                        existing_dev.save(update_fields=["parent", "igdb_id"])
                    studio_to_developer_id[studio.id] = existing_dev.id
                else:
                    # Create new Developer for subsidiary
                    new_dev = Developer.objects.create(
                        name=studio.name,
                        igdb_id=studio.igdb_id,
                        parent=parent_dev,
                        slug=None,  # Subsidiaries don't get slugs
                    )
                    studio_to_developer_id[studio.id] = new_dev.id
        else:
            # Independent studio: create new Developer as root
            # Check if a Developer with this name already exists
            existing_dev = Developer.objects.filter(name=studio.name).first()
            if existing_dev:
                # Already exists, just map to it
                if studio.igdb_id and not existing_dev.igdb_id:
                    existing_dev.igdb_id = studio.igdb_id
                    existing_dev.save(update_fields=["igdb_id"])
                studio_to_developer_id[studio.id] = existing_dev.id
            else:
                # Create new Developer as root
                new_dev = Developer.objects.create(
                    name=studio.name,
                    igdb_id=studio.igdb_id,
                    parent=None,
                    slug=slugify(studio.name),  # Root developers get slugs
                )
                studio_to_developer_id[studio.id] = new_dev.id

    # Store the mapping in a way that the next migration can use it
    # We'll use a simple approach: store the mapping in the Studio model's igdb_id field
    # by encoding the Developer ID. Actually, that's not clean.

    # Better approach: Create a temporary table or just re-calculate in next
    # migration. For now, we'll pass the mapping through by reading
    # Studio -> Developer relationships in the next migration based on
    # matching igdb_id or name.

    if not TEST_MODE:
        print(f"Migrated {len(studio_to_developer_id)} studios to developers")


def reverse_studio_migration(apps, schema_editor):
    """
    Reverse migration: Remove Developer records that were created from Studios.
    Note: This is a best-effort reverse - some data relationships may be lost.
    """
    Developer = apps.get_model("games", "Developer")

    # Delete Developer records that have a parent (these came from subsidiary studios)
    Developer.objects.filter(parent__isnull=False).delete()

    # For Developer records without parent that have no slug, they came from
    # independent studios. We can't easily distinguish these from original
    # Companies, so we leave them
    if not TEST_MODE:
        print("Reversed studio migration (deleted subsidiary developers)")


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0053_rename_company_to_developer"),
    ]

    operations = [
        migrations.RunPython(
            migrate_studios_to_developers,
            reverse_studio_migration,
        ),
    ]

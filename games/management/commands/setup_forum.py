"""
Set up the django-machina forum: structure, permissions and the
consolidated publication scores topic. Idempotent - safe to run
repeatedly.

Usage:
    python manage.py setup_forum
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from games.forum import (
    ensure_anonymous_read_permissions,
    ensure_forum_moderators_group,
    ensure_forum_structure,
    sync_publication_scores_topic,
)


class Command(BaseCommand):
    help = "Create forum structure, permissions and the publication scores topic"

    def handle(self, *args, **options):
        forums = ensure_forum_structure()
        self.stdout.write(f"Forums: {', '.join(f.name for f in forums.values())}")

        ensure_anonymous_read_permissions()
        self.stdout.write("Anonymous read permissions granted")

        group = ensure_forum_moderators_group()
        staff = get_user_model().objects.filter(is_staff=True)
        for user in staff:
            user.groups.add(group)
        self.stdout.write(f"{staff.count()} staff user(s) added to '{group.name}'")

        topic = sync_publication_scores_topic()
        self.stdout.write(f"'{topic.subject}' topic synced")

        self.stdout.write(self.style.SUCCESS("Forum setup complete"))

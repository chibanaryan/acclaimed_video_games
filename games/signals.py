"""
Signals for the games app.
"""

import logging

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from games.models import Developer, Game, Post, WikipediaGenre

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Post)
def check_should_notify(sender, instance, **kwargs):
    """
    Check if we should send email notifications for this Post.

    Notifications are sent when:
    - Post is active (published)
    - AND send_notification is checked
    - AND notification hasn't been sent yet (notification_sent=False)

    This ensures each post only triggers notifications once, even if edited later.
    """
    # Check if post should trigger notification
    if (
        instance.active
        and instance.send_notification
        and not instance.notification_sent
    ):
        # Mark that we should send notification after save
        instance._should_send_notification = True
        post_id = instance.title or instance.pk
        logger.info(f"Post '{post_id}' will trigger notification after save.")
    else:
        instance._should_send_notification = False


@receiver(post_save, sender=Post)
def send_notification_after_save(sender, instance, created, **kwargs):
    """
    Send email notifications after Post is saved (if flagged for notification).

    This runs after the post is saved to the database, ensuring the post ID
    and all fields are properly set before sending emails.
    """
    # Check if we should send notification (flag set in pre_save)
    if getattr(instance, "_should_send_notification", False):
        logger.info(
            f"Sending notifications for post '{instance.title or instance.pk}'..."
        )

        # Import here to avoid circular import
        from games import utils

        # Notify all subscribers
        sent_count = utils.notify_subscribers_of_new_post(instance)
        post_id = instance.title or instance.pk
        logger.info(f"Sent {sent_count} notification emails for post '{post_id}'")

        # Mark notification as sent (use update to avoid triggering another save)
        Post.objects.filter(pk=instance.pk).update(notification_sent=True)

        # Clean up the flag
        instance._should_send_notification = False


# =============================================================================
# Developer Hierarchy Cache Invalidation
# =============================================================================


@receiver([post_save, post_delete], sender=Developer)
def invalidate_developer_cache_on_change(sender, instance, **kwargs):
    """Invalidate developer hierarchy cache when Developer changes."""
    from django.core.cache import cache

    from games import config
    from games.services.developer_service import invalidate_developer_cache

    invalidate_developer_cache()

    # Also invalidate detail page caches for this developer and its root
    cache.delete(f"{config.CACHE_VERSION}:developer_detail:{instance.id}")
    if instance.parent_id:
        # Invalidate root developer's detail cache too
        root = instance.root_developer
        cache.delete(f"{config.CACHE_VERSION}:developer_detail:{root.id}")

    logger.debug("Developer hierarchy cache invalidated (Developer changed)")


@receiver(m2m_changed, sender=Game.developers.through)
def invalidate_developer_cache_on_game_change(sender, instance, pk_set, **kwargs):
    """Invalidate developer hierarchy cache when Game.developers M2M changes."""
    from django.core.cache import cache

    from games import config
    from games.services.developer_service import invalidate_developer_cache

    invalidate_developer_cache()

    # Invalidate detail page caches for affected developers
    if pk_set:
        for dev_id in pk_set:
            cache.delete(f"{config.CACHE_VERSION}:developer_detail:{dev_id}")
            # Also invalidate root developer's cache
            try:
                dev = Developer.objects.get(id=dev_id)
                if dev.parent_id:
                    root = dev.root_developer
                    cache.delete(f"{config.CACHE_VERSION}:developer_detail:{root.id}")
            except Developer.DoesNotExist:
                pass

    logger.debug("Developer hierarchy cache invalidated (Game.developers changed)")


# =============================================================================
# WikipediaGenre Hierarchy Cache Invalidation
# =============================================================================


def invalidate_genre_descendant_cache(genre_id=None):
    """
    Invalidate genre descendant caches.

    If genre_id is provided, invalidates cache for that genre and its ancestors.
    Otherwise, invalidates all genre descendant caches using pattern matching.
    """
    from django.core.cache import cache

    from games import config

    if genre_id:
        # Invalidate this genre's cache
        cache.delete(f"{config.CACHE_VERSION}:genre_descendants:{genre_id}")
        # Also invalidate ancestor caches since their descendants changed
        try:
            genre = WikipediaGenre.objects.get(id=genre_id)
            for ancestor in genre.get_ancestors():
                cache.delete(f"{config.CACHE_VERSION}:genre_descendants:{ancestor.id}")
        except WikipediaGenre.DoesNotExist:
            pass
    else:
        # Invalidate all genre descendant caches
        # Note: This uses pattern delete which may not work with all cache backends
        # For production, consider using cache versioning instead
        all_genres = WikipediaGenre.objects.values_list("id", flat=True)
        for gid in all_genres:
            cache.delete(f"{config.CACHE_VERSION}:genre_descendants:{gid}")


@receiver([post_save, post_delete], sender=WikipediaGenre)
def invalidate_genre_cache_on_change(sender, instance, **kwargs):
    """Invalidate genre descendant cache when WikipediaGenre changes."""
    invalidate_genre_descendant_cache(instance.id)
    logger.debug(f"Genre descendant cache invalidated (WikipediaGenre {instance.id})")

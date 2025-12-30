"""
Signals for the games app.
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from games.models import Post, Subscriber, UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile whenever a new User is created.

    If the user's email matches an existing confirmed and active Subscriber,
    auto-set email_subscribed=True to maintain their subscription preference.
    """
    if created:
        email_subscribed = False
        # Check if user's email is already a confirmed, active subscriber
        if instance.email:
            subscriber = Subscriber.objects.filter(
                email__iexact=instance.email,
                is_confirmed=True,
                is_active=True,
            ).first()
            if subscriber:
                email_subscribed = True
                logger.info(
                    f"Found existing subscriber for {instance.email}, "
                    "setting email_subscribed=True"
                )
        UserProfile.objects.create(user=instance, email_subscribed=email_subscribed)


@receiver(pre_save, sender=Post)
def check_should_notify(sender, instance, **kwargs):
    """
    Check if we should send email notifications for this Post.

    Notifications are sent when:
    - Post is active (published)
    - AND notification hasn't been sent yet (notification_sent=False)

    This ensures each post only triggers notifications once, even if edited later.
    """
    # Check if post should trigger notification
    if instance.active and not instance.notification_sent:
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

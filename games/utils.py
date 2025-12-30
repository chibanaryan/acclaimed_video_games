"""
Utility functions for Acclaimed Games.

This module provides backward compatibility re-exports from the new
service modules. New code should import directly from the service modules:

- games.services.import_handler - Import functions
- games.services.ranking_service - Ranking calculations
- games.services.query_filters - Filter utilities

This module also contains the send_contact_email function which doesn't
fit into the service layer pattern.
"""

from games import constants

# =============================================================================
# Backward Compatibility Re-exports
# =============================================================================

# Import handler functions
from games.services.import_handler import (  # noqa: F401
    import_data,
    import_igdb_with_progress,
    import_wikipedia_pages_with_progress,
    import_batch_with_progress,
    import_batch,
    delete_existing_data,
    clear_igdb_metadata,
    clear_wikipedia_metadata,
    import_lists,
    import_listmemberships,
    import_games,
    import_platforms,
    import_developers,
    _validate_prerequisites,
)

# Re-export dependencies that tests may patch
from io import TextIOWrapper  # noqa: F401
from django.db import transaction  # noqa: F401

# Ranking service functions
from games.services.ranking_service import (  # noqa: F401
    year_to_decade,
    update_year_decade_ranks,
)

# Query filter utilities
from games.services.query_filters import (  # noqa: F401
    apply_genre_filter,
    apply_platform_filter,
    apply_series_filter,
    get_or_set_cache,
    apply_year_filters,
    safe_int_filter,
    Filter,
)


# =============================================================================
# Email Utilities
# =============================================================================


def send_contact_email(name: str, email: str, category: str, message: str) -> bool:
    """
    Send a contact form email to the site administrators.

    Args:
        name: Name of the person sending the message
        email: Email address of the sender
        category: Category of the message (feature, bug, data, general, etc.)
        message: The message content

    Returns:
        True if the email was sent successfully, False otherwise
    """
    from django.conf import settings
    from django.core.mail import send_mail

    category_label = constants.get_contact_category_label(category)
    subject = f"[{category_label}] Contact Form Submission from {name}"

    # Use category-based email alias for better filtering
    # e.g., contact+feature@acclaimedvideogames.com
    base_email = settings.CONTACT_EMAIL
    if "@" in base_email:
        local, domain = base_email.split("@", 1)
        recipient_email = f"{local}+{category}@{domain}"
    else:
        recipient_email = base_email

    site_url = (
        settings.SITE_URL
        if hasattr(settings, "SITE_URL")
        else "acclaimedvideogames.com"
    )

    email_body = f"""
New contact form submission:

From: {name}
Email: {email}
Category: {category_label}

Message:
{message}

---
This message was sent via the contact form at {site_url}
"""

    try:
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send contact form email: {e}")
        return False


def send_post_notification_email(post, user) -> bool:
    """
    Send a notification email about a new post to a subscriber.

    Args:
        post: Post model instance
        user: User model instance with subscription fields

    Returns:
        True if the email was sent successfully, False otherwise
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags

    site_url = getattr(settings, "SITE_URL", "https://www.acclaimedvideogames.com")
    post_url = f"{site_url}/#latest-news"
    unsubscribe_url = f"{site_url}/unsubscribe/{user.unsubscribe_token}/"

    subject = f"New post: {post.title or 'Latest Update'}"

    # Get author name
    if post.author:
        author_name = post.author.get_full_name() or post.author.username
    else:
        author_name = "Acclaimed Video Games"

    # Get HTML version (full post with links intact)
    post_html = post.text_rendered

    # Get plain text version (for email clients that don't support HTML)
    post_text = strip_tags(post.text_rendered)

    # Plain text version
    text_body = f"""
New post on Acclaimed Video Games!

{post.title or 'Latest Update'}
By {author_name}

{post_text}

Read more: {post_url}

---
You're receiving this because you subscribed to Acclaimed Video Games
post notifications. To unsubscribe, visit: {unsubscribe_url}

Acclaimed Video Games
{site_url}
"""

    # HTML version with minimal styling - just accent color for button
    # fmt: off
    body_style = (
        "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
        "sans-serif; line-height: 1.6; max-width: 600px; margin: 0 auto; "
        "padding: 20px;"
    )
    button_style = (
        "display: inline-block; background-color: #004900; color: #fff; "
        "padding: 12px 24px; border-radius: 6px; text-decoration: none; "
        "font-weight: bold;"
    )
    footer_style = (
        "font-size: 12px; margin-top: 30px; padding-top: 20px; "
        "border-top: 1px solid #ccc;"
    )
    # fmt: on
    html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="{body_style}">
    <h2>{post.title or 'Latest Update'}</h2>
    <p style="font-size: 14px; margin-top: 0; margin-bottom: 20px;">
        By {author_name}
    </p>

    <div style="margin: 20px 0;">
        {post_html}
    </div>

    <p style="margin: 30px 0;">
        <a href="{post_url}" style="{button_style}">Read More</a>
    </p>

    <p style="{footer_style}">
        You're receiving this because you subscribed to updates.<br>
        <a href="{unsubscribe_url}">Unsubscribe</a> |
        <a href="{site_url}">Acclaimed Video Games</a>
    </p>
</body>
</html>"""

    try:
        # Create email with both plain text and HTML versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send post notification email: {e}")
        return False


def notify_subscribers_of_new_post(post) -> int:
    """
    Notify all verified, subscribed users about a new post.

    Args:
        post: Post model instance

    Returns:
        Number of emails sent successfully
    """
    from allauth.account.models import EmailAddress
    from games.models import User

    # Get users who are subscribed AND have a verified email
    verified_emails = EmailAddress.objects.filter(verified=True).values_list(
        "user_id", flat=True
    )
    subscribers = User.objects.filter(email_subscribed=True, id__in=verified_emails)
    sent_count = 0

    for user in subscribers:
        if send_post_notification_email(post, user):
            sent_count += 1

    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Sent post notification to {sent_count}/{subscribers.count()} subscribers"
    )

    return sent_count

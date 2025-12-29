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


def send_subscription_confirmation_email(subscriber) -> bool:
    """
    Send a confirmation email to a new subscriber.

    Args:
        subscriber: Subscriber model instance

    Returns:
        True if the email was sent successfully, False otherwise
    """
    from django.conf import settings
    from django.core.mail import send_mail

    site_url = getattr(settings, "SITE_URL", "https://www.acclaimedvideogames.com")
    confirmation_url = f"{site_url}/subscribe/confirm/{subscriber.confirmation_token}/"

    subject = "Confirm your subscription to Acclaimed Games"

    email_body = f"""
Thank you for subscribing to Acclaimed Games!

Please confirm your subscription by clicking the link below:

{confirmation_url}

If you didn't request this subscription, you can safely ignore this email.

---
Acclaimed Games
{site_url}
"""

    try:
        send_mail(
            subject=subject,
            message=email_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscriber.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send confirmation email: {e}")
        return False


def send_post_notification_email(post, subscriber) -> bool:
    """
    Send a notification email about a new post to a subscriber.

    Args:
        post: Post model instance
        subscriber: Subscriber model instance

    Returns:
        True if the email was sent successfully, False otherwise
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags

    site_url = getattr(settings, "SITE_URL", "https://www.acclaimedvideogames.com")
    post_url = f"{site_url}/#latest-news"
    unsubscribe_url = f"{site_url}/unsubscribe/{subscriber.unsubscribe_token}/"

    subject = f"New post: {post.title or 'Latest Update'}"

    # Get author name
    if post.author:
        author_name = post.author.get_full_name() or post.author.username
    else:
        author_name = "Acclaimed Games"

    # Get HTML version (full post with links intact)
    post_html = post.text_rendered

    # Get plain text version (for email clients that don't support HTML)
    post_text = strip_tags(post.text_rendered)

    # Plain text version
    text_body = f"""
New post on Acclaimed Games!

{post.title or 'Latest Update'}
By {author_name}

{post_text}

Read more: {post_url}

---
You're receiving this because you subscribed to Acclaimed Games
post notifications. To unsubscribe, visit: {unsubscribe_url}

Acclaimed Games
{site_url}
"""

    # HTML version (with working links)
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont,
                'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 5px;
        }}
        .byline {{
            color: #666;
            font-size: 14px;
            margin-top: 0;
            margin-bottom: 20px;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            font-size: 12px;
            color: #666;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h2>{post.title or 'Latest Update'}</h2>
    <p class="byline">By {author_name}</p>

    <div class="content">
        {post_html}
    </div>

    <p>
        <a href="{post_url}" style="
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            text-decoration: none;
        ">Read More</a>
    </p>

    <div class="footer">
        <p>You're receiving this because you subscribed to
        Acclaimed Games post notifications.</p>
        <p>
            <a href="{unsubscribe_url}">Unsubscribe</a> |
            <a href="{site_url}">Acclaimed Games</a>
        </p>
    </div>
</body>
</html>
"""

    try:
        # Create email with both plain text and HTML versions
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[subscriber.email],
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
    Notify all confirmed, active subscribers about a new post.

    Args:
        post: Post model instance

    Returns:
        Number of emails sent successfully
    """
    from games.models import Subscriber

    subscribers = Subscriber.objects.filter(is_confirmed=True, is_active=True)
    sent_count = 0

    for subscriber in subscribers:
        if send_post_notification_email(post, subscriber):
            sent_count += 1

    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Sent post notification to {sent_count}/{subscribers.count()} subscribers"
    )

    return sent_count

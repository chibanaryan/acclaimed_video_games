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
    import_batch_with_progress,
    import_batch,
    delete_existing_data,
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

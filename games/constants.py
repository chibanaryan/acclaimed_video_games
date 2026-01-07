# Import shared list type constants from core for backward compatibility.
# These are re-exported so existing code using `from games import constants`
# continues to work without changes.
from core.constants import (  # noqa: F401
    LIST_ALLTIME,
    LIST_DECADE,
    LIST_EOY,
    LIST_MISC,
    LIST_TYPE_CODES,
    LIST_TYPE_IMPORTANCE_ORDER,
    LIST_TYPE_PRIORITY,
    LIST_TYPE_SLUGS,
    LIST_TYPES,
    get_list_type_label,
)

# Game-specific import type codes
TYPE_GAME = "G"
TYPE_PLATFORM = "P"
TYPE_LIST = "L"
TYPE_LIST_MEMBERSHIP = "M"
TYPE_DEVELOPER = "D"

# Contact form categories
CONTACT_CATEGORIES = [
    ("feature", "Feature Request"),
    ("bug", "Bug Report"),
    ("data", "Data Issue"),
    ("general", "General"),
    ("partnership", "Partnership/Business"),
    ("press", "Press Inquiry"),
    ("submit_list", "List Submission"),
]


def get_contact_category_label(category_code):
    """Get display label for a contact category code.

    Args:
        category_code: Category identifier (feature, bug, etc.)

    Returns:
        Human-readable label or the code itself if not found
    """
    return dict(CONTACT_CATEGORIES).get(category_code, category_code)

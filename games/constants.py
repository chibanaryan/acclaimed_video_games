TYPE_GAME = "G"
TYPE_PLATFORM = "P"
TYPE_LIST = "L"
TYPE_LIST_MEMBERSHIP = "M"
TYPE_DEVELOPER = "D"

TYPES = [
    (TYPE_PLATFORM, "Platforms"),
    (TYPE_LIST, "Source lists"),
    (TYPE_GAME, "Games"),
    (TYPE_LIST_MEMBERSHIP, "Game positions"),
]

LIST_EOY = "E"
LIST_MISC = "M"
LIST_ALLTIME = "A"
LIST_DECADE = "D"

LIST_TYPES = [
    (LIST_ALLTIME, "All time"),
    (LIST_EOY, "End of year"),
    (LIST_MISC, "Miscellaneous"),
    (LIST_DECADE, "Decade"),
]

SEARCH_ALL = "ALL"
SEARCH_ANY = "ANY"
SEARCH_EXACTLY = "EXACTLY"
SEARCH_NONE = "NONE"

# Contact form categories
CONTACT_CATEGORIES = [
    ("feature", "Feature Request"),
    ("bug", "Bug Report"),
    ("data", "Data Issue"),
    ("general", "General"),
    ("partnership", "Partnership/Business"),
    ("press", "Press Inquiry"),
]


def get_list_type_label(type_code):
    """Get display label for a list type code.

    Args:
        type_code: Single character code (A, D, E, M)

    Returns:
        Human-readable label or the code itself if not found
    """
    return dict(LIST_TYPES).get(type_code, type_code)


def get_contact_category_label(category_code):
    """Get display label for a contact category code.

    Args:
        category_code: Category identifier (feature, bug, etc.)

    Returns:
        Human-readable label or the code itself if not found
    """
    return dict(CONTACT_CATEGORIES).get(category_code, category_code)

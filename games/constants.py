TYPE_GAME = "G"
TYPE_PLATFORM = "P"
TYPE_LIST = "L"
TYPE_LIST_MEMBERSHIP = "M"
TYPE_DEVELOPER = "D"

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

# URL-friendly slugs for list types
LIST_TYPE_SLUGS = {
    LIST_ALLTIME: "all-time",
    LIST_EOY: "end-of-year",
    LIST_MISC: "miscellaneous",
    LIST_DECADE: "decade",
}

# Reverse mapping: slug -> code
LIST_TYPE_CODES = {slug: code for code, slug in LIST_TYPE_SLUGS.items()}

# Importance order for list types (most important first)
# Used for sorting lists within publications and publications by importance
LIST_TYPE_IMPORTANCE_ORDER = (LIST_ALLTIME, LIST_DECADE, LIST_MISC, LIST_EOY)

# Mapping from type code to sort priority (lower = more important)
LIST_TYPE_PRIORITY = {code: idx for idx, code in enumerate(LIST_TYPE_IMPORTANCE_ORDER)}

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

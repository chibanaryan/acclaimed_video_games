TYPE_GAME = "G"
TYPE_PLATFORM = "P"
TYPE_LIST = "L"
TYPE_LIST_MEMBERSHIP = "M"
TYPE_DEVELOPER = "D"

TYPES = [
    (TYPE_GAME, "Games"),
    (TYPE_LIST_MEMBERSHIP, "Game positions"),
    (TYPE_LIST, "Source lists"),
    (TYPE_PLATFORM, "Platforms"),
    # (TYPE_DEVELOPER, 'Developers'),
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

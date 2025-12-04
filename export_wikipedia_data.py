#!/usr/bin/env python
"""Export games with Wikipedia data to CSV for manual review."""

import csv
import os
from datetime import datetime

# Setup Django
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "acclaimedgames.settings")
django.setup()

from games.models import Game  # noqa: E402

# Query games with Wikipedia data
games = Game.objects.filter(wikipedia_page_title__isnull=False).order_by("rank")

# Generate output filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"wikipedia_data_export_{timestamp}.csv"

# Write to CSV with all fields quoted
with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    writer.writerow(
        [
            "Game Name",
            "Year",
            "Wikidata ID",
            "Wikipedia Page Title",
            "Lookup Source",
            "Wikipedia URL",
        ]
    )

    for game in games:
        if game.wikipedia_page_title:
            title = game.wikipedia_page_title.replace(" ", "_")
            wikipedia_url = f"https://en.wikipedia.org/wiki/{title}"
        else:
            wikipedia_url = ""
        writer.writerow(
            [
                game.name,
                game.year_of_release or "",
                game.wikidata_id or "",
                game.wikipedia_page_title or "",
                game.wikipedia_lookup_source or "",
                wikipedia_url,
            ]
        )

print(f"Exported {games.count()} games to {output_file}")

"""
Export game links to CSV.
Creates a CSV with game names and links to both our site and HowLongToBeat.
"""

import csv
from django.core.management.base import BaseCommand
from games.models import Game


class Command(BaseCommand):
    help = "Export CSV with links to our game pages and HLTB pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="game_links.csv",
            help="Output CSV file path (default: game_links.csv)",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default="https://acclaimedgames.com",
            help="Base URL for game links (default: https://acclaimedgames.com)",
        )
        parser.add_argument(
            "--hltb-only",
            action="store_true",
            help="Only include games with HLTB data",
        )

    def handle(self, *args, **options):
        output_file = options["output"]
        base_url = options["base_url"].rstrip("/")
        hltb_only = options["hltb_only"]

        # Query games with related data
        queryset = (
            Game.objects.select_related(
                "primary_hltb_game_data", "primary_igdb_game_data"
            )
            .prefetch_related("developers", "platforms", "wikipedia_genres")
            .order_by("rank")
        )

        if hltb_only:
            queryset = queryset.filter(primary_hltb_game_data__isnull=False)

        games_count = queryset.count()
        self.stdout.write(f"Exporting {games_count} games...")

        # Write CSV - matches format from fetch_hltb_data.py with added link columns
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Header row matching original HLTB CSV format + link columns
            writer.writerow(
                [
                    "Rank",
                    "Game Name",
                    "Year",
                    "Our Game URL",
                    "HLTB URL",
                    "Fetch Method",
                    "HLTB ID",
                    "HLTB Name",
                    "Similarity",
                    "Main Story (h)",
                    "Main + Extra (h)",
                    "Completionist (h)",
                    "Error",
                ]
            )

            for game in queryset:
                # Build our game URL
                our_url = f"{base_url}/games/{game.slug}/"

                # Get HLTB data
                hltb_url = ""
                fetch_method = ""
                hltb_id = ""
                hltb_name = ""
                similarity = ""
                main_story = ""
                main_extra = ""
                completionist = ""
                error = ""

                if game.primary_hltb_game_data:
                    hltb_data = game.primary_hltb_game_data
                    hltb_id = hltb_data.hltb_id
                    hltb_url = hltb_data.hltb_url or ""
                    hltb_name = hltb_data.hltb_name or ""
                    fetch_method = hltb_data.fetch_method or ""
                    similarity = (
                        f"{hltb_data.similarity:.2f}" if hltb_data.similarity else ""
                    )
                    main_story = (
                        str(hltb_data.main_story_hours)
                        if hltb_data.main_story_hours
                        else ""
                    )
                    main_extra = (
                        str(hltb_data.main_extra_hours)
                        if hltb_data.main_extra_hours
                        else ""
                    )
                    completionist = (
                        str(hltb_data.completionist_hours)
                        if hltb_data.completionist_hours
                        else ""
                    )
                    error = hltb_data.fetch_error or ""

                writer.writerow(
                    [
                        game.rank,
                        game.name,
                        game.year_of_release or "",
                        our_url,
                        hltb_url,
                        fetch_method,
                        hltb_id,
                        hltb_name,
                        similarity,
                        main_story,
                        main_extra,
                        completionist,
                        error,
                    ]
                )

        self.stdout.write(
            self.style.SUCCESS(f"✓ Exported {games_count} games to {output_file}")
        )

        # Show stats
        with_hltb = queryset.filter(primary_hltb_game_data__isnull=False).count()
        self.stdout.write(f"  - Games with HLTB data: {with_hltb}")
        self.stdout.write(f"  - Games without HLTB data: {games_count - with_hltb}")

"""
Management command to fetch HowLongToBeat playtime data for games.

Uses the howlongtobeatpy library to search for games and retrieve
completion time estimates (main story, main+extras, completionist).
"""

import asyncio
import csv
import logging
import re
import time
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand

from games.models import Game, HLTBGameData

logger = logging.getLogger(__name__)

# Roman numeral conversion mappings
ROMAN_TO_ARABIC = {
    "I": "1",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
    "VII": "7",
    "VIII": "8",
    "IX": "9",
    "X": "10",
    "XI": "11",
    "XII": "12",
    "XIII": "13",
    "XIV": "14",
    "XV": "15",
    "XVI": "16",
    "XVII": "17",
    "XVIII": "18",
    "XIX": "19",
    "XX": "20",
}

ARABIC_TO_ROMAN = {v: k for k, v in ROMAN_TO_ARABIC.items()}

# Platform name mappings for HLTB matching
# Maps common HLTB platform names to our platform names
PLATFORM_ALIASES = {
    "pc": ["PC", "Windows", "Linux", "Mac"],
    "playstation": ["PlayStation", "PS1", "PSX"],
    "playstation 2": ["PlayStation 2", "PS2"],
    "playstation 3": ["PlayStation 3", "PS3"],
    "playstation 4": ["PlayStation 4", "PS4"],
    "playstation 5": ["PlayStation 5", "PS5"],
    "xbox": ["Xbox"],
    "xbox 360": ["Xbox 360"],
    "xbox one": ["Xbox One"],
    "xbox series x/s": ["Xbox Series X/S", "Xbox Series X", "Xbox Series S"],
    "nintendo switch": ["Nintendo Switch", "Switch"],
    "wii": ["Wii"],
    "wii u": ["Wii U"],
    "nintendo 64": ["Nintendo 64", "N64"],
    "gamecube": ["GameCube", "NGC"],
    "game boy": ["Game Boy", "GB"],
    "game boy advance": ["Game Boy Advance", "GBA"],
    "nintendo ds": ["Nintendo DS", "DS"],
    "nintendo 3ds": ["Nintendo 3DS", "3DS"],
    "nes": ["NES", "Nintendo Entertainment System"],
    "snes": ["SNES", "Super Nintendo Entertainment System", "Super Nintendo"],
    "mobile": ["iOS", "Android", "Mobile"],
}


def platform_matches(hltb_platform, game_platforms):
    """
    Check if HLTB platform matches any of our game's platforms.

    Args:
        hltb_platform: Platform string from HLTB (e.g., "PlayStation 4")
        game_platforms: List of platform names from our database

    Returns:
        True if there's a match, False otherwise
    """
    if not hltb_platform or not game_platforms:
        return False

    hltb_lower = hltb_platform.lower().strip()

    # Check direct match
    for platform in game_platforms:
        if platform.lower() == hltb_lower:
            return True

    # Check aliases
    for hltb_name, our_names in PLATFORM_ALIASES.items():
        if hltb_name in hltb_lower:
            for our_name in our_names:
                if our_name in game_platforms:
                    return True

    return False


def convert_numerals(name):
    """
    Generate alternate versions of a game name with Roman/Arabic numerals swapped.

    Examples:
        "Final Fantasy VII" -> ["Final Fantasy 7"]
        "Street Fighter 2" -> ["Street Fighter II"]
        "Grand Theft Auto V" -> ["Grand Theft Auto 5"]

    Returns:
        List of alternate name versions, or empty list if no conversions found.
    """
    alternates = []

    # Pattern to match Roman numerals at word boundaries
    # Must be surrounded by spaces, colon, or end of string
    roman_pattern = r"\b(" + "|".join(ROMAN_TO_ARABIC.keys()) + r")\b"

    # Try converting Roman to Arabic
    def roman_to_arabic_replacer(match):
        return ROMAN_TO_ARABIC[match.group(1)]

    roman_converted = re.sub(roman_pattern, roman_to_arabic_replacer, name)
    if roman_converted != name:
        alternates.append(roman_converted)

    # Try converting Arabic to Roman
    # Pattern to match single/double digit numbers at word boundaries
    arabic_pattern = r"\b(\d{1,2})\b"

    def arabic_to_roman_replacer(match):
        num = match.group(1)
        return ARABIC_TO_ROMAN.get(num, num)  # Keep original if no mapping

    arabic_converted = re.sub(arabic_pattern, arabic_to_roman_replacer, name)
    if arabic_converted != name and arabic_converted not in alternates:
        alternates.append(arabic_converted)

    return alternates


class Command(BaseCommand):
    help = "Fetch HowLongToBeat playtime data for games"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument(
            "--game",
            type=str,
            help="Process specific game by name (case-insensitive)",
        )
        parser.add_argument(
            "--slug",
            type=str,
            help="Process specific game by slug",
        )
        parser.add_argument(
            "--id",
            type=int,
            help="Process specific game by database ID",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Limit number of games to process",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Skip first N games (default: 0)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Delay between requests in seconds (default: 1.0)",
        )
        parser.add_argument(
            "--min-similarity",
            type=float,
            default=0.85,
            help="Minimum similarity score for matching (default: 0.85)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output CSV file path (default: hltb_data_TIMESTAMP.csv)",
        )
        parser.add_argument(
            "--no-output",
            action="store_true",
            help="Skip CSV output (console only)",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results to database (default: CSV only)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip games that already have HLTB data",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh all games (ignore existing data)",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=1,
            help="Number of concurrent requests (default: 1, recommend 5-10 for speed)",
        )
        parser.add_argument(
            "--use-name-search",
            action="store_true",
            help="Enable name search fallback when Wikidata HLTB ID is not available. "
            "Disabled by default to avoid incorrect matches.",
        )

    def handle(self, *args, **options):
        self.start_time = time.time()

        # Get games to process (do this synchronously before async context)
        games_qs = self._get_games(options)

        if not games_qs.exists():
            self.stdout.write(self.style.ERROR("No games found to process"))
            return

        # Convert to list to avoid async ORM issues
        # Include Wikidata HLTB ID for direct lookup when available
        # Also include Wikipedia page title for fallback search
        # Prefetch platforms for better matching
        games_qs = games_qs.prefetch_related("platforms")

        # Prefetch WikipediaGameData for all games
        games_qs = games_qs.prefetch_related("wikipedia_game_data_set")

        # Convert to list with platform data and all Wikidata HLTB IDs
        games_list = []
        for game in games_qs:
            platform_names = list(game.platforms.values_list("name", flat=True))

            # Collect HLTB IDs from ALL WikipediaGameData records (not just primary)
            # This allows fallback when primary record doesn't have an HLTB ID
            # Order: primary first (if it has hltb_id), then other records
            all_hltb_ids = []
            all_wikidata_ids = []  # Track which Wikidata IDs the HLTB IDs came from
            is_from_primary = []  # Track whether each HLTB ID is from primary

            # Track primary's wikidata_id for display purposes
            primary_wikidata_id = (
                game.primary_wikipedia_game_data.wikidata_id
                if game.primary_wikipedia_game_data
                else None
            )

            # First add primary if it has an HLTB ID
            if (
                game.primary_wikipedia_game_data
                and game.primary_wikipedia_game_data.hltb_id
            ):
                all_hltb_ids.append(game.primary_wikipedia_game_data.hltb_id)
                all_wikidata_ids.append(game.primary_wikipedia_game_data.wikidata_id)
                is_from_primary.append(True)

            # Then add other WikipediaGameData records that have HLTB IDs
            for wiki_data in game.wikipedia_game_data_set.all():
                if wiki_data.hltb_id and wiki_data.hltb_id not in all_hltb_ids:
                    all_hltb_ids.append(wiki_data.hltb_id)
                    all_wikidata_ids.append(wiki_data.wikidata_id)
                    is_from_primary.append(False)

            games_list.append(
                {
                    "id": game.id,
                    "name": game.name,
                    "slug": game.slug,
                    "rank": game.rank,
                    "year_of_release": game.year_of_release,
                    "igdb_id": game.igdb_id,
                    # Backwards compatible: primary hltb_id (if any)
                    "primary_wikipedia_game_data__hltb_id": (
                        all_hltb_ids[0] if all_hltb_ids else None
                    ),
                    # New: all HLTB IDs from all WikipediaGameData records
                    "all_wikidata_hltb_ids": all_hltb_ids,
                    "all_wikidata_ids": all_wikidata_ids,
                    "is_from_primary": is_from_primary,  # Track which are from primary
                    "primary_wikidata_id": primary_wikidata_id,
                    "primary_wikipedia_game_data__page_title": (
                        game.primary_wikipedia_game_data.page_title
                        if game.primary_wikipedia_game_data
                        else None
                    ),
                    "platforms": platform_names,
                }
            )
        game_count = len(games_list)

        # Run async handler with pre-fetched data
        asyncio.run(self._async_handle(games_list, game_count, *args, **options))

    async def _async_handle(self, games_list, game_count, *args, **options):
        from asgiref.sync import sync_to_async
        from howlongtobeatpy import HowLongToBeat

        delay = options.get("delay", 1.0)
        min_similarity = options.get("min_similarity", 0.85)
        concurrency = options.get("concurrency", 1)
        use_name_search = options.get("use_name_search", False)

        self.stdout.write(f"\nProcessing {game_count} games...")
        self.stdout.write(
            f"Delay: {delay}s, Min similarity: {min_similarity}, "
            f"Concurrency: {concurrency}"
        )
        if use_name_search:
            self.stdout.write(" (name search ENABLED)")
        self.stdout.write("\n")

        # Prepare CSV output - only if explicitly requested with --output
        # (CSV was mainly for testing; production uses --save for database)
        csv_file = None
        csv_writer = None
        csv_path = None
        if options.get("output"):
            csv_path = self._get_csv_path(options.get("output"))
            csv_file = open(csv_path, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "Rank",
                    "Game Name",
                    "Year",
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
            self.stdout.write(f"Writing results to: {csv_path}\n")

        # Process games with concurrency
        success_count = 0
        failure_count = 0
        hltb = HowLongToBeat()

        # Create locks for thread-safe operations
        csv_lock = asyncio.Lock()
        counter_lock = asyncio.Lock()

        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(concurrency)

        async def process_game(idx, game_data):
            """Process a single game with rate limiting."""
            nonlocal success_count, failure_count

            async with semaphore:
                hltb_id = ""
                hltb_name = ""
                similarity = 0.0
                main_story = None
                main_extra = None
                completionist = None
                error_message = ""
                fetch_method = ""

                game_name = game_data["name"]
                game_year = game_data["year_of_release"]
                game_rank = game_data["rank"]
                game_igdb_id = game_data["igdb_id"]
                game_id = game_data["id"]
                game_platforms = game_data.get("platforms", [])
                # Get all HLTB IDs from all WikipediaGameData records
                all_wikidata_hltb_ids = game_data.get("all_wikidata_hltb_ids", [])
                all_wikidata_ids = game_data.get("all_wikidata_ids", [])
                is_from_primary_list = game_data.get("is_from_primary", [])
                wiki_page_title = game_data.get(
                    "primary_wikipedia_game_data__page_title"
                )
                # Track which wikidata ID was used for successful lookup
                used_wikidata_id = None

                try:
                    best_match = None

                    # Try direct ID lookup with ALL HLTB IDs from Wikidata
                    # Iterates through the list until one works (handles cases
                    # like Counter-Strike where primary doesn't have HLTB ID)
                    for idx_hltb, wikidata_hltb_id in enumerate(all_wikidata_hltb_ids):
                        try:
                            direct_result = await hltb.async_search_from_id(
                                int(wikidata_hltb_id)
                            )
                            if direct_result:
                                best_match = direct_result
                                fetch_method = "wikidata"
                                used_wikidata_id = (
                                    all_wikidata_ids[idx_hltb]
                                    if idx_hltb < len(all_wikidata_ids)
                                    else None
                                )
                                # Check if this HLTB ID is from primary or alternate
                                is_from_primary = (
                                    is_from_primary_list[idx_hltb]
                                    if idx_hltb < len(is_from_primary_list)
                                    else True
                                )
                                # Log which Wikidata ID was used (especially useful
                                # when it's not the primary)
                                extra_info = ""
                                if not is_from_primary:
                                    extra_info = (
                                        f" (via alternate Wikidata {used_wikidata_id})"
                                    )
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"[{idx}/{game_count}] ★ {game_name}: "
                                        f"Direct lookup via Wikidata HLTB ID "
                                        f"{wikidata_hltb_id}{extra_info}"
                                    )
                                )
                                break  # Found a working HLTB ID, stop iterating
                        except Exception as e:
                            logger.debug(
                                "Direct HLTB lookup failed for ID %s: %s",
                                wikidata_hltb_id,
                                e,
                            )
                            # Continue to next HLTB ID in the list

                    # Fall back to name search if direct lookup failed
                    # (only if --use-name-search was specified)
                    if not best_match and use_name_search:
                        # Build list of names to try: Wikipedia title first,
                        # then local name. Also include Roman/Arabic numeral
                        # conversions
                        search_names = []
                        if wiki_page_title and wiki_page_title != game_name:
                            search_names.append(wiki_page_title)
                            # Add numeral variants of Wikipedia title
                            search_names.extend(convert_numerals(wiki_page_title))

                        search_names.append(game_name)
                        # Add numeral variants of local name
                        search_names.extend(convert_numerals(game_name))

                        # Remove duplicates while preserving order
                        seen = set()
                        search_names = [
                            x for x in search_names if not (x in seen or seen.add(x))
                        ]

                        for search_name in search_names:
                            results = await hltb.async_search(search_name)

                            if results:
                                # Filter to matches that meet similarity threshold
                                good_matches = [
                                    r for r in results if r.similarity >= min_similarity
                                ]

                                if not good_matches:
                                    continue

                                # If we have a year and multiple matches,
                                # prefer year match
                                if game_year and len(good_matches) > 1:
                                    year_matches = []
                                    for result in good_matches:
                                        if (
                                            hasattr(result, "release_world")
                                            and result.release_world
                                        ):
                                            try:
                                                result_year = int(result.release_world)
                                                # Accept exact match or within 1
                                                # year (regional releases)
                                                if abs(result_year - game_year) <= 1:
                                                    year_matches.append(result)
                                            except (ValueError, TypeError):
                                                pass

                                    # If we found year matches, only consider those
                                    if year_matches:
                                        good_matches = year_matches

                                # If still multiple matches and we have platform
                                # data, prefer platform match
                                if game_platforms and len(good_matches) > 1:
                                    platform_matches_list = []
                                    for result in good_matches:
                                        # HLTB results have profile_platform field
                                        if hasattr(result, "profile_platform"):
                                            hltb_platform = result.profile_platform
                                            if platform_matches(
                                                hltb_platform, game_platforms
                                            ):
                                                platform_matches_list.append(result)

                                    # If we found platform matches, only consider those
                                    if platform_matches_list:
                                        good_matches = platform_matches_list

                                # Pick the match with highest similarity from
                                # remaining candidates
                                best_match = max(
                                    good_matches, key=lambda r: r.similarity
                                )
                                fetch_method = "name_search"
                                break  # Found a good match, stop trying

                    if best_match:
                        async with counter_lock:
                            success_count += 1
                        hltb_id = str(best_match.game_id)
                        hltb_name = best_match.game_name
                        similarity = getattr(best_match, "similarity", 1.0)

                        # Extract playtime values
                        main_story = self._get_hours(best_match, "main_story")
                        main_extra = self._get_hours(best_match, "main_extra")
                        completionist = self._get_hours(best_match, "completionist")

                        # Only print match details if not from direct Wikidata lookup
                        if not all_wikidata_hltb_ids:
                            self.stdout.write(
                                f"[{idx}/{game_count}] \u2713 {game_name}: "
                                f"{hltb_name} ({similarity:.2f}) - "
                                f"Main: {main_story}h, Extra: {main_extra}h, "
                                f"Complete: {completionist}h"
                            )

                        # Save to database if requested
                        if options.get("save"):
                            await sync_to_async(self._save_hltb_data)(
                                game_id,
                                game_igdb_id,
                                hltb_id,
                                hltb_name,
                                fetch_method,
                                similarity,
                                main_story,
                                main_extra,
                                completionist,
                            )
                    else:
                        async with counter_lock:
                            failure_count += 1
                        if all_wikidata_hltb_ids:
                            # Tried all Wikidata HLTB IDs but none worked
                            ids_tried = ", ".join(all_wikidata_hltb_ids)
                            error_message = (
                                f"Wikidata HLTB ID(s) [{ids_tried}] lookup failed"
                            )
                        elif use_name_search:
                            error_message = "No results found via name search"
                        else:
                            error_message = "No Wikidata HLTB ID available"
                        self.stdout.write(
                            self.style.WARNING(
                                f"[{idx}/{game_count}] \u2717 {game_name}: "
                                f"{error_message}"
                            )
                        )

                except Exception as e:
                    async with counter_lock:
                        failure_count += 1
                    error_message = str(e)[:100]
                    logger.warning(
                        "Failed to fetch HLTB data for '%s': %s",
                        game_name,
                        e,
                    )
                    self.stdout.write(
                        self.style.ERROR(
                            f"[{idx}/{game_count}] \u2717 {game_name}: {error_message}"
                        )
                    )

                # Write to CSV (thread-safe)
                if csv_writer:
                    async with csv_lock:
                        csv_writer.writerow(
                            [
                                game_rank,
                                game_name,
                                game_year or "",
                                fetch_method,
                                hltb_id,
                                hltb_name,
                                f"{similarity:.2f}" if similarity else "",
                                main_story or "",
                                main_extra or "",
                                completionist or "",
                                error_message,
                            ]
                        )
                        csv_file.flush()

                # Rate limiting delay
                await asyncio.sleep(delay)

        try:
            # Process all games concurrently
            tasks = [
                process_game(idx, game_data)
                for idx, game_data in enumerate(games_list, start=1)
            ]
            await asyncio.gather(*tasks)

        finally:
            if csv_file:
                csv_file.close()

        # Summary
        elapsed = time.time() - self.start_time
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\nCompleted in {elapsed:.1f} seconds"))
        self.stdout.write(f"\nTotal games: {game_count}")
        self.stdout.write(self.style.SUCCESS(f"HLTB data found: {success_count}"))
        if failure_count > 0:
            self.stdout.write(
                self.style.WARNING(f"HLTB data not found: {failure_count}")
            )

        if options.get("save"):
            self.stdout.write(self.style.SUCCESS("\n\u2713 Results saved to database"))
        if csv_path:
            self.stdout.write(f"\n\u2713 Results written to {csv_path}")

    def _get_games(self, options):
        """Get queryset of games to process based on options."""
        # Single game by name
        if options.get("game"):
            return Game.objects.filter(name__iexact=options["game"])

        # Single game by slug
        if options.get("slug"):
            return Game.objects.filter(slug=options["slug"])

        # Single game by ID
        if options.get("id"):
            return Game.objects.filter(id=options["id"])

        # All games with filtering
        games = Game.objects.all().order_by("rank")

        # Skip existing (unless force)
        if options.get("skip_existing") and not options.get("force"):
            games = games.filter(primary_hltb_game_data__isnull=True)
        elif not options.get("force"):
            # Default: only process games without HLTB data
            games = games.filter(primary_hltb_game_data__isnull=True)

        # Apply offset
        if options.get("offset"):
            games = games[options["offset"] :]

        # Apply limit
        if options.get("limit"):
            games = games[: options["limit"]]

        return games

    def _get_hours(self, result, field_name):
        """Extract hours from HLTB result, handling various attribute names."""
        # Try different attribute names the library might use
        possible_attrs = [
            field_name,
            f"{field_name}_seconds",
            f"gameplay_{field_name}",
        ]

        for attr in possible_attrs:
            value = getattr(result, attr, None)
            if value is not None and value > 0:
                # If value is in seconds, convert to hours
                if "seconds" in attr:
                    return round(value / 3600, 1)
                # If value is already in hours
                return round(value, 1)

        return None

    def _save_hltb_data(
        self,
        game_id,
        game_igdb_id,
        hltb_id,
        hltb_name,
        fetch_method,
        similarity,
        main_story,
        main_extra,
        completionist,
    ):
        """Save HLTB data to database."""
        game = Game.objects.get(id=game_id)

        # First, check for orphaned record with same igdb_id
        orphaned_record = HLTBGameData.objects.filter(
            igdb_id=game_igdb_id,
            game__isnull=True,
            is_primary=True,
        ).first()

        if orphaned_record:
            # Reconnect and update orphaned record
            HLTBGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            orphaned_record.game = game
            orphaned_record.hltb_id = hltb_id
            orphaned_record.hltb_name = hltb_name
            orphaned_record.fetch_method = fetch_method
            orphaned_record.similarity = (
                Decimal(str(similarity)) if similarity else None
            )
            orphaned_record.main_story_hours = (
                Decimal(str(main_story)) if main_story else None
            )
            orphaned_record.main_extra_hours = (
                Decimal(str(main_extra)) if main_extra else None
            )
            orphaned_record.completionist_hours = (
                Decimal(str(completionist)) if completionist else None
            )
            orphaned_record.save()
            hltb_data = orphaned_record
        else:
            # No orphaned record, create or update
            HLTBGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            hltb_data, created = HLTBGameData.objects.update_or_create(
                game=game,
                igdb_id=game_igdb_id,
                defaults={
                    "hltb_id": hltb_id,
                    "hltb_name": hltb_name,
                    "fetch_method": fetch_method,
                    "similarity": (Decimal(str(similarity)) if similarity else None),
                    "main_story_hours": (
                        Decimal(str(main_story)) if main_story else None
                    ),
                    "main_extra_hours": (
                        Decimal(str(main_extra)) if main_extra else None
                    ),
                    "completionist_hours": (
                        Decimal(str(completionist)) if completionist else None
                    ),
                    "is_primary": True,
                },
            )

        # Set primary relationship
        game.primary_hltb_game_data = hltb_data
        game.save(update_fields=["primary_hltb_game_data"])

        return hltb_data

    def _get_csv_path(self, output_path):
        """Get CSV output path (use provided or generate timestamp-based)."""
        if output_path:
            return output_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"hltb_data_{timestamp}.csv"

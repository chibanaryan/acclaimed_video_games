"""
Management command to fetch complete Wikipedia metadata for games.

Combines page lookup and genre scraping in one command - equivalent to the
"Fetch Wikipedia Pages" button in the admin UI.

Fetches:
- Wikipedia page titles (via Wikidata IDs or OpenSearch)
- Primary genre and all genres from Wikipedia infoboxes
- Wikidata IDs
"""

import csv
import logging
import time
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from games import config
from games.models import (
    Game,
    WikipediaGameData,
    WikipediaGenre,
)
from games.services.genre_normalizer import (
    canonicalize_genre_payload,
    get_or_create_genre,
)
from games.services.wiki_page_lookup_service import WikiPageLookupService
from games.services.wiki_genre_service import WikiGenreService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Fetch complete Wikipedia metadata (pages + genres) for games. "
        "Equivalent to the 'Fetch Wikipedia Pages' button."
    )

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
            help="Override delay between requests (default: auth-aware)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help=(
                "Output CSV file path "
                "(optional, default: wikipedia_metadata_TIMESTAMP.csv)"
            ),
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Save results to database (default: console only)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip games that already have Wikipedia page titles",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force refresh all games (ignore existing data)",
        )
        parser.add_argument(
            "--cleanup-orphans",
            action="store_true",
            help="Delete WikipediaGenre records with no linked games after processing",
        )
        parser.add_argument(
            "--skip-alternate-wikidata",
            action="store_true",
            help=(
                "Skip refreshing metadata for alternate WikipediaGameData records. "
                "By default, all WikipediaGameData records are refreshed to update "
                "HLTB IDs from alternate Wikidata entries."
            ),
        )

    def handle(self, *args, **options):
        self.start_time = time.time()

        # Show authentication status
        if settings.WIKIDATA_ACCESS_TOKEN:
            self.stdout.write(
                self.style.SUCCESS(
                    "✓ Using authenticated Wikidata requests "
                    f"({config.WIKIDATA_AUTHENTICATED_DELAY}s delay)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "⚠ Using unauthenticated Wikidata requests "
                    f"({config.WIKIDATA_UNAUTHENTICATED_DELAY}s delay)\n"
                    "  Set WIKIDATA_ACCESS_TOKEN for 2.5x faster processing"
                )
            )

        # Get games to process
        games = self._get_games(options)

        if not games.exists():
            self.stdout.write(self.style.ERROR("No games found to process"))
            return

        game_count = games.count()
        self.stdout.write(f"\nProcessing {game_count} games...")
        self.stdout.write("Fetching Wikipedia pages + genres...\n")

        # Initialize services
        page_service = WikiPageLookupService(delay=options.get("delay"))
        genre_service = WikiGenreService()

        # Prepare CSV output (only if --output is specified)
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
                    "Wikipedia Page Title",
                    "Lookup Source",
                    "Primary Genre",
                    "All Genres",
                    "Wikipedia URL",
                    "Error",
                ]
            )
            self.stdout.write(f"Writing results to: {csv_path}\n")

        # Process games
        success_count = 0
        failure_count = 0
        genre_success_count = 0
        genre_failure_count = 0

        try:
            for idx, game in enumerate(games, start=1):
                # Step 1: Lookup Wikipedia page
                page_result = page_service.lookup_page(
                    game.name, game.wikidata_id, game.year_of_release
                )

                page_title = ""
                lookup_source = ""
                wikipedia_url = ""
                primary_genre = ""
                all_genres = ""
                error_message = ""

                if page_result.success:
                    success_count += 1
                    page_title = page_result.page_title
                    lookup_source = page_result.lookup_source
                    wikipedia_url = page_result.wikipedia_url

                    self.stdout.write(
                        f"[{idx}/{game_count}] ✓ {game.name}: "
                        f"{page_title} ({lookup_source})"
                    )

                    # Save page data to database if requested
                    if options.get("save"):
                        wiki_game_data = self._save_page_data(
                            game, page_result, game.wikidata_id
                        )

                        # Step 2: Scrape genres from the Wikipedia page
                        try:
                            genre_result = genre_service.get_genre_from_url(
                                game.name, wikipedia_url
                            )

                            if genre_result.primary_genre:
                                genre_success_count += 1

                                (
                                    normalized_primary,
                                    normalized_all,
                                    normalized_all_str,
                                ) = canonicalize_genre_payload(
                                    genre_result.primary_genre,
                                    genre_result.all_genres,
                                )

                                primary_genre = normalized_primary or ""
                                all_genres = normalized_all_str

                                # Update WikipediaGameData with genres
                                wiki_game_data.primary_genre = normalized_primary
                                wiki_game_data.all_genres = normalized_all_str
                                wiki_game_data.save(
                                    update_fields=["primary_genre", "all_genres"]
                                )

                                # Create WikipediaGenre objects and link to game
                                wikipedia_genres = [
                                    get_or_create_genre(genre_name)
                                    for genre_name in normalized_all
                                ]
                                game.wikipedia_genres.set(wikipedia_genres)

                                self.stdout.write(
                                    f"  └─ Genre: {normalized_primary} "
                                    f"({len(normalized_all)} total)"
                                )
                            else:
                                genre_failure_count += 1
                                self.stdout.write(
                                    self.style.WARNING(
                                        "  └─ No genre found in Wikipedia page"
                                    )
                                )

                        except Exception as genre_error:
                            genre_failure_count += 1
                            logger.warning(
                                "Failed to scrape genres for '%s': %s",
                                game.name,
                                genre_error,
                            )
                            error_msg = str(genre_error)[:50]
                            self.stdout.write(
                                self.style.WARNING(
                                    f"  └─ Genre scraping error: {error_msg}"
                                )
                            )

                        # Refresh all alternate WikipediaGameData records by default
                        if not options.get("skip_alternate_wikidata"):
                            alt_updated, alt_hltb = (
                                self._refresh_alternate_wikidata_records(
                                    game, page_service
                                )
                            )
                            if alt_updated > 0:
                                self.stdout.write(
                                    f"  └─ Refreshed {alt_updated} alternate "
                                    f"Wikidata record(s)"
                                    + (
                                        f" ({alt_hltb} with HLTB ID)"
                                        if alt_hltb
                                        else ""
                                    )
                                )

                else:
                    failure_count += 1
                    error_message = page_result.error_message
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{idx}/{game_count}] ✗ {game.name}: {error_message}"
                        )
                    )

                    # Still refresh alternate records even if primary failed
                    # (they might have their own valid Wikidata IDs with HLTB IDs)
                    if options.get("save") and not options.get(
                        "skip_alternate_wikidata"
                    ):
                        alt_updated, alt_hltb = (
                            self._refresh_alternate_wikidata_records(game, page_service)
                        )
                        if alt_updated > 0:
                            self.stdout.write(
                                f"  └─ Refreshed {alt_updated} alternate "
                                f"Wikidata record(s)"
                                + (f" ({alt_hltb} with HLTB ID)" if alt_hltb else "")
                            )

                # Write to CSV
                if csv_writer:
                    csv_writer.writerow(
                        [
                            game.rank,
                            game.name,
                            page_title,
                            lookup_source,
                            primary_genre,
                            all_genres,
                            wikipedia_url,
                            error_message,
                        ]
                    )
                    csv_file.flush()  # Write immediately

        finally:
            if csv_file:
                csv_file.close()

        # Summary
        elapsed = time.time() - self.start_time
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\nCompleted in {elapsed:.1f} seconds"))
        self.stdout.write(f"\nTotal games: {game_count}")
        self.stdout.write(self.style.SUCCESS(f"Wikipedia pages found: {success_count}"))
        if failure_count > 0:
            self.stdout.write(
                self.style.WARNING(f"Wikipedia pages not found: {failure_count}")
            )

        if options.get("save") and success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Genres found: {genre_success_count}")
            )
            if genre_failure_count > 0:
                self.stdout.write(
                    self.style.WARNING(f"Genres not found: {genre_failure_count}")
                )

        if options.get("save"):
            self.stdout.write(self.style.SUCCESS("\n✓ Results saved to database"))

        if csv_path:
            self.stdout.write(f"\n✓ Results written to {csv_path}")

        # Cleanup orphan WikipediaGenre records if requested
        if options.get("cleanup_orphans"):
            orphan_genres = WikipediaGenre.objects.filter(
                games_with_wikipedia_genre__isnull=True
            )
            orphan_count = orphan_genres.count()
            if orphan_count > 0:
                orphan_names = list(orphan_genres.values_list("name", flat=True)[:10])
                orphan_genres.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Deleted {orphan_count} orphan WikipediaGenre records"
                    )
                )
                if orphan_names:
                    self.stdout.write(f"  Examples: {', '.join(orphan_names)}")
            else:
                self.stdout.write("\n✓ No orphan WikipediaGenre records found")

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
            games = games.filter(
                Q(primary_wikipedia_game_data__isnull=True)
                | Q(primary_wikipedia_game_data__page_title="")
            )
        elif not options.get("force"):
            # Default: only process games without Wikipedia data
            games = games.filter(
                Q(primary_wikipedia_game_data__isnull=True)
                | Q(primary_wikipedia_game_data__page_title="")
            )

        # Apply offset
        if options.get("offset"):
            games = games[options["offset"] :]

        # Apply limit
        if options.get("limit"):
            games = games[: options["limit"]]

        return games

    def _save_page_data(self, game, page_result, wikidata_id):
        """Save Wikipedia page data to database."""
        # First, check for orphaned record with same page_title
        orphaned_record = WikipediaGameData.objects.filter(
            page_title=page_result.page_title,
            game__isnull=True,
            is_primary=True,
        ).first()

        if orphaned_record:
            # Reconnect orphaned record
            # Unset is_primary on any existing records for this game
            WikipediaGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            # Reconnect the orphaned record
            orphaned_record.game = game
            orphaned_record.lookup_source = page_result.lookup_source
            # Update wikidata_id if available
            if wikidata_id:
                orphaned_record.wikidata_id = wikidata_id
            # Update hltb_id if available from Wikidata P2816
            if page_result.hltb_id:
                orphaned_record.hltb_id = page_result.hltb_id
            # Update steam_app_id if available from Wikidata P1733
            if page_result.steam_app_id:
                orphaned_record.steam_app_id = page_result.steam_app_id
            # Update wikiquote_page_title if available
            if page_result.wikiquote_page_title:
                orphaned_record.wikiquote_page_title = page_result.wikiquote_page_title
            orphaned_record.save(
                update_fields=[
                    "game",
                    "lookup_source",
                    "wikidata_id",
                    "hltb_id",
                    "steam_app_id",
                    "wikiquote_page_title",
                ]
            )
            wiki_game_data = orphaned_record
        else:
            # No orphaned record found, create or update
            # Unset is_primary on any existing records
            WikipediaGameData.objects.filter(game=game, is_primary=True).update(
                is_primary=False
            )

            # Create or update WikipediaGameData record
            defaults = {
                "lookup_source": page_result.lookup_source,
                "is_primary": True,
            }
            if wikidata_id:
                defaults["wikidata_id"] = wikidata_id
            if page_result.hltb_id:
                defaults["hltb_id"] = page_result.hltb_id
            if page_result.steam_app_id:
                defaults["steam_app_id"] = page_result.steam_app_id
            if page_result.wikiquote_page_title:
                defaults["wikiquote_page_title"] = page_result.wikiquote_page_title

            wiki_game_data, created = WikipediaGameData.objects.update_or_create(
                game=game,
                page_title=page_result.page_title,
                defaults=defaults,
            )

        # Set primary relationship
        game.primary_wikipedia_game_data = wiki_game_data
        game.save(update_fields=["primary_wikipedia_game_data"])

        return wiki_game_data

    def _get_csv_path(self, output_path):
        """Get CSV output path (use provided or generate timestamp-based)."""
        if output_path:
            return output_path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"wikipedia_metadata_{timestamp}.csv"

    def _refresh_alternate_wikidata_records(self, game, page_service):
        """
        Process all Wikidata IDs from game.all_wikidata_ids.

        Creates or updates WikipediaGameData records for all Wikidata IDs,
        ensuring HLTB IDs from any alternate Wikidata entry are available.

        Args:
            game: Game instance
            page_service: WikiPageLookupService instance

        Returns:
            Tuple of (records_updated, records_with_hltb_id)
        """
        records_updated = 0
        records_with_hltb_id = 0

        # Get all Wikidata IDs for this game
        all_wikidata_ids = game.all_wikidata_ids or []
        if not all_wikidata_ids and game.wikidata_id:
            # Fallback to single wikidata_id if all_wikidata_ids is empty
            all_wikidata_ids = [game.wikidata_id]

        # Skip the primary ID (already processed in main loop)
        primary_wikidata_id = game.wikidata_id
        alternate_ids = [wid for wid in all_wikidata_ids if wid != primary_wikidata_id]

        # Process each alternate Wikidata ID
        for wikidata_id in alternate_ids:
            if not wikidata_id or not wikidata_id.strip():
                continue

            # Look up metadata via Wikidata API
            wikidata_result = page_service._lookup_via_wikidata(wikidata_id)

            if wikidata_result:
                (
                    page_title,
                    hltb_id,
                    steam_app_id,
                    wikiquote_title,
                ) = wikidata_result

                # Create or update WikipediaGameData record for this alternate ID
                wiki_data, created = WikipediaGameData.objects.get_or_create(
                    game=game,
                    wikidata_id=wikidata_id,
                    defaults={
                        "page_title": page_title or "",
                        "is_primary": False,
                        "hltb_id": hltb_id,
                        "steam_app_id": steam_app_id,
                        "wikiquote_page_title": wikiquote_title,
                    },
                )

                if created:
                    records_updated += 1
                    if hltb_id:
                        records_with_hltb_id += 1
                        logger.info(
                            "Created WikipediaGameData for %s "
                            "(Wikidata %s) with HLTB ID: %s",
                            game.name,
                            wikidata_id,
                            hltb_id,
                        )
                else:
                    # Update existing record
                    update_fields = []

                    if page_title and page_title != wiki_data.page_title:
                        wiki_data.page_title = page_title
                        update_fields.append("page_title")

                    if hltb_id and hltb_id != wiki_data.hltb_id:
                        wiki_data.hltb_id = hltb_id
                        update_fields.append("hltb_id")
                        records_with_hltb_id += 1
                        logger.info(
                            "Updated HLTB ID for %s (Wikidata %s): %s",
                            game.name,
                            wikidata_id,
                            hltb_id,
                        )

                    if steam_app_id and steam_app_id != wiki_data.steam_app_id:
                        wiki_data.steam_app_id = steam_app_id
                        update_fields.append("steam_app_id")
                        logger.info(
                            "Updated Steam AppID for %s (Wikidata %s): %s",
                            game.name,
                            wikidata_id,
                            steam_app_id,
                        )

                    if (
                        wikiquote_title
                        and wikiquote_title != wiki_data.wikiquote_page_title
                    ):
                        wiki_data.wikiquote_page_title = wikiquote_title
                        update_fields.append("wikiquote_page_title")

                    if update_fields:
                        wiki_data.save(update_fields=update_fields)
                        records_updated += 1

        return records_updated, records_with_hltb_id

"""Tests for the fetch_wikipedia_metadata management command."""

import os
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from games.models import Game, WikipediaGameData
from games.services.wiki_genre_service import GenreResult, GenreSource
from games.services.wiki_page_lookup_service import PageLookupResult


class FetchWikipediaMetadataCommandTests(TestCase):
    """Tests for the fetch_wikipedia_metadata management command."""

    def setUp(self):
        """Set up test games."""
        self.game1 = Game.objects.create(
            name="Test Game 1",
            rank=1,
            wikidata_id="Q123456",
        )
        self.game2 = Game.objects.create(
            name="Test Game 2",
            rank=2,
        )

    def test_command_processes_all_games(self):
        """Test command processes all games by default."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game",
                page_title="Test Game",
                lookup_source="wikidata",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action", "Adventure"],
            )

            call_command("fetch_wikipedia_metadata", "--save", stdout=out)

        # Should process both games
        self.assertEqual(mock_page_service.lookup_page.call_count, 2)

    def test_command_processes_single_game_by_name(self):
        """Test command processes single game when --game is specified."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                stdout=out,
            )

        # Should only process one game
        self.assertEqual(mock_page_service.lookup_page.call_count, 1)

    def test_command_saves_page_data_and_genres_to_database(self):
        """Test command saves both page data and genres to database with --save flag."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action", "Adventure", "Puzzle"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Refresh from database and check WikipediaGameData was created
        self.game1.refresh_from_db()
        self.assertIsNotNone(self.game1.primary_wikipedia_game_data)
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.page_title, "Test Game 1")
        self.assertEqual(wiki_data.lookup_source, "wikidata")
        self.assertEqual(wiki_data.primary_genre, "Action")
        self.assertEqual(wiki_data.all_genres, "Action, Adventure, Puzzle")

        # Check WikipediaGenre objects were created
        self.assertEqual(self.game1.wikipedia_genres.count(), 3)
        genre_names = set(self.game1.wikipedia_genres.values_list("name", flat=True))
        self.assertEqual(genre_names, {"Action", "Adventure", "Puzzle"})

    def test_command_handles_page_lookup_failure(self):
        """Test command handles page lookup failures gracefully."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title=None,
                error_message="Page not found",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Refresh from database - should not be updated
        self.game1.refresh_from_db()
        self.assertIsNone(self.game1.primary_wikipedia_game_data)

        output = out.getvalue()
        self.assertIn("Page not found", output)

    def test_command_handles_genre_scraping_failure(self):
        """Test command handles genre scraping failures gracefully."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="opensearch",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.FAILED,
                primary_genre=None,
                all_genres=[],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Page data should be saved, but genres should be None
        self.game1.refresh_from_db()
        self.assertIsNotNone(self.game1.primary_wikipedia_game_data)
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.page_title, "Test Game 1")
        self.assertIsNone(wiki_data.primary_genre)

    def test_command_skips_existing_when_flag_set(self):
        """Test command skips games with existing data when --skip-existing is set."""
        # Set existing data on game1
        wiki_data = WikipediaGameData.objects.create(
            game=self.game1,
            page_title="Test Game 1",
            primary_genre="Existing Genre",
            is_primary=True,
        )
        self.game1.primary_wikipedia_game_data = wiki_data
        self.game1.save()

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 2",
                page_title="Test Game 2",
                lookup_source="wikidata",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--skip-existing",
                stdout=out,
            )

        # Should only process game2 (game1 has existing data)
        self.assertEqual(mock_page_service.lookup_page.call_count, 1)

    def test_command_reconnects_orphaned_records(self):
        """Test command reconnects orphaned WikipediaGameData records."""
        # Create orphaned record (no game link)
        orphaned_record = WikipediaGameData.objects.create(
            game=None,
            page_title="Test Game 1",
            primary_genre="Action",
            lookup_source="wikidata",
            is_primary=True,
        )

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Adventure",
                all_genres=["Adventure"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Check orphaned record was reconnected
        orphaned_record.refresh_from_db()
        self.assertEqual(orphaned_record.game, self.game1)
        self.game1.refresh_from_db()
        self.assertEqual(self.game1.primary_wikipedia_game_data.id, orphaned_record.id)

    def test_command_writes_csv_output(self):
        """Test command writes CSV output file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            output_path = tmp.name

        try:
            cmd = "games.management.commands.fetch_wikipedia_metadata"
            with mock.patch(
                f"{cmd}.WikiPageLookupService"
            ) as mock_page_service_class, mock.patch(
                f"{cmd}.WikiGenreService"
            ) as mock_genre_service_class:
                mock_page_service = mock_page_service_class.return_value
                mock_page_service.lookup_page.return_value = PageLookupResult(
                    game_name="Test Game 1",
                    page_title="Test Game 1",
                    lookup_source="opensearch",
                )

                mock_genre_service = mock_genre_service_class.return_value
                mock_genre_service.get_genre_from_url.return_value = GenreResult(
                    game_name="Test Game 1",
                    source=GenreSource.WIKIPEDIA,
                    primary_genre="Puzzle",
                    all_genres=["Puzzle", "Strategy"],
                )

                call_command(
                    "fetch_wikipedia_metadata",
                    "--game",
                    "Test Game 1",
                    "--save",
                    "--output",
                    output_path,
                )

            # Check CSV was written
            with open(output_path, "r") as f:
                content = f.read()

            self.assertIn("Game Name", content)
            self.assertIn("Wikipedia Page Title", content)
            self.assertIn("Primary Genre", content)
            self.assertIn("All Genres", content)
            self.assertIn("Test Game 1", content)
            self.assertIn("Puzzle", content)

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_command_respects_limit(self):
        """Test command respects --limit option."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game",
                page_title="Test Game",
                lookup_source="wikidata",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--limit",
                "1",
                stdout=out,
            )

        # Should only process 1 game due to limit
        self.assertEqual(mock_page_service.lookup_page.call_count, 1)

    def test_command_capitalizes_genre_names(self):
        """Test command properly capitalizes genre names."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            # Service returns lowercase genre names
            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="action-adventure",
                all_genres=["action-adventure", "rpg"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Check genres were capitalized
        self.game1.refresh_from_db()
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.primary_genre, "Action-adventure")
        self.assertEqual(wiki_data.all_genres, "Action-adventure, Rpg")

    def test_command_handles_genre_scraping_exception(self):
        """Test command handles exceptions during genre scraping."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.side_effect = Exception(
                "Network error"
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Page data should still be saved even though genre scraping failed
        self.game1.refresh_from_db()
        self.assertIsNotNone(self.game1.primary_wikipedia_game_data)
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.page_title, "Test Game 1")
        self.assertIsNone(wiki_data.primary_genre)

        output = out.getvalue()
        self.assertIn("Genre scraping error", output)

    def test_command_no_games_to_process(self):
        """Test command message when no games match criteria."""
        out = StringIO()

        call_command(
            "fetch_wikipedia_metadata",
            "--game",
            "NonExistentGame",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("No games found to process", output)

    def test_command_normalizes_genres(self):
        """Test command normalizes genre names to canonical forms."""
        from games.models import WikipediaGenre

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            # Service returns non-canonical genres
            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Survival horror",
                all_genres=["Survival horror", "First-person shooter", "Action"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Check genres were normalized
        self.game1.refresh_from_db()
        genre_names = set(self.game1.wikipedia_genres.values_list("name", flat=True))
        # "Survival horror" should normalize to "Horror"
        # "First-person shooter" should normalize to "First-Person Shooter"
        # "Action" stays as "Action"
        self.assertEqual(genre_names, {"Horror", "First-Person Shooter", "Action"})

        # Ensure only canonical genres exist in database
        self.assertFalse(WikipediaGenre.objects.filter(name="Survival horror").exists())
        self.assertTrue(WikipediaGenre.objects.filter(name="Horror").exists())

    def test_command_removes_duplicate_normalized_genres(self):
        """Test command removes duplicates after normalization."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            # Service returns genres that normalize to the same value
            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Platform",
                all_genres=["Platform", "Platformer", "Platform game"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # All three should normalize to "Platform" - only one genre should be linked
        self.game1.refresh_from_db()
        self.assertEqual(self.game1.wikipedia_genres.count(), 1)
        self.assertEqual(self.game1.wikipedia_genres.first().name, "Platform")

    def test_command_skips_invalid_genres(self):
        """Test command skips genres that map to None (invalid)."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
            )

            # Service returns genres including invalid ones
            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action", "(minigame)", "Various"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        # Invalid genres should be skipped
        self.game1.refresh_from_db()
        self.assertEqual(self.game1.wikipedia_genres.count(), 1)
        self.assertEqual(self.game1.wikipedia_genres.first().name, "Action")

    def test_cleanup_orphans_flag_deletes_unlinked_genres(self):
        """Test --cleanup-orphans flag deletes WikipediaGenre records with no games."""
        from games.models import WikipediaGenre

        # Clear all pre-existing genres first
        WikipediaGenre.objects.all().delete()

        # Create orphan genres (not linked to any game)
        WikipediaGenre.objects.create(name="Orphan Genre 1")
        WikipediaGenre.objects.create(name="Orphan Genre 2")
        linked_genre = WikipediaGenre.objects.create(name="Linked Genre")
        self.game1.wikipedia_genres.add(linked_genre)

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title=None,
                error_message="Not found",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--cleanup-orphans",
                stdout=out,
            )

        output = out.getvalue()

        # Should delete orphan genres
        self.assertIn("Deleted 2 orphan WikipediaGenre records", output)
        self.assertFalse(WikipediaGenre.objects.filter(name="Orphan Genre 1").exists())
        self.assertFalse(WikipediaGenre.objects.filter(name="Orphan Genre 2").exists())
        # Linked genre should still exist
        self.assertTrue(WikipediaGenre.objects.filter(name="Linked Genre").exists())

    def test_cleanup_orphans_no_orphans_message(self):
        """Test --cleanup-orphans shows message when no orphans exist."""
        from games.models import WikipediaGenre

        # Clear all pre-existing genres first
        WikipediaGenre.objects.all().delete()

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title=None,
                error_message="Not found",
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--cleanup-orphans",
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("No orphan WikipediaGenre records found", output)

    def test_command_saves_countries_and_game_modes(self):
        """Test command saves countries and game modes as M2M relationships."""
        from games.models import WikipediaCountry, WikipediaGameMode

        # Pre-create country and game mode records (normally created by
        # WikiPageLookupService during lookup, but we're mocking it)
        WikipediaCountry.objects.create(name="USA", wikidata_id="Q30")
        WikipediaCountry.objects.create(name="Japan", wikidata_id="Q17")
        WikipediaGameMode.objects.create(name="Single-player", wikidata_id="Q208850")
        WikipediaGameMode.objects.create(name="Multiplayer", wikidata_id="Q6895044")

        out = StringIO()

        with mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiPageLookupService"
        ) as mock_page_service_class, mock.patch(
            "games.management.commands.fetch_wikipedia_metadata.WikiGenreService"
        ) as mock_genre_service_class:
            mock_page_service = mock_page_service_class.return_value
            mock_page_service.lookup_page.return_value = PageLookupResult(
                game_name="Test Game 1",
                page_title="Test Game 1",
                lookup_source="wikidata",
                country_of_origin=["USA", "Japan"],
                game_modes=["Single-player", "Multiplayer"],
                wikiquote_page_title="Test Game 1",
            )

            mock_genre_service = mock_genre_service_class.return_value
            mock_genre_service.get_genre_from_url.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                stdout=out,
            )

        self.game1.refresh_from_db()

        # Check countries M2M
        countries = list(self.game1.wikipedia_countries.values_list("name", flat=True))
        self.assertEqual(sorted(countries), ["Japan", "USA"])

        # Check game modes M2M
        modes = list(self.game1.wikipedia_game_modes.values_list("name", flat=True))
        self.assertEqual(sorted(modes), ["Multiplayer", "Single-player"])

        # Check wikiquote was saved
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.wikiquote_page_title, "Test Game 1")

        # Verify records exist with correct wikidata IDs
        usa = WikipediaCountry.objects.get(name="USA")
        self.assertEqual(usa.wikidata_id, "Q30")

        japan = WikipediaCountry.objects.get(name="Japan")
        self.assertEqual(japan.wikidata_id, "Q17")

        single_player = WikipediaGameMode.objects.get(name="Single-player")
        self.assertEqual(single_player.wikidata_id, "Q208850")

        multiplayer = WikipediaGameMode.objects.get(name="Multiplayer")
        self.assertEqual(multiplayer.wikidata_id, "Q6895044")


class WikiPageLookupServiceTests(TestCase):
    """Tests for WikiPageLookupService internal logic."""

    def test_skips_deprecated_hltb_ids(self):
        """Test that deprecated P2816 (HLTB ID) claims are skipped."""
        from games.services.wiki_page_lookup_service import WikiPageLookupService

        service = WikiPageLookupService(delay=0)

        # Mock the Wikidata API response for NHL '94 (Q607073)
        # which has deprecated IDs 6571 and 16527, and normal ID 15544
        mock_response_data = {
            "entities": {
                "Q607073": {
                    "sitelinks": {
                        "enwiki": {"title": "NHL 94"},
                    },
                    "claims": {
                        "P2816": [
                            {
                                "rank": "deprecated",
                                "mainsnak": {
                                    "datavalue": {"value": "6571"},
                                },
                            },
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "datavalue": {"value": "15544"},
                                },
                            },
                            {
                                "rank": "deprecated",
                                "mainsnak": {
                                    "datavalue": {"value": "16527"},
                                },
                            },
                        ],
                    },
                }
            }
        }

        with mock.patch.object(service, "_make_request") as mock_request:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_request.return_value = mock_response

            result = service._lookup_via_wikidata("Q607073")

        # Should return the normal (non-deprecated) HLTB ID
        self.assertIsNotNone(result)
        page_title, hltb_id, steam_app_id, game_modes, countries, wikiquote = result
        self.assertEqual(page_title, "NHL 94")
        self.assertEqual(hltb_id, "15544")  # The normal rank ID, not deprecated

    def test_prefers_preferred_rank_over_normal(self):
        """Test that 'preferred' rank P2816 claims take priority over 'normal'."""
        from games.services.wiki_page_lookup_service import WikiPageLookupService

        service = WikiPageLookupService(delay=0)

        mock_response_data = {
            "entities": {
                "Q12345": {
                    "sitelinks": {
                        "enwiki": {"title": "Test Game"},
                    },
                    "claims": {
                        "P2816": [
                            {
                                "rank": "normal",
                                "mainsnak": {
                                    "datavalue": {"value": "111"},
                                },
                            },
                            {
                                "rank": "preferred",
                                "mainsnak": {
                                    "datavalue": {"value": "222"},
                                },
                            },
                        ],
                    },
                }
            }
        }

        with mock.patch.object(service, "_make_request") as mock_request:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_request.return_value = mock_response

            result = service._lookup_via_wikidata("Q12345")

        # Should return the preferred HLTB ID
        self.assertIsNotNone(result)
        page_title, hltb_id, steam_app_id, game_modes, countries, wikiquote = result
        self.assertEqual(hltb_id, "222")  # Preferred rank

    def test_returns_none_when_all_hltb_ids_deprecated(self):
        """Test that None is returned for HLTB ID when all claims are deprecated."""
        from games.services.wiki_page_lookup_service import WikiPageLookupService

        service = WikiPageLookupService(delay=0)

        mock_response_data = {
            "entities": {
                "Q99999": {
                    "sitelinks": {
                        "enwiki": {"title": "All Deprecated Game"},
                    },
                    "claims": {
                        "P2816": [
                            {
                                "rank": "deprecated",
                                "mainsnak": {
                                    "datavalue": {"value": "111"},
                                },
                            },
                            {
                                "rank": "deprecated",
                                "mainsnak": {
                                    "datavalue": {"value": "222"},
                                },
                            },
                        ],
                    },
                }
            }
        }

        with mock.patch.object(service, "_make_request") as mock_request:
            mock_response = mock.MagicMock()
            mock_response.json.return_value = mock_response_data
            mock_request.return_value = mock_response

            result = service._lookup_via_wikidata("Q99999")

        # Page should be found but HLTB ID should be None
        self.assertIsNotNone(result)
        page_title, hltb_id, steam_app_id, game_modes, countries, wikiquote = result
        self.assertEqual(page_title, "All Deprecated Game")
        self.assertIsNone(hltb_id)  # No valid HLTB ID

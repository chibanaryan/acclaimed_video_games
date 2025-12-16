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

            call_command(
                "fetch_wikipedia_metadata", "--no-output", "--save", stdout=out
            )

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
                "--no-output",
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
                all_genres=["Action", "Adventure", "RPG"],
            )

            call_command(
                "fetch_wikipedia_metadata",
                "--game",
                "Test Game 1",
                "--save",
                "--no-output",
                stdout=out,
            )

        # Refresh from database and check WikipediaGameData was created
        self.game1.refresh_from_db()
        self.assertIsNotNone(self.game1.primary_wikipedia_game_data)
        wiki_data = self.game1.primary_wikipedia_game_data
        self.assertEqual(wiki_data.page_title, "Test Game 1")
        self.assertEqual(wiki_data.lookup_source, "wikidata")
        self.assertEqual(wiki_data.primary_genre, "Action")
        self.assertEqual(wiki_data.all_genres, "Action, Adventure, RPG")

        # Check WikipediaGenre objects were created
        self.assertEqual(self.game1.wikipedia_genres.count(), 3)
        genre_names = set(self.game1.wikipedia_genres.values_list("name", flat=True))
        self.assertEqual(genre_names, {"Action", "Adventure", "RPG"})

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
                "--no-output",
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
                "--no-output",
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
                "--no-output",
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
                "--no-output",
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
                "--no-output",
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
                "--no-output",
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
                "--no-output",
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
            "--no-output",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("No games found to process", output)

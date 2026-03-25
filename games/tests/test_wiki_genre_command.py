"""Tests for the get_wiki_genres management command."""

import os
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from games.models import Game, WikipediaGameData
from games.services.wiki_genre_service import GenreResult, GenreSource


class GetWikiGenresCommandTests(TestCase):
    """Tests for the get_wiki_genres management command."""

    def setUp(self):
        """Set up test games."""
        self.game1 = Game.objects.create(
            name="Test Game 1",
            rank=1,
        )
        self.game2 = Game.objects.create(
            name="Test Game 2",
            rank=2,
        )

    def test_command_processes_all_games(self):
        """Test command processes all games by default."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action", "Adventure"],
                source_url="https://en.wikipedia.org/wiki/Test_Game",
            )

            call_command("get_wiki_genres", "--no-output", stdout=out)

        # Should process both games
        self.assertEqual(mock_service.get_genre.call_count, 2)

    def test_command_processes_single_game_by_name(self):
        """Test command processes single game when --game is specified."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
                source_url="https://en.wikipedia.org/wiki/Test_Game_1",
            )

            call_command(
                "get_wiki_genres", "--game", "Test Game 1", "--no-output", stdout=out
            )

        # Should only process one game
        self.assertEqual(mock_service.get_genre.call_count, 1)
        mock_service.get_genre.assert_called_with("Test Game 1", year=None)

    def test_command_processes_single_game_by_id(self):
        """Test command processes single game when --id is specified."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
            )

            call_command(
                "get_wiki_genres", "--id", str(self.game1.id), "--no-output", stdout=out
            )

        self.assertEqual(mock_service.get_genre.call_count, 1)

    def test_command_respects_limit(self):
        """Test command respects --limit option."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
            )

            call_command("get_wiki_genres", "--limit", "1", "--no-output", stdout=out)

        # Should only process 1 game due to limit
        self.assertEqual(mock_service.get_genre.call_count, 1)

    def test_command_saves_to_database_when_save_flag_set(self):
        """Test command saves results to database with --save flag."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action", "Adventure", "RPG"],
                source_url="https://en.wikipedia.org/wiki/Test_Game_1",
            )

            call_command(
                "get_wiki_genres",
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
        self.assertEqual(wiki_data.primary_genre, "Action")
        self.assertEqual(wiki_data.all_genres, "Action, Adventure, Role-Playing")

    def test_command_does_not_save_failed_results(self):
        """Test command does not save failed results to database."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.FAILED,
                error_message="Not found",
            )

            call_command(
                "get_wiki_genres",
                "--game",
                "Test Game 1",
                "--save",
                "--no-output",
                stdout=out,
            )

        # Refresh from database - should not be updated
        self.game1.refresh_from_db()
        self.assertIsNone(self.game1.primary_wikipedia_game_data)

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
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
            )

            call_command(
                "get_wiki_genres", "--skip-existing", "--no-output", stdout=out
            )

        # Should only process game2 (game1 has existing data)
        self.assertEqual(mock_service.get_genre.call_count, 1)
        mock_service.get_genre.assert_called_with("Test Game 2", year=None)

    def test_command_writes_csv_output(self):
        """Test command writes CSV output file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            output_path = tmp.name

        try:
            with mock.patch(
                "games.management.commands.get_wiki_genres.WikiGenreService"
            ) as mock_service_class:
                mock_service = mock_service_class.return_value
                mock_service.get_genre.return_value = GenreResult(
                    game_name="Test Game 1",
                    source=GenreSource.WIKIPEDIA,
                    primary_genre="Action",
                    all_genres=["Action", "Adventure"],
                    source_url="https://en.wikipedia.org/wiki/Test_Game_1",
                )

                call_command(
                    "get_wiki_genres",
                    "--game",
                    "Test Game 1",
                    "--output",
                    output_path,
                )

            # Check CSV was written
            with open(output_path, "r") as f:
                content = f.read()

            self.assertIn("Original Title", content)
            self.assertIn("Primary Genre", content)
            self.assertIn("All Genres", content)
            self.assertIn("Source URL", content)
            self.assertIn("Test Game 1", content)
            self.assertIn("Action", content)
            self.assertIn("Action, Adventure", content)

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    def test_command_handles_game_not_found(self):
        """Test command handles non-existent game gracefully."""
        out = StringIO()

        with mock.patch("games.management.commands.get_wiki_genres.WikiGenreService"):
            call_command(
                "get_wiki_genres",
                "--game",
                "NonExistentGame",
                "--no-output",
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("No games to process", output)

    def test_command_uses_custom_delay(self):
        """Test command uses custom delay when specified."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Action",
                all_genres=["Action"],
            )

            call_command(
                "get_wiki_genres",
                "--game",
                "Test Game 1",
                "--delay",
                "2.5",
                "--no-output",
                stdout=out,
            )

        # Check service was initialized with custom delay
        mock_service_class.assert_called_once()
        call_kwargs = mock_service_class.call_args[1]
        self.assertEqual(call_kwargs["delay"], 2.5)

    def test_command_shows_progress_output(self):
        """Test command shows progress in output."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.WIKIPEDIA,
                primary_genre="Puzzle",
                all_genres=["Puzzle", "Strategy"],
            )

            call_command(
                "get_wiki_genres",
                "--game",
                "Test Game 1",
                "--no-output",
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("Test Game 1", output)
        self.assertIn("Puzzle", output)
        self.assertIn("2 genres", output)  # Shows genre count
        self.assertIn("successful", output)

    def test_command_shows_failure_output(self):
        """Test command shows failure messages in output."""
        out = StringIO()

        with mock.patch(
            "games.management.commands.get_wiki_genres.WikiGenreService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_genre.return_value = GenreResult(
                game_name="Test Game 1",
                source=GenreSource.FAILED,
                error_message="Page not found",
            )

            call_command(
                "get_wiki_genres",
                "--game",
                "Test Game 1",
                "--no-output",
                stdout=out,
            )

        output = out.getvalue()
        self.assertIn("FAILED", output)
        self.assertIn("Page not found", output)

    def test_command_no_games_to_process_with_skip_existing(self):
        """Test command message when all games already have data."""
        # Set existing data on both games
        wiki_data1 = WikipediaGameData.objects.create(
            game=self.game1,
            page_title="Test Game 1",
            primary_genre="Genre 1",
            is_primary=True,
        )
        self.game1.primary_wikipedia_game_data = wiki_data1
        self.game1.save()

        wiki_data2 = WikipediaGameData.objects.create(
            game=self.game2,
            page_title="Test Game 2",
            primary_genre="Genre 2",
            is_primary=True,
        )
        self.game2.primary_wikipedia_game_data = wiki_data2
        self.game2.save()

        out = StringIO()

        call_command("get_wiki_genres", "--skip-existing", "--no-output", stdout=out)

        output = out.getvalue()
        self.assertIn("No games to process", output)

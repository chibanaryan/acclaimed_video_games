"""Tests for get_quotes management command."""

import csv
import json
import os
import tempfile
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from games.models import Game, GameQuote
from games.services.quote_service import QuoteResult, QuoteSource


class GetQuotesCommandTest(TestCase):
    """Test get_quotes management command."""

    def setUp(self):
        """Set up test fixtures."""
        self.game1 = Game.objects.create(
            name="Portal",
            slug="portal",
            rank=1,
            year_of_release=2007,
        )
        self.game2 = Game.objects.create(
            name="Half-Life",
            slug="half-life",
            rank=2,
            year_of_release=1998,
        )

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_single_game_mode_by_name(self, mock_get_quotes):
        """Test processing single game by name."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[
                {"text": "The cake is a lie.", "attribution": "GLaDOS"},
            ],
            source_url="https://example.com",
        )

        out = StringIO()
        call_command(
            "get_quotes",
            "--game",
            "Portal",
            "--save",
            "--no-output",
            stdout=out,
        )

        # Verify quote was saved
        self.assertEqual(self.game1.quotes.count(), 1)
        quote = self.game1.quotes.first()
        self.assertEqual(quote.text, "The cake is a lie.")
        self.assertEqual(quote.attribution, "GLaDOS")
        self.assertTrue(quote.is_featured)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_single_game_mode_by_slug(self, mock_get_quotes):
        """Test processing single game by slug."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote from slug test", "attribution": "Character"}],
        )

        call_command(
            "get_quotes",
            "--slug",
            self.game1.slug,
            "--save",
            "--no-output",
        )

        self.assertEqual(self.game1.quotes.count(), 1)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_single_game_mode_by_id(self, mock_get_quotes):
        """Test processing single game by database ID."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote", "attribution": "Character"}],
        )

        out = StringIO()
        call_command(
            "get_quotes",
            "--id",
            self.game1.id,
            "--save",
            "--no-output",
            stdout=out,
        )

        self.assertEqual(self.game1.quotes.count(), 1)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_marks_first_quote_as_featured(self, mock_get_quotes):
        """Test that first quote is marked as featured."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[
                {"text": "Quote 1", "attribution": "Character 1"},
                {"text": "Quote 2", "attribution": "Character 2"},
                {"text": "Quote 3", "attribution": "Character 3"},
            ],
        )

        call_command(
            "get_quotes",
            "--game",
            "Portal",
            "--save",
            "--no-output",
        )

        # Check quotes
        self.assertEqual(self.game1.quotes.count(), 3)

        # First quote should be featured
        first_quote = self.game1.quotes.filter(text="Quote 1").first()
        self.assertTrue(first_quote.is_featured)

        # Other quotes should not be featured
        other_quotes = self.game1.quotes.exclude(text="Quote 1")
        for quote in other_quotes:
            self.assertFalse(quote.is_featured)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_skips_duplicate_quotes(self, mock_get_quotes):
        """Test that duplicate quotes are skipped."""
        # Create existing quote
        GameQuote.objects.create(
            game=self.game1,
            text="The cake is a lie.",
            attribution="GLaDOS",
            is_featured=True,
        )

        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[
                {"text": "The cake is a lie.", "attribution": "GLaDOS"},
                {"text": "New quote", "attribution": "GLaDOS"},
            ],
        )

        call_command(
            "get_quotes",
            "--game",
            "Portal",
            "--save",
            "--no-output",
        )

        # Should have 2 quotes total (existing + 1 new)
        self.assertEqual(self.game1.quotes.count(), 2)

        # Verify only one "The cake is a lie" quote exists
        self.assertEqual(self.game1.quotes.filter(text="The cake is a lie.").count(), 1)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_csv_output_format(self, mock_get_quotes):
        """Test CSV export format."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote", "attribution": "Character"}],
            source_url="https://example.com",
        )

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            temp_path = f.name

        try:
            call_command(
                "get_quotes",
                "--game",
                "Portal",
                "--output",
                temp_path,
            )

            # Read and verify CSV
            with open(temp_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Rank"], "1")
            self.assertEqual(rows[0]["Game Name"], "Portal")
            self.assertEqual(rows[0]["Source"], "Wikiquote")
            self.assertEqual(rows[0]["Quote Count"], "1")
            self.assertEqual(rows[0]["Source URL"], "https://example.com")

            # Verify quotes JSON
            quotes = json.loads(rows[0]["Quotes JSON"])
            self.assertEqual(len(quotes), 1)
            self.assertEqual(quotes[0]["text"], "Quote")
        finally:
            os.unlink(temp_path)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_failed_result_recorded_in_csv(self, mock_get_quotes):
        """Test that failed results are recorded in CSV."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Portal",
            source=QuoteSource.FAILED,
            error_message="Page not found on Wikiquote",
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            temp_path = f.name

        try:
            call_command(
                "get_quotes",
                "--game",
                "Portal",
                "--output",
                temp_path,
            )

            with open(temp_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Source"], "Failed")
            self.assertEqual(rows[0]["Quote Count"], "0")
            self.assertEqual(rows[0]["Error"], "Page not found on Wikiquote")
        finally:
            os.unlink(temp_path)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_skip_existing_mode(self, mock_get_quotes):
        """Test that --skip-existing skips games with quotes."""
        # Add quote to game1
        GameQuote.objects.create(
            game=self.game1,
            text="Existing quote",
            attribution="Character",
        )

        mock_get_quotes.return_value = QuoteResult(
            game_name="Game",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote", "attribution": "Character"}],
        )

        out = StringIO()
        call_command(
            "get_quotes",
            "--skip-existing",
            "--save",
            "--no-output",
            stdout=out,
        )

        # Should have only called service for game2 (game1 has quotes)
        self.assertEqual(mock_get_quotes.call_count, 1)
        mock_get_quotes.assert_called_with("Half-Life", year=1998)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_limit_and_offset(self, mock_get_quotes):
        """Test --limit and --offset options."""
        # Create more games
        Game.objects.create(name="Game 3", rank=3)
        Game.objects.create(name="Game 4", rank=4)

        mock_get_quotes.return_value = QuoteResult(
            game_name="Game",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote", "attribution": "Character"}],
        )

        out = StringIO()
        call_command(
            "get_quotes",
            "--offset",
            "1",
            "--limit",
            "2",
            "--save",
            "--no-output",
            stdout=out,
        )

        # Should process games at rank 2 and 3 (offset 1, limit 2)
        self.assertEqual(mock_get_quotes.call_count, 2)

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_no_games_to_process(self, mock_get_quotes):
        """Test warning when no games to process."""
        # Delete all games
        Game.objects.all().delete()

        out = StringIO()
        call_command(
            "get_quotes",
            "--save",
            "--no-output",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("No games to process", output)
        mock_get_quotes.assert_not_called()

    @patch("games.management.commands.get_quotes.QuoteService.get_quotes")
    def test_resume_mode_skips_processed_games(self, mock_get_quotes):
        """Test --resume mode skips already-processed games."""
        mock_get_quotes.return_value = QuoteResult(
            game_name="Game",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote", "attribution": "Character"}],
        )

        # Create initial CSV with game1
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
            temp_path = f.name
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Rank",
                    "Game Name",
                    "Source",
                    "Quote Count",
                    "Quotes JSON",
                    "Source URL",
                    "Error",
                ]
            )
            writer.writerow([1, "Portal", "Wikiquote", 1, "[]", "", ""])

        try:
            out = StringIO()
            call_command(
                "get_quotes",
                "--resume",
                temp_path,
                "--save",
                stdout=out,
            )

            # Should only process game2 (game1 already in CSV)
            self.assertEqual(mock_get_quotes.call_count, 1)
            mock_get_quotes.assert_called_with("Half-Life", year=1998)

            output = out.getvalue()
            self.assertIn("1 games already processed", output)
        finally:
            os.unlink(temp_path)

    def test_default_attribution(self):
        """Test that default attribution is used when not provided."""
        from games.services.quote_service import QuoteResult, QuoteSource

        result = QuoteResult(
            game_name="Test",
            source=QuoteSource.WIKIQUOTE,
            quotes=[{"text": "Quote without attribution"}],
        )

        # Save to DB
        command = __import__(
            "games.management.commands.get_quotes", fromlist=["Command"]
        ).Command()
        command._save_quotes_to_db(self.game1, result.quotes)

        quote = self.game1.quotes.first()
        self.assertEqual(quote.attribution, "In-game dialogue")

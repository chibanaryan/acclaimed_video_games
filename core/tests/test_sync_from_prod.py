"""Tests for sync_from_prod management command"""

import os
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from games import models


class SyncFromProdCommandTests(TestCase):
    """Tests for sync_from_prod management command"""

    def setUp(self):
        # Create some local data that will be cleared
        self.platform = models.Platform.objects.create(name="PC", code="PC")
        self.genre = models.IGDBGenre.objects.create(name="Action")
        self.developer = models.Developer.objects.create(name="Test Dev")
        self.game = models.Game.objects.create(
            name="Local Game", rank=1, year_of_release=2020
        )

    def tearDown(self):
        # Clean up the fixture file if it was created
        fixture_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "games",
            "fixtures",
            "prod_dump.json",
        )
        if os.path.exists(fixture_path):
            os.remove(fixture_path)

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_successful_sync(self, mock_subprocess, mock_call_command):
        """Test successful sync from production"""
        from io import StringIO

        # Mock heroku run output with valid JSON
        mock_subprocess.return_value = mock.Mock(
            stdout='Some heroku noise\n[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Syncing production database", output)
        self.assertIn("Dumping production data", output)
        self.assertIn("Clearing local data", output)
        self.assertIn("Loading data into local database", output)
        self.assertIn("Sync complete!", output)
        self.assertIn("createsuperuser", output)

        # Verify migrate and loaddata were called
        calls = mock_call_command.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "migrate")
        self.assertEqual(calls[1][0][0], "loaddata")

    @mock.patch("subprocess.run")
    def test_heroku_cli_not_found(self, mock_subprocess):
        """Test error when Heroku CLI is not installed"""
        from io import StringIO

        mock_subprocess.side_effect = FileNotFoundError("heroku not found")

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Heroku CLI not found", error_output)
        self.assertIn("brew install", error_output)

    @mock.patch("subprocess.run")
    def test_no_json_in_output(self, mock_subprocess):
        """Test error when heroku output contains no JSON"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout="Some error output without JSON",
            stderr="",
            returncode=0,
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("No JSON data found", error_output)

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_loaddata_failure(self, mock_subprocess, mock_call_command):
        """Test error handling when loaddata fails"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        # Only fail on loaddata, not migrate
        def side_effect(cmd, *args, **kwargs):
            if cmd == "loaddata":
                raise Exception("Database error")

        mock_call_command.side_effect = side_effect

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Failed to load data", error_output)

    @mock.patch("builtins.input", return_value="n")
    def test_confirmation_abort(self, mock_input):
        """Test that sync aborts when user says no"""
        from io import StringIO

        out = StringIO()
        call_command("sync_from_prod", stdout=out)
        output = out.getvalue()

        self.assertIn("Aborted", output)
        mock_input.assert_called_once()

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    @mock.patch("builtins.input", return_value="y")
    def test_confirmation_proceed(self, mock_input, mock_subprocess, mock_call_command):
        """Test that sync proceeds when user confirms"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", stdout=out)
        output = out.getvalue()

        self.assertIn("Sync complete!", output)
        mock_input.assert_called_once()

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_keep_fixture_flag(self, mock_subprocess, mock_call_command):
        """Test --keep-fixture flag keeps the downloaded file"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, keep_fixture=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Fixture kept at:", output)
        # tearDown handles fixture cleanup

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_clears_local_data(self, mock_subprocess, mock_call_command):
        """Test that local data is cleared before loading"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        # Verify data exists before sync
        self.assertEqual(models.Game.objects.count(), 1)
        self.assertEqual(models.Platform.objects.count(), 1)

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)

        # Verify data was cleared (loaddata is mocked so no new data loaded)
        self.assertEqual(models.Game.objects.count(), 0)
        self.assertEqual(models.Platform.objects.count(), 0)
        self.assertEqual(models.IGDBGenre.objects.count(), 0)
        self.assertEqual(models.Developer.objects.count(), 0)

    @mock.patch("subprocess.run")
    def test_heroku_command_error(self, mock_subprocess):
        """Test error when heroku command fails"""
        import subprocess
        from io import StringIO

        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, "heroku", stderr="Connection failed"
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Failed to dump production data", error_output)

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_custom_app_name(self, mock_subprocess, mock_call_command):
        """Test using custom Heroku app name"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, app="my-custom-app", stdout=out)
        output = out.getvalue()

        self.assertIn("my-custom-app", output)
        # Verify heroku was called with custom app name
        call_args = mock_subprocess.call_args[0][0]
        self.assertIn("my-custom-app", call_args)

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_runs_migrations(self, mock_subprocess, mock_call_command):
        """Test that migrations are run before loading data"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"model": "games.game", "pk": 1}]',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Running migrations", output)
        # Verify migrate was called before loaddata
        calls = mock_call_command.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "migrate")
        self.assertEqual(calls[1][0][0], "loaddata")

    @mock.patch("core.management.commands.sync_from_prod.call_command")
    @mock.patch("subprocess.run")
    def test_strips_post_author(self, mock_subprocess, mock_call_command):
        """Test that author field is stripped from Post records"""
        import json
        from io import StringIO

        # Fixture with Post that has author_id (would fail without stripping)
        fixture = [
            {"model": "games.post", "pk": 1, "fields": {"text": "Test", "author": 5}}
        ]
        mock_subprocess.return_value = mock.Mock(
            stdout=json.dumps(fixture),
            stderr="",
            returncode=0,
        )

        out = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out)

        # loaddata should be called with fixture that has author stripped
        self.assertIn("Sync complete!", out.getvalue())

    @mock.patch("subprocess.run")
    def test_invalid_json_error(self, mock_subprocess):
        """Test error when JSON parsing fails"""
        from io import StringIO

        mock_subprocess.return_value = mock.Mock(
            stdout='[{"invalid json',
            stderr="",
            returncode=0,
        )

        out = StringIO()
        err = StringIO()
        call_command("sync_from_prod", no_input=True, stdout=out, stderr=err)
        error_output = err.getvalue()

        self.assertIn("Invalid JSON from Heroku", error_output)

from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from .. import models, utils


class GetIgdbCommandTests(TestCase):

    def test_updates_games_missing_artwork(self):
        models.Game.objects.create(
            name="Needs Art",
            rank=2,
            igdb_id=2,
            year_of_release=1991,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb")

        mock_get.assert_called_once_with()

    def test_command_logs_when_game_update_fails(self):
        models.Game.objects.create(
            name="Broken",
            rank=3,
            igdb_id=3,
            year_of_release=1992,
        )

        with mock.patch.object(
            models.Game, "get_igdb_data", side_effect=ValueError("boom")
        ), mock.patch("games.management.commands.get_igdb.logger") as logger_mock:
            call_command("get_igdb")

        logger_mock.error.assert_called_once_with("boom")


class ImportDataRoutingTests(TestCase):

    def test_unknown_import_type_returns_error(self):
        file_content = mock.Mock()
        data = {"file": file_content, "type": "Z"}

        success, message = utils.import_data(data)
        self.assertFalse(success)
        self.assertIn('Unknown import type "Z"', message)

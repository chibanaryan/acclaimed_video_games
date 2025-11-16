from io import BytesIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from .. import models, utils


class GetIgdbCommandTests(TestCase):

    def test_updates_games_missing_artwork(self):
        with_art = models.Game.objects.create(
            name="Has Art",
            rank=1,
            igdb_id=1,
            year_of_release=1990,
            igdb_artwork_id="abc",
        )
        without_art = models.Game.objects.create(
            name="Needs Art",
            rank=2,
            igdb_id=2,
            year_of_release=1991,
        )

        with mock.patch.object(models.Game, "get_igdb_data") as mock_get:
            call_command("get_igdb")

        # Only games without artwork should trigger an update
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[0], ())
        self.assertEqual(mock_get.call_args_list[0][0], ())
        self.assertEqual(mock_get.call_args_list[0][1], {})
        self.assertEqual(mock_get.call_args_list[0][0], ())


class ImportDataRoutingTests(TestCase):

    def test_unknown_import_type_returns_error(self):
        file_content = BytesIO(b"")
        data = {
            "file": file_content,
            "type": "Z",
        }

        success, message = utils.import_data(data)
        self.assertFalse(success)
        self.assertIn('Unknown import type "Z"', message)

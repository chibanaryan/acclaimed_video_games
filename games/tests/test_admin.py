from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from games import admin, models


class GameAdminTests(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.admin = admin.GameAdmin(models.Game, self.site)

    def test_save_model_fetches_fresh_igdb_data(self):
        game = mock.Mock(spec=models.Game)
        self.admin.save_model(request=None, obj=game, form=None, change=False)
        game.get_igdb_data.assert_called_once_with(cache_results=False)
        game.save.assert_called_once()

    def test_genres_helper_returns_joined_names(self):
        genre = models.Genre.objects.create(name="Action")
        game = models.Game.objects.create(
            name="Sample",
            rank=1,
            igdb_id=1,
            year_of_release=1990,
        )
        game.genres.add(genre)
        value = self.admin._genres(game)
        self.assertEqual(value, "Action")

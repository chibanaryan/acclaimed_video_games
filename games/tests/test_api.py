from django.contrib.flatpages.models import FlatPage
from django.test import TestCase
from rest_framework.test import APIClient

from .. import models
from ..api import serializers


class GameListApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.platform_pc = models.Platform.objects.create(code="PC", name="PC")
        self.platform_ps = models.Platform.objects.create(code="PS", name="PlayStation")
        self.genre_action = models.Genre.objects.create(name="Action")
        self.genre_adventure = models.Genre.objects.create(name="Adventure")

        developer = models.Developer.objects.create(name="Studio", igdb_id=10)
        self.alias = models.DeveloperAlias.objects.create(
            developer=developer, name="Studio Alias", igdb_id=11
        )

        self.game1 = models.Game.objects.create(
            name="Alpha Quest",
            rank=1,
            igdb_id=1001,
            year_of_release=2000,
            slug="alpha-quest",
        )
        self.game1.platforms.add(self.platform_pc)
        self.game1.genres.add(self.genre_action)
        self.game1.developers.add(self.alias)

        self.game2 = models.Game.objects.create(
            name="Beta Saga",
            rank=2,
            igdb_id=1002,
            year_of_release=2010,
            slug="beta-saga",
        )
        self.game2.platforms.add(self.platform_ps)
        self.game2.genres.add(self.genre_adventure)

    def _get_game_names(self, **params):
        response = self.client.get("/api/games/", params)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"] if "results" in data else data
        return [item["name"] for item in results]

    def test_filter_by_platform(self):
        names = self._get_game_names(platforms=str(self.platform_ps.id))
        self.assertEqual(names, ["Beta Saga"])

    def test_filter_by_genres_all_option(self):
        self.game1.genres.add(self.genre_adventure)
        names = self._get_game_names(
            genres=f"{self.genre_action.id},{self.genre_adventure.id}",
        )
        self.assertEqual(names, ["Alpha Quest"])

    def test_filter_by_developer(self):
        names = self._get_game_names(developer=str(self.alias.developer.igdb_id))
        self.assertEqual(names, ["Alpha Quest"])

    def test_filter_by_genres_any_option(self):
        self.game2.genres.add(self.genre_action)
        names = self._get_game_names(genres=str(self.genre_action.id), genre_option="A")
        self.assertCountEqual(names, ["Alpha Quest", "Beta Saga"])

    def test_order_by_parameter_applies(self):
        names = self._get_game_names(order_by="-year_of_release")
        self.assertEqual(names, ["Beta Saga", "Alpha Quest"])


class ApiSmokeTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.publication = models.Publication.objects.create(name="IGN")
        self.list = models.List.objects.create(
            publisher=self.publication,
            name="Top 10",
            year=2020,
            type="E",
        )
        self.developer = models.Developer.objects.create(name="Studio", slug="studio")
        self.post = models.Post.objects.create(title="News", text="Hello", active=True)
        models.Snippet.objects.create(slug="about", text="About text")
        models.Snippet.objects.create(slug="donate", text="Donate info")
        self.game = models.Game.objects.create(
            name="Alpha Quest",
            rank=1,
            igdb_id=1234,
            year_of_release=2000,
        )
        self.alias = models.DeveloperAlias.objects.create(
            developer=self.developer, name="Studio Alias", igdb_id=200
        )
        self.game.developers.add(self.alias)
        self.flatpage = FlatPage.objects.create(
            url="/faq/", title="FAQ", content="**Docs**"
        )

    def test_lists_endpoint(self):
        resp = self.client.get("/api/lists/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_developer_detail_endpoint(self):
        resp = self.client.get(f"/api/developers/{self.developer.slug}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Studio")

    def test_meta_endpoint(self):
        resp = self.client.get("/api/meta/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("games", resp.json())

    def test_posts_endpoint(self):
        resp = self.client.get("/api/posts/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["results"]), 1)

    def test_snippet_endpoint(self):
        resp = self.client.get("/api/snippets/about/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("snippet", resp.json())

    def test_page_endpoint_returns_404_for_missing(self):
        resp = self.client.get("/api/pages/missing/")
        self.assertEqual(resp.status_code, 404)

    def test_page_endpoint_returns_content(self):
        resp = self.client.get("/api/pages/faq/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "FAQ")

    def test_platforms_endpoint(self):
        resp = self.client.get("/api/platforms/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())

    def test_genres_endpoint(self):
        resp = self.client.get("/api/genres/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())

    def test_developer_alias_search_filters_results(self):
        resp = self.client.get("/api/developer-aliases/", {"q": "Studio"})
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_publication_detail_endpoint(self):
        resp = self.client.get(f"/api/publications/{self.publication.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "IGN")


class SerializerBehaviorTests(TestCase):

    def test_game_detail_serializer_lists_field(self):
        publication = models.Publication.objects.create(name="IGN")
        lst = models.List.objects.create(
            publisher=publication,
            name="Top 10",
            year=2020,
            type="E",
            order=1,
        )
        game = models.Game.objects.create(
            name="Sample", rank=1, igdb_id=1010, year_of_release=2020
        )
        models.ListMembership.objects.create(list=lst, game=game, rank=1)
        data = serializers.GameDetailSerializer(game).data
        self.assertEqual(len(data["lists"]), 1)
        self.assertEqual(data["lists"][0]["publication"], "IGN")

    def test_page_serializer_renders_markdown(self):
        page = FlatPage.objects.create(url="/terms/", title="Terms", content="**Hi**")
        serializer = serializers.PageSerializer(page)
        self.assertIn("<strong>Hi</strong>", serializer.data["content"])

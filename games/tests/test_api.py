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
        names = self._get_game_names(
            genres=str(self.genre_action.id), genre_option="any"
        )
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
        data = resp.json()

        # Check games data structure
        self.assertIn("games", data)
        self.assertIn("years", data["games"])
        self.assertIn("decades", data["games"])
        self.assertIn("last_update", data["games"])

        # Check lists data structure with total_count
        self.assertIn("lists", data)
        self.assertIn("years", data["lists"])
        self.assertIn("total_count", data["lists"])
        self.assertIsInstance(data["lists"]["total_count"], int)
        self.assertGreaterEqual(data["lists"]["total_count"], 1)

        # Check publications data structure with total_count
        self.assertIn("publications", data)
        self.assertIn("total_count", data["publications"])
        self.assertIsInstance(data["publications"]["total_count"], int)
        self.assertGreaterEqual(data["publications"]["total_count"], 1)

    def test_posts_endpoint(self):
        resp = self.client.get("/api/posts/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["results"]), 1)

    def test_posts_endpoint_with_author(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="newsauthor", first_name="Jane", last_name="Smith"
        )
        models.Post.objects.create(
            title="Authored News", text="Content", active=True, author=user
        )
        resp = self.client.get("/api/posts/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        authored_post = next(r for r in results if r["title"] == "Authored News")
        self.assertEqual(authored_post["author"], "Jane Smith")

    def test_posts_endpoint_without_author(self):
        resp = self.client.get("/api/posts/")
        results = resp.json()["results"]
        # The post created in setUp has no author
        unauth_post = next(r for r in results if r["title"] == "News")
        self.assertIsNone(unauth_post["author"])

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


class GameSearchAPIViewTests(TestCase):
    """Test the GameSearchAPIView (navbar search endpoint)."""

    def setUp(self):
        self.client = APIClient()

        # Create test games
        developer = models.Developer.objects.create(name="Test Dev", igdb_id=10)
        alias = models.DeveloperAlias.objects.create(
            developer=developer, name="Test Developer", igdb_id=11
        )

        self.game1 = models.Game.objects.create(
            name="The Legend of Zelda",
            rank=1,
            year_of_release=1986,
            slug="zelda",
        )
        self.game1.developers.add(alias)

        self.game2 = models.Game.objects.create(
            name="Zelda II: The Adventure of Link",
            rank=50,
            year_of_release=1987,
            slug="zelda-2",
        )
        self.game2.developers.add(alias)

        self.game3 = models.Game.objects.create(
            name="Super Mario Bros",
            rank=2,
            year_of_release=1985,
            slug="mario",
        )

    def test_search_with_valid_query(self):
        """Test searching with a valid query returns results."""
        response = self.client.get("/api/games/search/", {"q": "zelda"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["results"]), 2)

    def test_search_returns_correct_fields(self):
        """Test that search results contain expected fields."""
        response = self.client.get("/api/games/search/", {"q": "zelda"})
        data = response.json()
        result = data["results"][0]
        self.assertIn("id", result)
        self.assertIn("name", result)
        self.assertIn("slug", result)
        self.assertIn("year_of_release", result)
        self.assertIn("rank", result)
        self.assertIn("thumbnail", result)

    def test_search_with_short_query_returns_empty(self):
        """Test that queries less than 2 characters return empty results."""
        response = self.client.get("/api/games/search/", {"q": "z"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["results"]), 0)

    def test_search_without_query_returns_empty(self):
        """Test that no query parameter returns empty results."""
        response = self.client.get("/api/games/search/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_search_with_empty_query_returns_empty(self):
        """Test that empty query returns empty results."""
        response = self.client.get("/api/games/search/", {"q": ""})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_search_with_limit(self):
        """Test that limit parameter works."""
        response = self.client.get("/api/games/search/", {"q": "zelda", "limit": 1})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["results"]), 1)

    def test_search_orders_by_rank(self):
        """Test that search results are ordered by rank."""
        response = self.client.get("/api/games/search/", {"q": "zelda"})
        data = response.json()
        # Game1 has rank=1, Game2 has rank=50
        self.assertEqual(data["results"][0]["name"], "The Legend of Zelda")
        self.assertEqual(data["results"][1]["name"], "Zelda II: The Adventure of Link")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get("/api/games/search/", {"q": "ZELDA"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_search_partial_match(self):
        """Test that search matches partial names."""
        response = self.client.get("/api/games/search/", {"q": "mario"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Super Mario Bros")

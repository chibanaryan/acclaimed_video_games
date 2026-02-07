import importlib
from unittest import mock

from django.core.cache import cache
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

        self.developer = models.Developer.objects.create(
            name="Studio", slug="studio", igdb_id=10
        )

        self.game1 = models.Game.objects.create(
            name="Alpha Quest",
            rank=1,
            igdb_id=1001,
            year_of_release=2000,
            slug="alpha-quest",
        )
        self.game1.platforms.add(self.platform_pc)
        self.game1.developers.add(self.developer)
        self.genre = models.WikipediaGenre.objects.create(
            name="Test Genre", slug="test-genre", level=0
        )
        self.game1.wikipedia_genres.add(self.genre)

        self.game2 = models.Game.objects.create(
            name="Beta Saga",
            rank=2,
            igdb_id=1002,
            year_of_release=2010,
            slug="beta-saga",
        )
        self.game2.platforms.add(self.platform_ps)

    def _get_game_names(self, **params):
        response = self.client.get("/api/games/", params)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"] if "results" in data else data
        return [item["name"] for item in results]

    def test_filter_by_platform(self):
        names = self._get_game_names(platforms=str(self.platform_ps.id))
        self.assertEqual(names, ["Beta Saga"])

    def test_filter_by_developer(self):
        names = self._get_game_names(developer=str(self.developer.igdb_id))
        self.assertEqual(names, ["Alpha Quest"])

    def test_filter_by_genre(self):
        names = self._get_game_names(genres=str(self.genre.id))
        self.assertEqual(names, ["Alpha Quest"])

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
        self.developer = models.Developer.objects.create(
            name="Studio", slug="studio", igdb_id=200
        )
        self.post = models.Post.objects.create(title="News", text="Hello", active=True)
        models.Snippet.objects.create(slug="about", text="About text")
        models.Snippet.objects.create(slug="donate", text="Donate info")
        self.game = models.Game.objects.create(
            name="Alpha Quest",
            rank=1,
            igdb_id=1234,
            year_of_release=2000,
        )
        self.game.developers.add(self.developer)
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

        # Create test developer
        self.developer = models.Developer.objects.create(
            name="Test Developer", slug="test-dev", igdb_id=10
        )

        self.game1 = models.Game.objects.create(
            name="The Legend of Zelda",
            rank=1,
            year_of_release=1986,
            slug="zelda",
        )
        self.game1.developers.add(self.developer)

        self.game2 = models.Game.objects.create(
            name="Zelda II: The Adventure of Link",
            rank=50,
            year_of_release=1987,
            slug="zelda-2",
        )
        self.game2.developers.add(self.developer)

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

    def test_search_accent_insensitive(self):
        """Test that ASCII query finds accented game names via name_normalized."""
        game = models.Game.objects.create(
            name="Pokémon Red",
            rank=10,
            year_of_release=1996,
            slug="pokemon-red",
        )
        # Verify name_normalized was populated by save()
        game.refresh_from_db()
        self.assertEqual(game.name_normalized, "Pokemon Red")

        # ASCII query should find accented name
        response = self.client.get("/api/games/search/", {"q": "Pokemon"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "Pokémon Red")

        # Accented query should also work
        response = self.client.get("/api/games/search/", {"q": "Pokémon"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)


class UnifiedSearchViewTests(TestCase):
    """Test the UnifiedSearchView for unified navbar search."""

    def setUp(self):
        self.client = APIClient()

        # Create test developers (root developers with subsidiaries)
        self.nintendo = models.Developer.objects.create(
            name="Nintendo", slug="nintendo", igdb_id=10
        )
        self.nintendo_ead = models.Developer.objects.create(
            parent=self.nintendo, name="Nintendo EAD", igdb_id=11
        )

        self.capcom = models.Developer.objects.create(
            name="Capcom", slug="capcom", igdb_id=20
        )
        self.capcom_studio = models.Developer.objects.create(
            parent=self.capcom, name="Capcom Production Studio 4", igdb_id=21
        )

        # Independent developer with no parent (but also no slug, so no detail page)
        self.indie_dev = models.Developer.objects.create(
            name="Indie Dev Studio", igdb_id=30
        )

        # Create test games
        self.game1 = models.Game.objects.create(
            name="The Legend of Zelda",
            rank=1,
            year_of_release=1986,
            slug="zelda",
        )
        self.game1.developers.add(self.nintendo_ead)

        self.game2 = models.Game.objects.create(
            name="Super Mario Bros",
            rank=2,
            year_of_release=1985,
            slug="mario",
        )
        self.game2.developers.add(self.nintendo_ead)

        self.game3 = models.Game.objects.create(
            name="Street Fighter II",
            rank=5,
            year_of_release=1991,
            slug="sf2",
        )
        self.game3.developers.add(self.capcom_studio)

    def test_unified_search_returns_both_developers_and_games(self):
        """Test that unified search returns both developers and games."""
        response = self.client.get("/api/unified-search/", {"q": "nintendo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("developers", data)
        self.assertIn("games", data)

    def test_unified_search_developer_results_have_correct_fields(self):
        """Test that developer results contain expected fields."""
        response = self.client.get("/api/unified-search/", {"q": "nintendo"})
        data = response.json()
        self.assertGreater(len(data["developers"]), 0)
        dev = data["developers"][0]
        self.assertIn("id", dev)
        self.assertIn("name", dev)
        self.assertIn("root_slug", dev)
        self.assertIn("games_count", dev)

    def test_unified_search_game_results_have_correct_fields(self):
        """Test that game results contain expected fields."""
        response = self.client.get("/api/unified-search/", {"q": "zelda"})
        data = response.json()
        self.assertGreater(len(data["games"]), 0)
        game = data["games"][0]
        self.assertIn("id", game)
        self.assertIn("name", game)
        self.assertIn("slug", game)
        self.assertIn("year_of_release", game)
        self.assertIn("rank", game)
        self.assertIn("thumbnail", game)

    def test_unified_search_with_short_query_returns_empty(self):
        """Test that queries less than 2 characters return empty results."""
        response = self.client.get("/api/unified-search/", {"q": "n"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["developers"]), 0)
        self.assertEqual(len(data["games"]), 0)

    def test_unified_search_respects_limits(self):
        """Test that developer_limit and game_limit parameters work."""
        response = self.client.get(
            "/api/unified-search/",
            {"q": "nintendo", "developer_limit": 1, "game_limit": 1},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data["developers"]), 1)
        self.assertLessEqual(len(data["games"]), 1)

    def test_unified_search_excludes_independent_studios(self):
        """Test that studios without a parent company are not included."""
        # Search for indie studio by name - should not appear in results
        response = self.client.get("/api/unified-search/", {"q": "indie"})
        data = response.json()
        # The indie studio should not appear in developer results
        for dev in data["developers"]:
            self.assertNotEqual(dev["name"], "Indie Dev Studio")

    def test_unified_search_developers_ordered_by_games_count(self):
        """Test that developer results are ordered by games count descending."""
        # Nintendo EAD has 2 games, Capcom has 1 game
        response = self.client.get("/api/unified-search/", {"q": "studio"})
        data = response.json()
        if len(data["developers"]) > 1:
            # First developer should have more or equal games than second
            self.assertGreaterEqual(
                data["developers"][0]["games_count"],
                data["developers"][1]["games_count"],
            )

    def test_unified_search_games_ordered_by_rank(self):
        """Test that game results are ordered by rank."""
        response = self.client.get("/api/unified-search/", {"q": "the"})
        data = response.json()
        if len(data["games"]) > 1:
            # First game should have lower rank (better) than second
            self.assertLessEqual(data["games"][0]["rank"], data["games"][1]["rank"])

    def test_unified_search_accent_insensitive_games(self):
        """Test that ASCII query finds accented game names in unified search."""
        models.Game.objects.create(
            name="Pokémon Red",
            rank=10,
            year_of_release=1996,
            slug="pokemon-red",
        )
        response = self.client.get("/api/unified-search/", {"q": "Pokemon"})
        data = response.json()
        self.assertEqual(len(data["games"]), 1)
        self.assertEqual(data["games"][0]["name"], "Pokémon Red")


class GameDataVersionViewTests(TestCase):
    """Test the GameDataVersionView endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
            slug="test-game",
        )

    def test_version_endpoint_returns_version(self):
        """Test that version endpoint returns a version hash."""
        response = self.client.get("/api/games/version/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("version", data)
        self.assertIsInstance(data["version"], str)
        self.assertEqual(len(data["version"]), 12)  # MD5 hash truncated to 12 chars


class GameAllDataViewTests(TestCase):
    """Test the GameAllDataView endpoint for client-side filtering."""

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.platform = models.Platform.objects.create(code="PC", name="PC")
        self.root_dev = models.Developer.objects.create(
            name="Test Company", slug="test-company", igdb_id=100
        )
        self.developer = models.Developer.objects.create(
            parent=self.root_dev, name="Test Studio", igdb_id=101
        )
        self.genre = models.WikipediaGenre.objects.create(
            name="Test Action", slug="test-action-unique", level=0
        )
        self.child_genre = models.WikipediaGenre.objects.create(
            name="Test Shooter", slug="test-shooter-unique", parent=self.genre, level=1
        )
        self.game = models.Game.objects.create(
            name="Test Game",
            rank=1,
            year_of_release=2020,
            slug="test-game",
            igdb_id=1234,
        )
        self.game.platforms.add(self.platform)
        self.game.developers.add(self.developer)
        self.game.wikipedia_genres.add(self.genre)
        self.series = models.Series.objects.create(
            name="Test Series", slug="test-series", igdb_id=999
        )
        self.game.series.add(self.series)
        self.igdb_data = models.IGDBGameData.objects.create(
            game=self.game,
            igdb_id=1234,
            artwork_id="co1234",
            url="https://igdb.com/game/1234",
            is_primary=True,
        )
        self.game.primary_igdb_game_data = self.igdb_data
        self.hltb_data = models.HLTBGameData.objects.create(
            game=self.game,
            igdb_id=1234,
            hltb_id="hltb123",
            main_story_hours=10.5,
            completionist_hours=25.0,
            is_primary=True,
        )
        self.game.primary_hltb_game_data = self.hltb_data
        self.game.save()

    def test_all_data_endpoint_returns_correct_structure(self):
        """Test that all data endpoint returns correct structure."""
        response = self.client.get("/api/games/all/")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check top-level structure
        self.assertIn("version", data)
        self.assertIn("data", data)

        # Check data structure
        game_data = data["data"]
        self.assertIn("games", game_data)
        self.assertIn("developers", game_data)
        self.assertIn("platforms", game_data)
        self.assertIn("genres", game_data)

    def test_all_data_games_have_correct_fields(self):
        """Test that games have correct compressed field names."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        games = data["data"]["games"]

        self.assertEqual(len(games), 1)
        game = games[0]

        # Check compressed field names
        self.assertIn("id", game)
        self.assertIn("n", game)  # name
        self.assertIn("s", game)  # slug
        self.assertIn("r", game)  # rank
        self.assertIn("y", game)  # year
        self.assertIn("a", game)  # artwork_id
        self.assertIn("dv", game)  # developer IDs
        self.assertIn("p", game)  # platform IDs
        self.assertIn("g", game)  # genre IDs
        self.assertIn("sr", game)  # series IDs
        self.assertIn("pt", game)  # main story playtime
        self.assertIn("ptc", game)  # completionist playtime

        # Check values
        self.assertEqual(game["n"], "Test Game")
        self.assertEqual(game["r"], 1)
        self.assertEqual(game["y"], 2020)
        self.assertEqual(game["a"], "co1234")
        self.assertIn(self.developer.id, game["dv"])
        self.assertIn(self.platform.id, game["p"])
        self.assertIn(self.genre.id, game["g"])
        self.assertIn(self.series.id, game["sr"])
        self.assertEqual(game["pt"], 10.5)
        self.assertEqual(game["ptc"], 25.0)

    def test_all_data_developers_reference_data(self):
        """Test that developers reference data is correct."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        developers = data["data"]["developers"]

        # Note: JSON keys are strings, but Python dict may use integers
        # Check that the subsidiary developer is in the developers dict
        dev_id_key = self.developer.id
        if str(dev_id_key) in developers:
            dev_id_key = str(dev_id_key)
        self.assertIn(dev_id_key, developers)
        dev_data = developers[dev_id_key]
        self.assertEqual(dev_data["n"], "Test Studio")
        self.assertEqual(dev_data["pa"], self.root_dev.id)  # parent ID

        # Check that the root developer is also included
        root_id_key = self.root_dev.id
        if str(root_id_key) in developers:
            root_id_key = str(root_id_key)
        self.assertIn(root_id_key, developers)
        root_data = developers[root_id_key]
        self.assertEqual(root_data["n"], "Test Company")
        self.assertEqual(root_data["s"], "test-company")

    def test_all_data_genres_have_hierarchy(self):
        """Test that genres include hierarchy information."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        genres = data["data"]["genres"]

        # Find parent genre
        parent_genre = next((g for g in genres if g["id"] == self.genre.id), None)
        self.assertIsNotNone(parent_genre)
        self.assertEqual(parent_genre["n"], "Test Action")
        self.assertEqual(parent_genre["l"], 0)  # level
        self.assertIsNone(parent_genre["p"])  # parent_id
        self.assertIn(self.child_genre.id, parent_genre["d"])  # descendants

        # Find child genre
        child_genre = next((g for g in genres if g["id"] == self.child_genre.id), None)
        self.assertIsNotNone(child_genre)
        self.assertEqual(child_genre["n"], "Test Shooter")
        self.assertEqual(child_genre["l"], 1)  # level
        self.assertEqual(child_genre["p"], self.genre.id)  # parent_id

    def test_all_data_series_reference_data(self):
        """Test that series reference data is included."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        series_data = data["data"]["series"]

        series_key = str(self.series.id)
        self.assertIn(series_key, series_data)
        self.assertEqual(series_data[series_key]["n"], "Test Series")
        self.assertEqual(series_data[series_key]["s"], "test-series")

    def test_all_data_platforms_reference_data(self):
        """Test that platforms reference data is correct."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        platforms = data["data"]["platforms"]

        self.assertIn(str(self.platform.id), platforms)
        platform_data = platforms[str(self.platform.id)]
        self.assertEqual(platform_data["n"], "PC")
        self.assertEqual(platform_data["c"], "PC")

    def test_all_data_games_have_series_field(self):
        """Test that all games have series IDs field in response."""
        response = self.client.get("/api/games/all/")
        data = response.json()
        games = data["data"]["games"]

        game = games[0]
        # Check series IDs field is present (even if empty)
        self.assertIn("sr", game)
        # With series in setup, should include series id
        self.assertIn(self.series.id, game["sr"])

    def test_all_data_games_without_optional_data(self):
        """Test that games without optional data return None for those fields."""
        # Clear optional data from the existing game in setup
        self.game.series.clear()
        models.Game.objects.filter(id=self.game.id).update(
            primary_igdb_game_data_id=None,
            primary_hltb_game_data_id=None,
        )
        self.game.refresh_from_db()
        response = self.client.get("/api/games/all/")
        data = response.json()
        games_list = data["data"]["games"]
        game = next((g for g in games_list if g["n"] == "Test Game"), None)
        self.assertIsNotNone(game)

        # When no IGDB data attached, artwork should be None
        self.assertIsNone(game["a"])
        # When no HLTB data attached, playtime should be None
        self.assertIsNone(game["pt"])
        self.assertIsNone(game["ptc"])


class IdNameSerializerTests(TestCase):
    """Tests for IdNameSerializer get_id method."""

    def test_get_id_with_igdb_id(self):
        """Test that get_id returns igdb_id when available."""
        developer = models.Developer.objects.create(
            name="Test Dev", slug="test-dev", igdb_id=12345
        )
        serializer = serializers.IdNameSerializer(developer)
        self.assertEqual(serializer.data["id"], 12345)

    def test_get_id_falls_back_to_id(self):
        """Test that get_id falls back to regular id when no igdb_id."""
        # WikipediaGenre has id but no igdb_id attribute
        genre = models.WikipediaGenre.objects.create(name="Test Genre")
        serializer = serializers.IdNameSerializer(genre)
        self.assertEqual(serializer.data["id"], genre.id)


class GameSummarySerializerTests(TestCase):
    """Tests for GameSummarySerializer methods."""

    def test_get_igdb_artwork_id_with_primary_data(self):
        """Test that artwork_id is returned from primary_igdb_game_data."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=1001, slug="test-game-sm1"
        )
        igdb_data = models.IGDBGameData.objects.create(
            game=game, igdb_id=1001, artwork_id="cover123", is_primary=True
        )
        game.primary_igdb_game_data = igdb_data
        game.save()

        serializer = serializers.GameSummarySerializer(game)
        self.assertEqual(serializer.data["igdb_artwork_id"], "cover123")

    def test_get_igdb_artwork_id_returns_none_without_primary_data(self):
        """Test that artwork_id returns None when no primary_igdb_game_data."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=1002, slug="test-game-sm2"
        )
        serializer = serializers.GameSummarySerializer(game)
        self.assertIsNone(serializer.data["igdb_artwork_id"])

    def test_get_igdb_url_with_primary_data(self):
        """Test that URL is returned from primary_igdb_game_data."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=1003, slug="test-game-sm3"
        )
        igdb_data = models.IGDBGameData.objects.create(
            game=game,
            igdb_id=1003,
            url="https://igdb.com/games/test",
            is_primary=True,
        )
        game.primary_igdb_game_data = igdb_data
        game.save()

        serializer = serializers.GameSummarySerializer(game)
        self.assertEqual(serializer.data["igdb_url"], "https://igdb.com/games/test")

    def test_get_igdb_url_returns_none_without_primary_data(self):
        """Test that URL returns None when no primary_igdb_game_data."""
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=1004, slug="test-game-sm4"
        )
        serializer = serializers.GameSummarySerializer(game)
        self.assertIsNone(serializer.data["igdb_url"])


class DeveloperSerializerTests(TestCase):
    """Tests for DeveloperSerializer get_games_count method."""

    def test_get_games_count_with_annotated_count(self):
        """Test that annotated games_count is used when available."""
        from django.db.models import Count

        developer = models.Developer.objects.create(
            name="Test Dev", slug="test-dev-ds", igdb_id=100
        )
        game = models.Game.objects.create(
            name="Test Game", rank=1, igdb_id=2001, slug="test-game-ds"
        )
        game.developers.add(developer)

        # Annotate the queryset
        developer_annotated = models.Developer.objects.annotate(
            games_count=Count("developed_games")
        ).get(pk=developer.pk)

        serializer = serializers.DeveloperSerializer(developer_annotated)
        self.assertEqual(serializer.data["games_count"], 1)

    def test_get_games_count_fallback_to_computed(self):
        """Test that games_count is computed when not annotated."""
        developer = models.Developer.objects.create(
            name="Test Dev 2", slug="test-dev-ds2", igdb_id=101
        )
        game = models.Game.objects.create(
            name="Test Game 2", rank=1, igdb_id=2002, slug="test-game-ds2"
        )
        game.developers.add(developer)

        # Get developer without annotation
        serializer = serializers.DeveloperSerializer(developer)
        self.assertEqual(serializer.data["games_count"], 1)


class PostSerializerTests(TestCase):
    """Tests for PostSerializer get_author method."""

    def test_get_author_with_full_name(self):
        """Test that author's full name is returned when available."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="testuser-ps", first_name="John", last_name="Doe"
        )
        post = models.Post.objects.create(
            title="Test Post", text="Content", author=user, active=True
        )
        serializer = serializers.PostSerializer(post)
        self.assertEqual(serializer.data["author"], "John Doe")

    def test_get_author_fallback_to_username(self):
        """Test that author's username is used when full name is empty."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="testuser2-ps")
        post = models.Post.objects.create(
            title="Test Post 2", text="Content", author=user, active=True
        )
        serializer = serializers.PostSerializer(post)
        self.assertEqual(serializer.data["author"], "testuser2-ps")

    def test_get_author_returns_none_when_no_author(self):
        """Test that None is returned when post has no author."""
        post = models.Post.objects.create(
            title="Test Post 3", text="Content", active=True
        )
        serializer = serializers.PostSerializer(post)
        self.assertIsNone(serializer.data["author"])


class WikipediaGenreTreeSerializerTests(TestCase):
    """Tests for WikipediaGenreTreeSerializer methods."""

    def test_get_children_returns_nested_children(self):
        """Test that children are serialized recursively."""
        parent = models.WikipediaGenre.objects.create(
            name="Action Ser", slug="action-ser", level=0, display_order=1
        )
        models.WikipediaGenre.objects.create(
            name="Shooter Ser",
            slug="shooter-ser",
            parent=parent,
            level=1,
            display_order=1,
        )
        models.WikipediaGenre.objects.create(
            name="Platformer Ser",
            slug="platformer-ser",
            parent=parent,
            level=1,
            display_order=2,
        )

        serializer = serializers.WikipediaGenreTreeSerializer(parent)
        data = serializer.data

        self.assertEqual(len(data["children"]), 2)
        self.assertEqual(data["children"][0]["name"], "Shooter Ser")
        self.assertEqual(data["children"][1]["name"], "Platformer Ser")

    def test_get_game_count_with_annotated_count(self):
        """Test that annotated game count is used when available."""
        from django.db.models import Count

        genre = models.WikipediaGenre.objects.create(
            name="RPG Ser", slug="rpg-ser", level=0
        )
        game = models.Game.objects.create(
            name="RPG Game", rank=1, igdb_id=3001, slug="rpg-game-ser"
        )
        game.wikipedia_genres.add(genre)

        # Annotate the queryset
        genre_annotated = models.WikipediaGenre.objects.annotate(
            game_count_annotated=Count("games_with_wikipedia_genre")
        ).get(pk=genre.pk)

        serializer = serializers.WikipediaGenreTreeSerializer(genre_annotated)
        self.assertEqual(serializer.data["game_count"], 1)

    def test_get_game_count_fallback_to_computed(self):
        """Test that game count is computed when not annotated."""
        genre = models.WikipediaGenre.objects.create(
            name="Strategy Ser", slug="strategy-ser", level=0
        )
        game = models.Game.objects.create(
            name="Strategy Game", rank=1, igdb_id=3002, slug="strategy-game-ser"
        )
        game.wikipedia_genres.add(genre)

        serializer = serializers.WikipediaGenreTreeSerializer(genre)
        self.assertEqual(serializer.data["game_count"], 1)


class DeveloperSearchSerializerTests(TestCase):
    """Tests for DeveloperSearchSerializer get_root_slug method."""

    def test_get_root_slug_with_root_developer(self):
        """Test that root_slug is returned for developer with root_developer."""
        from django.db.models import Count

        root = models.Developer.objects.create(
            name="Nintendo SS", slug="nintendo-ss", igdb_id=500
        )
        subsidiary = models.Developer.objects.create(
            parent=root, name="Nintendo EAD SS", igdb_id=501
        )

        # Annotate with games_count for the serializer
        subsidiary_annotated = models.Developer.objects.annotate(
            games_count=Count("developed_games")
        ).get(pk=subsidiary.pk)

        serializer = serializers.DeveloperSearchSerializer(subsidiary_annotated)
        self.assertEqual(serializer.data["root_slug"], "nintendo-ss")

    def test_get_root_slug_fallback_to_own_slug(self):
        """Test that own slug is used when no root_developer."""
        from django.db.models import Count

        # Root developer (parent=None, so root_developer is self)
        root = models.Developer.objects.create(
            name="Valve SS", slug="valve-ss", igdb_id=600
        )

        root_annotated = models.Developer.objects.annotate(
            games_count=Count("developed_games")
        ).get(pk=root.pk)

        serializer = serializers.DeveloperSearchSerializer(root_annotated)
        self.assertEqual(serializer.data["root_slug"], "valve-ss")


class WikipediaGenreTreeViewTests(TestCase):
    """Tests for WikipediaGenreTreeView endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.parent = models.WikipediaGenre.objects.create(
            name="Action Tree", slug="action-tree", level=0, display_order=1
        )
        models.WikipediaGenre.objects.create(
            name="Shooter Tree",
            slug="shooter-tree",
            parent=self.parent,
            level=1,
            display_order=1,
        )

    def test_genre_tree_endpoint_returns_roots(self):
        response = self.client.get("/api/genres/tree/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        items = data.get("results", data)
        action_root = next(
            (item for item in items if item["name"] == "Action Tree"), None
        )
        self.assertIsNotNone(action_root)


class PostgresSearchFieldTests(TestCase):
    """Tests for PostgreSQL-specific search fields."""

    def test_postgres_search_fields_added(self):
        import games.api.views as views

        with mock.patch("django.db.connection.vendor", "postgresql"):
            importlib.reload(views)
            self.assertIn("name__search", views.GameListView.search_fields)
            self.assertIn("name__search", views.DeveloperListAPIView.search_fields)

        importlib.reload(views)

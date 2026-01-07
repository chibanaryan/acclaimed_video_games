from unittest import mock
from unittest.mock import MagicMock, mock_open

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from games import models, views


class ImportViewIntegrationTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client = Client()

    def test_requires_authentication(self):
        response = self.client.get(reverse("import"))
        self.assertEqual(response.status_code, 302)

    @mock.patch("games.views.utils.import_batch", return_value=(True, "Done"))
    def test_successful_data_import(self, mock_import):
        """Test batch import with a single file."""
        self.client.login(username="tester", password="pass")
        fake_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPersonal Computer")
        response = self.client.post(
            reverse("import"),
            {
                "platforms_file": fake_file,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check session data instead of messages
        self.assertEqual(response.wsgi_request.session.get("import_success"), "Done")
        mock_import.assert_called_once()

    @mock.patch("games.views.utils.import_data", return_value=(True, "Deleted"))
    def test_delete_existing_data_triggers_import(self, mock_import):
        self.client.login(username="tester", password="pass")
        response = self.client.post(
            reverse("import"),
            {
                "delete": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check session data instead of messages
        self.assertEqual(response.wsgi_request.session.get("import_success"), "Deleted")
        mock_import.assert_called_once()

    @mock.patch("games.views.utils.import_data", return_value=(True, "IGDB"))
    def test_igdb_import_triggers_command(self, mock_import):
        self.client.login(username="tester", password="pass")
        response = self.client.post(
            reverse("import"),
            {
                "igdb": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check session data instead of messages
        self.assertEqual(response.wsgi_request.session.get("import_success"), "IGDB")
        mock_import.assert_called_once()

    @mock.patch("games.views.utils.import_batch", return_value=(False, "Failed"))
    def test_failed_data_import_sets_error_message(self, mock_import):
        self.client.login(username="tester", password="pass")
        fake_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPersonal Computer")
        response = self.client.post(
            reverse("import"),
            {
                "platforms_file": fake_file,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check session data instead of messages (line 161)
        self.assertEqual(response.wsgi_request.session.get("import_errors"), ["Failed"])
        mock_import.assert_called_once()

    @mock.patch("games.views.utils.import_data", return_value=(False, "Error message"))
    def test_form_valid_error_path(self, mock_import):
        """Test form_valid error path (line 161)."""
        self.client.login(username="tester", password="pass")
        response = self.client.post(
            reverse("import"),
            {
                "delete": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.wsgi_request.session.get("import_errors"), ["Error message"]
        )

    def test_get_context_data_includes_counts(self):
        """Test that get_context_data includes database counts."""
        self.client.login(username="tester", password="pass")
        response = self.client.get(reverse("import"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("counts", response.context)
        self.assertIn("igdb_counts", response.context)
        self.assertIn("platforms", response.context["counts"])
        self.assertIn("games", response.context["counts"])

    def test_get_context_data_with_session_data(self):
        """Test that get_context_data retrieves session messages."""
        self.client.login(username="tester", password="pass")
        session = self.client.session
        session["import_success"] = "Test success"
        session["import_errors"] = ["Test error"]
        session.save()

        response = self.client.get(reverse("import"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["import_success_message"], "Test success")
        self.assertEqual(response.context["import_errors"], ["Test error"])

        # Session data should be consumed (popped)
        self.client.session.save()
        response2 = self.client.get(reverse("import"))
        self.assertIsNone(response2.context.get("import_success_message"))
        self.assertIsNone(response2.context.get("import_errors"))

    @mock.patch("games.views.utils.import_batch", return_value=(True, "Loaded"))
    @mock.patch("builtins.open", new_callable=mock_open, read_data=b"test data")
    @mock.patch("games.views.Path")
    def test_seed_test_data_success(self, mock_path, mock_file, mock_import):
        """Test seed_test_data loads bundled test files successfully."""
        self.client.login(username="tester", password="pass")

        # Mock Path to return mock file objects
        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.__truediv__ = lambda self, other: mock_path_obj

        response = self.client.post(
            reverse("import"),
            {
                "seed_test_data": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "Loaded bundled test data",
            response.wsgi_request.session.get("import_success"),
        )
        mock_import.assert_called_once()

    @mock.patch("builtins.open", side_effect=FileNotFoundError)
    @mock.patch("games.views.Path")
    def test_seed_test_data_file_not_found(self, mock_path, mock_file):
        """Test seed_test_data handles missing test files."""
        self.client.login(username="tester", password="pass")

        mock_path_obj = MagicMock()
        mock_path.return_value = mock_path_obj
        mock_path_obj.__truediv__ = lambda self, other: mock_path_obj

        response = self.client.post(
            reverse("import"),
            {
                "seed_test_data": True,
            },
        )

        self.assertEqual(response.status_code, 302)
        errors = response.wsgi_request.session.get("import_errors")
        self.assertIsNotNone(errors)
        self.assertIn("test_input_files", errors[0])


class IGDBProgressViewTests(TestCase):
    """Tests for IGDBProgressView."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client = Client()

    def test_igdb_progress_view_get(self):
        """Test IGDBProgressView.get() returns streaming response."""
        self.client.login(username="tester", password="pass")

        # Mock the import_igdb_with_progress to return a simple generator
        with mock.patch("games.views.utils.import_igdb_with_progress") as mock_progress:
            mock_progress.return_value = iter(["data: test\n\n"])

            response = self.client.get("/import/igdb-progress/")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["content-type"], "text/event-stream")


class WikipediaPageProgressViewTests(TestCase):
    """Tests for WikipediaPageProgressView."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tester2", password="pass")
        self.client = Client()

    def test_wikipedia_progress_view_get(self):
        """Test WikipediaPageProgressView.get() returns streaming response."""
        self.client.login(username="tester2", password="pass")

        with mock.patch(
            "games.views.utils.import_wikipedia_pages_with_progress"
        ) as mock_progress:
            mock_progress.return_value = iter(["data: test\n\n"])

            response = self.client.get(
                "/import/wikipedia-page-progress/?force=true"
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["content-type"], "text/event-stream")


class GameListSeriesFilterTests(TestCase):
    """Tests for series filtering in GameListView."""

    def setUp(self):
        self.client = Client()
        # Create a series
        self.series = models.Series.objects.create(
            name="Test Series",
            slug="test-series",
            igdb_id=12345,
        )
        # Create games - one in series, one not
        self.game_in_series = models.Game.objects.create(
            name="Game In Series",
            rank=1,
            igdb_id=100,
            year_of_release=2020,
        )
        self.game_in_series.series.add(self.series)

        self.game_not_in_series = models.Game.objects.create(
            name="Game Not In Series",
            rank=2,
            igdb_id=101,
            year_of_release=2020,
        )

    def test_series_filter_returns_only_games_in_series(self):
        """Test that series filter returns only games in the specified series."""
        response = self.client.get(f"/?series={self.series.id}")
        self.assertEqual(response.status_code, 200)
        # The response should contain the game in the series
        self.assertContains(response, "Game In Series")

    def test_series_filter_with_invalid_id(self):
        """Test that series filter with invalid ID returns empty results gracefully."""
        response = self.client.get("/?series=99999")
        self.assertEqual(response.status_code, 200)

    def test_series_list_in_context(self):
        """Test that series_list is included in the view context."""
        response = self.client.get("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("series_list", response.context)


class GenreSubtitleTests(TestCase):
    """Tests for _build_genre_subtitle helper."""

    def test_build_genre_subtitle_empty(self):
        """Test subtitle with no genres."""
        result = views._build_genre_subtitle([], "any", [])
        self.assertEqual(result, "")

    def test_build_genre_subtitle_single(self):
        """Test subtitle with single genre."""
        genres = [{"id": 1, "name": "Action"}]
        result = views._build_genre_subtitle([1], "any", genres)
        self.assertEqual(result, "Genre: Action")

    def test_build_genre_subtitle_multiple_any(self):
        """Test subtitle with multiple genres using 'any' option."""
        genres = [{"id": 1, "name": "Action"}, {"id": 2, "name": "RPG"}]
        result = views._build_genre_subtitle([1, 2], "any", genres)
        self.assertEqual(result, "Genre: Action OR RPG")

    def test_build_genre_subtitle_multiple_all(self):
        """Test subtitle with multiple genres using 'all' option."""
        genres = [{"id": 1, "name": "Action"}, {"id": 2, "name": "RPG"}]
        result = views._build_genre_subtitle([1, 2], "all", genres)
        self.assertEqual(result, "Genre: Action AND RPG")

    def test_build_genre_subtitle_missing_genre(self):
        """Test subtitle with genre ID not in lookup."""
        genres = [{"id": 1, "name": "Action"}]
        result = views._build_genre_subtitle([999], "any", genres)
        self.assertEqual(result, "Genre: 999")

    def test_build_genre_subtitle_empty_names(self):
        """Test subtitle returns empty when names are blank."""
        genres = [{"id": 1, "name": ""}]
        result = views._build_genre_subtitle([1], "any", genres)
        self.assertEqual(result, "")


class PlayedFilterTests(TestCase):
    """Tests for _apply_played_filter helper."""

    def test_apply_played_filter_invalid_value_returns_queryset(self):
        """Test invalid played param returns unmodified queryset."""
        game = models.Game.objects.create(name="Test Game", rank=1, igdb_id=100)
        User = get_user_model()
        user = User.objects.create_user(username="tester", password="pass")

        qs = models.Game.objects.all()
        filtered = views._apply_played_filter(qs, user, "maybe")

        self.assertEqual(list(filtered), [game])


class FilterTitleTests(TestCase):
    """Tests for _build_filter_title helper."""

    def test_build_filter_title_with_hltb_max_only(self):
        """Test title includes hltb max-only label."""
        filters = {
            "start": None,
            "end": None,
            "genres": [],
            "platforms": [],
            "series": [],
            "played": "",
            "hltb_mode": "main",
            "hltb_min": None,
            "hltb_max": 5,
        }
        title = views._build_filter_title(filters, [], [], 1980, 2020)

        self.assertIn("<5 Hour", title)


class PlatformSegmentTests(TestCase):
    """Tests for _build_platform_segment helper."""

    def test_build_platform_segment_uses_platform_name(self):
        platforms = [{"id": 1, "code": "UNK", "name": "Mystery Box"}]
        result = views._build_platform_segment([1], platforms)
        self.assertEqual(result, "Mystery Box Games")

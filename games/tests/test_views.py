from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, mock_open

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase
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

    @mock.patch("games.views.utils.import_batch", return_value=(True, "Done", False))
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

    @mock.patch("games.views.utils.import_batch", return_value=(False, "Failed", False))
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

    @mock.patch("games.views.utils.import_batch", return_value=(True, "Done", True))
    def test_successful_import_with_igdb_trigger(self, mock_import):
        """Test that successful import with IGDB checkbox sets trigger flag."""
        self.client.login(username="tester", password="pass")
        fake_file = SimpleUploadedFile("PlatformDB.txt", b"PC\tPersonal Computer")
        response = self.client.post(
            reverse("import"),
            {
                "platforms_file": fake_file,
                "igdb": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.wsgi_request.session.get("import_success"), "Done")
        self.assertTrue(response.wsgi_request.session.get("trigger_igdb"))
        mock_import.assert_called_once()

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
        session["trigger_igdb"] = True
        session.save()

        response = self.client.get(reverse("import"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["import_success_message"], "Test success")
        self.assertEqual(response.context["import_errors"], ["Test error"])
        self.assertTrue(response.context["trigger_igdb"])

        # Session data should be consumed (popped)
        self.client.session.save()
        response2 = self.client.get(reverse("import"))
        self.assertIsNone(response2.context.get("import_success_message"))
        self.assertIsNone(response2.context.get("import_errors"))
        self.assertFalse(response2.context.get("trigger_igdb", False))

    @mock.patch("games.views.utils.import_batch", return_value=(True, "Loaded", False))
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


class SPAWithPrerenderedViewTests(TestCase):
    """Tests for SPAWithPrerenderedView that serves pre-rendered HTML files."""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = views.SPAWithPrerenderedView()

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_root_path_serves_index_html(self, mock_path_class, mock_settings):
        """Test that root path serves index.html."""
        request = self.factory.get("/")

        # Setup mocks
        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True
        mock_index_file.__truediv__.return_value = mock_index_file
        mock_dist_path.__truediv__.return_value = mock_index_file
        mock_path_class.return_value = mock_dist_path

        with patch("builtins.open", mock_open(read_data="<html>index</html>")):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>index</html>")
        self.assertEqual(response["content-type"], "text/html")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_empty_path_serves_index_html(self, mock_path_class, mock_settings):
        """Test that empty path serves index.html."""
        request = self.factory.get("")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True
        mock_index_file.__truediv__.return_value = mock_index_file
        mock_dist_path.__truediv__.return_value = mock_index_file
        mock_path_class.return_value = mock_dist_path

        with patch("builtins.open", mock_open(read_data="<html>index</html>")):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>index</html>")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_path_with_directory_index_serves_file(
        self, mock_path_class, mock_settings
    ):
        """Test that /games/ serves frontend/dist/games/index.html."""
        request = self.factory.get("/games/")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_games_dir = MagicMock(spec=Path, unsafe=True)
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True
        mock_games_dir.__truediv__.return_value = mock_index_file
        mock_dist_path.__truediv__.return_value = mock_games_dir
        mock_path_class.return_value = mock_dist_path

        with patch("builtins.open", mock_open(read_data="<html>games page</html>")):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>games page</html>")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_path_with_html_file_serves_file(self, mock_path_class, mock_settings):
        """Test that /about serves frontend/dist/about.html."""
        request = self.factory.get("/about")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_about_dir = MagicMock(spec=Path, unsafe=True)
        mock_about_dir.exists.return_value = False  # /about/index.html doesn't exist
        mock_about_html = MagicMock(spec=Path, unsafe=True)
        mock_about_html.exists.return_value = True  # /about.html exists
        mock_dist_path.__truediv__.side_effect = lambda x: (
            mock_about_dir if x == "about" else mock_about_html
        )
        mock_about_dir.__truediv__.return_value = mock_about_dir
        mock_path_class.return_value = mock_dist_path

        with patch("builtins.open", mock_open(read_data="<html>about page</html>")):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>about page</html>")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_missing_path_falls_back_to_index_html(
        self, mock_path_class, mock_settings
    ):
        """Test that missing path falls back to index.html."""
        request = self.factory.get("/nonexistent")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_nonexistent_dir = MagicMock(spec=Path, unsafe=True)
        mock_nonexistent_dir.exists.return_value = False
        mock_nonexistent_html = MagicMock(spec=Path, unsafe=True)
        mock_nonexistent_html.exists.return_value = False
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True
        mock_dist_path.__truediv__.side_effect = lambda x: (
            mock_nonexistent_dir
            if x == "nonexistent"
            else (
                mock_nonexistent_html
                if "nonexistent.html" in str(x)
                else mock_index_file
            )
        )
        mock_nonexistent_dir.__truediv__.return_value = mock_nonexistent_dir
        mock_path_class.return_value = mock_dist_path

        with patch("builtins.open", mock_open(read_data="<html>fallback</html>")):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>fallback</html>")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_missing_path_and_index_returns_404(self, mock_path_class, mock_settings):
        """Test that missing path and index.html returns 404."""
        request = self.factory.get("/nonexistent")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_file = MagicMock(spec=Path, unsafe=True)
        mock_file.exists.return_value = False
        mock_dist_path.__truediv__.return_value = mock_file
        mock_file.__truediv__.return_value = mock_file
        mock_path_class.return_value = mock_dist_path

        response = self.view.get(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content.decode(), "Not found")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_ioerror_reading_file_falls_back(self, mock_path_class, mock_settings):
        """Test that IOError when reading file falls back to index.html."""
        request = self.factory.get("/games/")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_games_dir = MagicMock(spec=Path, unsafe=True)
        mock_games_index = MagicMock(spec=Path, unsafe=True)
        mock_games_index.exists.return_value = True
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True
        mock_games_dir.__truediv__.return_value = mock_games_index
        mock_dist_path.__truediv__.side_effect = lambda x: (
            mock_games_dir if x == "games" else mock_index_file
        )
        mock_path_class.return_value = mock_dist_path

        # First open raises IOError, second succeeds
        call_count = [0]

        def open_side_effect(path, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise IOError("Permission denied")
            return mock_open(read_data="<html>fallback</html>")(path, *args, **kwargs)

        with patch("builtins.open", side_effect=open_side_effect):
            response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "<html>fallback</html>")

    @patch("games.views.settings")
    @patch("games.views.Path")
    def test_ioerror_on_fallback_returns_404(self, mock_path_class, mock_settings):
        """Test IOError when reading fallback file returns 404 (lines 56-57)."""
        request = self.factory.get("/test")

        mock_settings.BASE_DIR = Path("/tmp/test")
        mock_dist_path = MagicMock(spec=Path, unsafe=True)
        mock_file = MagicMock(spec=Path, unsafe=True)
        mock_file.exists.return_value = False  # Test file doesn't exist
        mock_index_file = MagicMock(spec=Path, unsafe=True)
        mock_index_file.exists.return_value = True  # Fallback exists
        mock_dist_path.__truediv__.side_effect = lambda x: (
            mock_file if x == "test" else mock_index_file
        )
        mock_file.__truediv__.return_value = mock_file
        mock_path_class.return_value = mock_dist_path

        # Fallback open raises IOError - exception handler catches it (lines 56-57)
        def open_side_effect(path, *args, **kwargs):
            raise IOError("Permission denied")

        with patch("builtins.open", side_effect=open_side_effect):
            # Should handle IOError gracefully and return 404
            response = self.view.get(request)
            self.assertEqual(response.status_code, 404)


class PostListViewTests(TestCase):
    """Tests for PostListView."""

    def setUp(self):
        self.client = Client()
        # Create some posts for testing
        models.Post.objects.create(title="Post 1", text="Content 1", active=True)
        models.Post.objects.create(title="Post 2", text="Content 2", active=True)
        models.Post.objects.create(title="Post 3", text="Content 3", active=True)
        models.Post.objects.create(title="Post 4", text="Content 4", active=True)
        models.Post.objects.create(title="Post 5", text="Content 5", active=True)
        models.Post.objects.create(title="Post 6", text="Content 6", active=True)

    def test_post_list_view_returns_posts(self):
        """Test that PostListView returns posts."""
        # Note: PostListView is in games.views, but the URL might be in beta
        # Let's test the view directly
        factory = RequestFactory()
        request = factory.get("/posts/")
        view = views.PostListView()
        view.request = request

        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 6)

    def test_post_list_view_pagination(self):
        """Test that PostListView paginates correctly."""
        factory = RequestFactory()
        request = factory.get("/posts/")
        view = views.PostListView()
        view.request = request

        # PostListView has paginate_by = 5
        queryset = view.get_queryset()
        paginator = view.get_paginator(queryset, view.paginate_by)
        page = paginator.page(1)

        self.assertEqual(len(page.object_list), 5)
        self.assertTrue(page.has_other_pages())

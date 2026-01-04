"""Tests for PlayedGame, WantToPlayGame models and related functionality."""

from django.db import IntegrityError
from django.test import TestCase

from games.models import Game, PlayedGame, WantToPlayGame, User


class PlayedGameModelTests(TestCase):
    """Test cases for PlayedGame model."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game1 = Game.objects.create(
            name="Test Game 1",
            rank=1,
            igdb_id=12345,
        )
        cls.game2 = Game.objects.create(
            name="Test Game 2",
            rank=2,
            igdb_id=67890,
        )

    def test_create_played_game(self):
        """Test creating a PlayedGame record."""
        played = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        self.assertEqual(played.user, self.user)
        self.assertEqual(played.game, self.game1)
        self.assertEqual(played.igdb_id, 12345)
        self.assertIsNotNone(played.created)

    def test_str_with_game(self):
        """Test string representation with linked game."""
        played = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        self.assertEqual(str(played), "testuser played Test Game 1")

    def test_str_without_game(self):
        """Test string representation when game is null."""
        played = PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=99999,
        )
        self.assertEqual(str(played), "testuser played IGDB:99999")

    def test_unique_constraint_user_igdb_id(self):
        """Test that user+igdb_id must be unique."""
        PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        # Trying to create another record with same user and igdb_id should fail
        with self.assertRaises(IntegrityError):
            PlayedGame.objects.create(
                user=self.user,
                game=self.game1,
                igdb_id=self.game1.igdb_id,
            )

    def test_set_null_on_game_delete(self):
        """Test that game FK is set to null when game is deleted."""
        played = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        self.assertEqual(played.game, self.game1)

        # Delete the game
        self.game1.delete()

        # Refresh and check game is null but record still exists
        played.refresh_from_db()
        self.assertIsNone(played.game)
        self.assertEqual(played.igdb_id, 12345)

    def test_cascade_on_user_delete(self):
        """Test that PlayedGame is deleted when user is deleted."""
        played = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        played_id = played.id

        # Delete the user
        self.user.delete()

        # PlayedGame should be deleted
        self.assertFalse(PlayedGame.objects.filter(id=played_id).exists())

    def test_multiple_users_same_game(self):
        """Test multiple users can mark the same game as played."""
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        played1 = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        played2 = PlayedGame.objects.create(
            user=user2,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )

        self.assertEqual(self.game1.played_by.count(), 2)
        self.assertIn(played1, self.game1.played_by.all())
        self.assertIn(played2, self.game1.played_by.all())


class GameQuerySetPlayedStatusTests(TestCase):
    """Test cases for GameQuerySet.with_played_status() method."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game1 = Game.objects.create(
            name="Played Game",
            rank=1,
            igdb_id=12345,
        )
        cls.game2 = Game.objects.create(
            name="Unplayed Game",
            rank=2,
            igdb_id=67890,
        )
        # Mark game1 as played
        PlayedGame.objects.create(
            user=cls.user,
            game=cls.game1,
            igdb_id=cls.game1.igdb_id,
        )

    def test_with_played_status_authenticated(self):
        """Test annotation for authenticated user."""
        games = Game.objects.with_played_status(self.user)

        game1 = games.get(id=self.game1.id)
        game2 = games.get(id=self.game2.id)

        self.assertTrue(game1.is_played_by_user)
        self.assertFalse(game2.is_played_by_user)

    def test_with_played_status_unauthenticated(self):
        """Test annotation for unauthenticated user returns unmodified queryset."""
        from django.contrib.auth.models import AnonymousUser

        games = Game.objects.with_played_status(AnonymousUser())

        # Should not have is_played_by_user attribute
        game = games.first()
        self.assertFalse(hasattr(game, "is_played_by_user"))

    def test_with_played_status_none_user(self):
        """Test annotation for None user returns unmodified queryset."""
        games = Game.objects.with_played_status(None)

        # Should not have is_played_by_user attribute
        game = games.first()
        self.assertFalse(hasattr(game, "is_played_by_user"))

    def test_with_played_status_different_user(self):
        """Test annotation shows false for different user."""
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        games = Game.objects.with_played_status(user2)

        game1 = games.get(id=self.game1.id)
        game2 = games.get(id=self.game2.id)

        # Neither game should be marked as played for user2
        self.assertFalse(game1.is_played_by_user)
        self.assertFalse(game2.is_played_by_user)


class TogglePlayedGameViewTests(TestCase):
    """Test cases for TogglePlayedGameView."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
        )

    def test_toggle_requires_authentication(self):
        """Test that toggle endpoint requires authentication."""
        from django.urls import reverse

        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})
        response = self.client.post(url)
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_toggle_creates_want_to_play_game(self):
        """Test that first toggle creates WantToPlayGame for authenticated user."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        # First click creates WantToPlayGame, not PlayedGame
        self.assertTrue(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertFalse(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_toggle_deletes_existing_played_game(self):
        """Test that toggle deletes PlayedGame if it already exists."""
        from django.urls import reverse

        # Create existing PlayedGame
        PlayedGame.objects.create(
            user=self.user,
            game=self.game,
            igdb_id=self.game.igdb_id,
        )

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_toggle_404_for_invalid_igdb_id(self):
        """Test that toggle returns 404 for non-existent igdb_id."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": 99999})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

    def test_toggle_returns_button_template(self):
        """Test that toggle returns the played button partial."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        # Should contain the button element
        self.assertIn(b"button", response.content)


class ProfilePlayedCountTests(TestCase):
    """Test cases for played game count in profile view."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game1 = Game.objects.create(
            name="Active Game 1",
            rank=1,
            igdb_id=11111,
        )
        cls.game2 = Game.objects.create(
            name="Active Game 2",
            rank=2,
            igdb_id=22222,
        )

    def test_profile_count_excludes_orphaned_games(self):
        """Test that profile played count excludes orphaned PlayedGame records."""
        from django.urls import reverse

        # Create played records for both games
        PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        PlayedGame.objects.create(
            user=self.user,
            game=self.game2,
            igdb_id=self.game2.igdb_id,
        )

        # Create an orphaned played record (game=None)
        PlayedGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=99999,  # Orphaned - game doesn't exist
        )

        self.client.force_login(self.user)
        url = reverse("auth-modal-profile")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should only count the 2 connected games, not the orphaned one
        self.assertEqual(response.context["played_count"], 2)

    def test_orphaned_records_preserved_for_reconnection(self):
        """Test that orphaned records are preserved and can be reconnected."""
        # Create a played record for game1
        played = PlayedGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )

        # Delete the game - should orphan the PlayedGame record
        igdb_id = self.game1.igdb_id
        self.game1.delete()

        # Verify record is orphaned but still exists
        played.refresh_from_db()
        self.assertIsNone(played.game)
        self.assertEqual(played.igdb_id, igdb_id)

        # Verify user still has the orphaned record
        self.assertEqual(self.user.played_games.count(), 1)

        # But active count (for profile) should be 0
        active_count = self.user.played_games.filter(game__isnull=False).count()
        self.assertEqual(active_count, 0)


class WantToPlayGameModelTests(TestCase):
    """Test cases for WantToPlayGame model."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game1 = Game.objects.create(
            name="Test Game 1",
            rank=1,
            igdb_id=12345,
        )

    def test_create_want_to_play_game(self):
        """Test creating a WantToPlayGame record."""
        want = WantToPlayGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        self.assertEqual(want.user, self.user)
        self.assertEqual(want.game, self.game1)
        self.assertEqual(want.igdb_id, 12345)
        self.assertIsNotNone(want.created)

    def test_str_with_game(self):
        """Test string representation with linked game."""
        want = WantToPlayGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        self.assertEqual(str(want), "testuser wants to play Test Game 1")

    def test_str_without_game(self):
        """Test string representation when game is null."""
        want = WantToPlayGame.objects.create(
            user=self.user,
            game=None,
            igdb_id=99999,
        )
        self.assertEqual(str(want), "testuser wants to play IGDB:99999")

    def test_unique_constraint_user_igdb_id(self):
        """Test that user+igdb_id must be unique."""
        WantToPlayGame.objects.create(
            user=self.user,
            game=self.game1,
            igdb_id=self.game1.igdb_id,
        )
        # Trying to create another record with same user and igdb_id should fail
        with self.assertRaises(IntegrityError):
            WantToPlayGame.objects.create(
                user=self.user,
                game=self.game1,
                igdb_id=self.game1.igdb_id,
            )


class GameStatusCycleTests(TestCase):
    """Test cases for the 3-state game status cycle: none -> want -> played -> none."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game = Game.objects.create(
            name="Test Game",
            rank=1,
            igdb_id=12345,
        )

    def test_cycle_none_to_want(self):
        """Test first click: none -> want to play."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        # Should create WantToPlayGame, not PlayedGame
        self.assertTrue(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertFalse(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_cycle_want_to_played(self):
        """Test second click: want -> played."""
        from django.urls import reverse

        # Set up: game is in want-to-play state
        WantToPlayGame.objects.create(
            user=self.user, game=self.game, igdb_id=self.game.igdb_id
        )

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        # Should remove WantToPlayGame and create PlayedGame
        self.assertFalse(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertTrue(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_cycle_played_to_none(self):
        """Test third click: played -> none."""
        from django.urls import reverse

        # Set up: game is in played state
        PlayedGame.objects.create(
            user=self.user, game=self.game, igdb_id=self.game.igdb_id
        )

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        # Should remove PlayedGame, and NOT create WantToPlayGame
        self.assertFalse(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertFalse(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_full_cycle(self):
        """Test the complete cycle: none -> want -> played -> none."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        # Click 1: none -> want
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

        # Click 2: want -> played
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertFalse(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

        # Click 3: played -> none
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )
        self.assertFalse(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )

    def test_mutual_exclusivity(self):
        """Test that a game cannot be both want-to-play and played."""
        from django.urls import reverse

        self.client.force_login(self.user)
        url = reverse("toggle-played-game", kwargs={"igdb_id": self.game.igdb_id})

        # Start in want state
        self.client.post(url)

        # Transition to played
        self.client.post(url)

        # At no point should both exist
        self.assertFalse(
            WantToPlayGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
            and PlayedGame.objects.filter(
                user=self.user, igdb_id=self.game.igdb_id
            ).exists()
        )


class GameQuerySetWantToPlayStatusTests(TestCase):
    """Test cases for GameQuerySet.with_played_status() including want-to-play."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        cls.game_played = Game.objects.create(
            name="Played Game",
            rank=1,
            igdb_id=11111,
        )
        cls.game_want = Game.objects.create(
            name="Want to Play Game",
            rank=2,
            igdb_id=22222,
        )
        cls.game_none = Game.objects.create(
            name="Untracked Game",
            rank=3,
            igdb_id=33333,
        )
        # Set up statuses
        PlayedGame.objects.create(
            user=cls.user,
            game=cls.game_played,
            igdb_id=cls.game_played.igdb_id,
        )
        WantToPlayGame.objects.create(
            user=cls.user,
            game=cls.game_want,
            igdb_id=cls.game_want.igdb_id,
        )

    def test_with_played_status_annotates_both(self):
        """Test that with_played_status annotates both played and want-to-play."""
        games = Game.objects.with_played_status(self.user)

        game_played = games.get(id=self.game_played.id)
        game_want = games.get(id=self.game_want.id)
        game_none = games.get(id=self.game_none.id)

        # Played game
        self.assertTrue(game_played.is_played_by_user)
        self.assertFalse(game_played.is_want_to_play_by_user)

        # Want to play game
        self.assertFalse(game_want.is_played_by_user)
        self.assertTrue(game_want.is_want_to_play_by_user)

        # Untracked game
        self.assertFalse(game_none.is_played_by_user)
        self.assertFalse(game_none.is_want_to_play_by_user)

"""Tests for SavedFilterSet model and API."""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core.models import User
from games.models import SavedFilterSet


class SavedFilterSetModelTests(TestCase):
    """Test cases for SavedFilterSet model."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_saved_filter_set(self):
        """Test creating a SavedFilterSet record."""
        filters = {
            "q": "zelda",
            "start": 2000,
            "end": 2024,
            "genres": [1, 2],
            "platforms": [3, 4],
            "series": [],
            "sort": "rank",
            "played": "",
        }
        saved = SavedFilterSet.objects.create(
            user=self.user,
            name="My Zelda Filter",
            filters=filters,
        )
        self.assertEqual(saved.user, self.user)
        self.assertEqual(saved.name, "My Zelda Filter")
        self.assertEqual(saved.filters, filters)
        self.assertIsNotNone(saved.created)
        self.assertIsNotNone(saved.modified)

    def test_str_representation(self):
        """Test string representation."""
        saved = SavedFilterSet.objects.create(
            user=self.user,
            name="Nintendo Games 2020",
            filters={},
        )
        self.assertEqual(str(saved), "testuser: Nintendo Games 2020")

    def test_cascade_on_user_delete(self):
        """Test that SavedFilterSet is deleted when user is deleted."""
        saved = SavedFilterSet.objects.create(
            user=self.user,
            name="Test Filter",
            filters={},
        )
        saved_id = saved.id

        self.user.delete()

        self.assertFalse(SavedFilterSet.objects.filter(id=saved_id).exists())

    def test_ordering_by_modified_descending(self):
        """Test that filters are ordered by most recently modified."""
        saved1 = SavedFilterSet.objects.create(
            user=self.user, name="Filter 1", filters={}
        )
        saved2 = SavedFilterSet.objects.create(
            user=self.user, name="Filter 2", filters={}
        )

        # Update saved1 to make it more recent
        saved1.name = "Filter 1 Updated"
        saved1.save()

        filters = list(SavedFilterSet.objects.filter(user=self.user))
        self.assertEqual(filters[0], saved1)
        self.assertEqual(filters[1], saved2)


class SavedFilterSetAPITests(TestCase):
    """Test cases for SavedFilterSet API endpoints."""

    def setUp(self):
        """Set up test client and data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="testpass123",
        )

    def test_list_requires_authentication(self):
        """Test that list endpoint requires authentication."""
        url = reverse("games-api:saved-filter-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_list_returns_user_filters_only(self):
        """Test that list only returns filters for authenticated user."""
        SavedFilterSet.objects.create(
            user=self.user, name="My Filter", filters={"q": "test"}
        )
        SavedFilterSet.objects.create(
            user=self.other_user, name="Other User Filter", filters={}
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["filter_sets"][0]["name"], "My Filter")

    def test_create_requires_authentication(self):
        """Test that create endpoint requires authentication."""
        url = reverse("games-api:saved-filter-list")
        response = self.client.post(
            url,
            data={"name": "Test", "filters": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_create_saved_filter(self):
        """Test creating a new saved filter."""
        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")

        filters = {"q": "mario", "genres": [1, 2], "platforms": []}
        response = self.client.post(
            url,
            data={"name": "Mario Games", "filters": filters},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Mario Games")
        self.assertEqual(data["filters"], filters)

        # Verify it was created in database
        self.assertTrue(
            SavedFilterSet.objects.filter(user=self.user, name="Mario Games").exists()
        )

    def test_create_requires_name(self):
        """Test that create requires a name."""
        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")

        response = self.client.post(
            url,
            data={"name": "", "filters": {}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_name_max_length(self):
        """Test that create enforces name max length."""
        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")

        long_name = "x" * 256  # Exceeds 255 char limit
        response = self.client.post(
            url,
            data={"name": long_name, "filters": {}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_create_enforces_10_filter_limit(self):
        """Test that create enforces maximum of 10 saved filters."""
        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")

        # Create 10 filters
        for i in range(10):
            SavedFilterSet.objects.create(
                user=self.user, name=f"Filter {i}", filters={}
            )

        # Try to create 11th filter
        response = self.client.post(
            url,
            data={"name": "Filter 11", "filters": {}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Maximum", response.json()["error"])

    def test_rename_saved_filter(self):
        """Test renaming a saved filter."""
        saved = SavedFilterSet.objects.create(
            user=self.user, name="Old Name", filters={}
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": saved.id})

        response = self.client.patch(
            url,
            data={"name": "New Name"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "New Name")

        saved.refresh_from_db()
        self.assertEqual(saved.name, "New Name")

    def test_rename_requires_name(self):
        """Test that rename requires a name."""
        saved = SavedFilterSet.objects.create(user=self.user, name="Test", filters={})

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": saved.id})

        response = self.client.patch(
            url,
            data={"name": ""},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_rename_name_too_long(self):
        """Test that rename enforces name max length."""
        saved = SavedFilterSet.objects.create(user=self.user, name="Test", filters={})

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": saved.id})

        response = self.client.patch(
            url,
            data={"name": "x" * 256},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("255", response.json()["error"])

    def test_delete_saved_filter(self):
        """Test deleting a saved filter."""
        saved = SavedFilterSet.objects.create(
            user=self.user, name="To Delete", filters={}
        )
        saved_id = saved.id

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": saved.id})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(SavedFilterSet.objects.filter(id=saved_id).exists())

    def test_cannot_access_other_users_filter(self):
        """Test that user cannot access another user's saved filter."""
        other_saved = SavedFilterSet.objects.create(
            user=self.other_user, name="Other User Filter", filters={}
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": other_saved.id})

        # Try to rename
        response = self.client.patch(
            url,
            data={"name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

        # Try to delete
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)

        # Verify filter still exists unchanged
        other_saved.refresh_from_db()
        self.assertEqual(other_saved.name, "Other User Filter")

    def test_delete_nonexistent_filter(self):
        """Test deleting a nonexistent filter returns 404."""
        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": 99999})

        response = self.client.delete(url)
        self.assertEqual(response.status_code, 404)

    def test_create_duplicate_name_rejected(self):
        """Test that creating a filter with duplicate name is rejected."""
        SavedFilterSet.objects.create(user=self.user, name="My Filter", filters={})

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-list")

        response = self.client.post(
            url,
            data={"name": "My Filter", "filters": {}},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.json()["error"])

    def test_rename_to_duplicate_name_rejected(self):
        """Test that renaming to an existing name is rejected."""
        SavedFilterSet.objects.create(user=self.user, name="First Filter", filters={})
        second = SavedFilterSet.objects.create(
            user=self.user, name="Second Filter", filters={}
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": second.id})

        response = self.client.patch(
            url,
            data={"name": "First Filter"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", response.json()["error"])

    def test_rename_to_same_name_allowed(self):
        """Test that renaming to the same name (no change) is allowed."""
        saved = SavedFilterSet.objects.create(
            user=self.user, name="My Filter", filters={}
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("games-api:saved-filter-detail", kwargs={"pk": saved.id})

        response = self.client.patch(
            url,
            data={"name": "My Filter"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

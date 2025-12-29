"""Tests for constants module."""

from django.test import TestCase

from games import constants


class ListTypeLabelTests(TestCase):
    """Tests for get_list_type_label function."""

    def test_valid_list_types(self):
        """Test that valid list type codes return correct labels."""
        self.assertEqual(constants.get_list_type_label("A"), "All time")
        self.assertEqual(constants.get_list_type_label("D"), "Decade")
        self.assertEqual(constants.get_list_type_label("E"), "End of year")
        self.assertEqual(constants.get_list_type_label("M"), "Miscellaneous")

    def test_invalid_list_type_returns_code(self):
        """Test that invalid type code returns the code itself."""
        self.assertEqual(constants.get_list_type_label("X"), "X")
        self.assertEqual(constants.get_list_type_label(""), "")


class ContactCategoryLabelTests(TestCase):
    """Tests for get_contact_category_label function."""

    def test_valid_categories(self):
        """Test that valid category codes return correct labels."""
        self.assertEqual(
            constants.get_contact_category_label("feature"), "Feature Request"
        )
        self.assertEqual(constants.get_contact_category_label("bug"), "Bug Report")
        self.assertEqual(constants.get_contact_category_label("data"), "Data Issue")
        self.assertEqual(constants.get_contact_category_label("general"), "General")
        self.assertEqual(
            constants.get_contact_category_label("partnership"), "Partnership/Business"
        )
        self.assertEqual(constants.get_contact_category_label("press"), "Press Inquiry")

    def test_invalid_category_returns_code(self):
        """Test that invalid category code returns the code itself."""
        self.assertEqual(constants.get_contact_category_label("unknown"), "unknown")


class ConstantValuesTests(TestCase):
    """Tests for constant values."""

    def test_list_types_tuple(self):
        """Test LIST_TYPES is a list of tuples."""
        self.assertIsInstance(constants.LIST_TYPES, list)
        self.assertEqual(len(constants.LIST_TYPES), 4)
        for item in constants.LIST_TYPES:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)

    def test_contact_categories_tuple(self):
        """Test CONTACT_CATEGORIES is a list of tuples."""
        self.assertIsInstance(constants.CONTACT_CATEGORIES, list)
        self.assertEqual(len(constants.CONTACT_CATEGORIES), 7)
        for item in constants.CONTACT_CATEGORIES:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)

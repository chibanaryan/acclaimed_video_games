"""Coverage tests for deprecated games.mixins compatibility layer."""

import warnings

from django.test import TestCase

from games import mixins as games_mixins


class DeprecatedGamesMixinsTests(TestCase):
    def test_robust_pagination_mixin_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            games_mixins.RobustPaginationMixin()
        self.assertTrue(
            any(
                "games.mixins.RobustPaginationMixin is deprecated" in str(w.message)
                for w in caught
            )
        )

    def test_htmx_partial_mixin_emits_deprecation_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            games_mixins.HTMXPartialMixin()
        self.assertTrue(
            any(
                "games.mixins.HTMXPartialMixin is deprecated" in str(w.message)
                for w in caught
            )
        )

    def test_module_exports_expected_symbols(self):
        self.assertEqual(
            games_mixins.__all__,
            ["RobustPaginationMixin", "HTMXPartialMixin"],
        )

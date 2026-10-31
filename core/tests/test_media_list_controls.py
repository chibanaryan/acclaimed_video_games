"""The ranking-list controls are one partial, shared by every section.

`core/includes/_media_list_controls.html` renders the sort dropdown, the
direction flip, the list/grid toggle and the jump-to-rank box. Games' and
music's results headers were written separately before this and drifted:
music's sort became a pair of native selects in the sidebar and it never had
the other two controls at all. These tests pin the partial's contract and
check both rankings pages actually render it.
"""

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from bs4 import BeautifulSoup

from core.models import User
from games import config as games_config
from core import sites
from core.tests.utils import get_on_site
from games import models as game_models
from music import config as music_config
from music import models as music_models
from music.tests.site import music_site


def render_controls(**context):
    base = {
        "sort_options": music_config.SORT_OPTIONS,
        "default_sort_label": "Rank",
        "item_noun": "Album",
        "total_count": 500,
        "loaded_count": 100,
    }
    base.update(context)
    return BeautifulSoup(
        render_to_string("core/includes/_media_list_controls.html", base),
        "html.parser",
    )


class ControlsPartialTests(TestCase):
    def test_every_sort_option_appears_in_the_menu_and_the_select(self):
        soup = render_controls()
        for option in music_config.SORT_OPTIONS:
            with self.subTest(sort=option["value"]):
                self.assertTrue(
                    soup.select(f'[\\@click="updateSort(\'{option["value"]}\')"]')
                )
                self.assertTrue(soup.select(f'option[value="{option["value"]}"]'))

    def test_the_current_label_expression_covers_every_option(self):
        # The dropdown's label is one chained ternary built from the options,
        # so an option missing from it would show the fallback label instead.
        label = render_controls().select_one('[x-text*="filters.sort"]')["x-text"]
        for option in music_config.SORT_OPTIONS:
            with self.subTest(sort=option["value"]):
                self.assertIn(f"filters.sort === '{option['value']}'", label)

    def test_a_label_expression_is_rendered_unescaped(self):
        # Games' playtime label depends on other filter state, so its label
        # is an Alpine expression. Escaping its quotes would leave Alpine
        # with entities instead of a string.
        label = render_controls(
            sort_options=games_config.SORT_OPTIONS,
        ).select_one(
            '[x-text*="filters.sort"]'
        )["x-text"]
        self.assertIn("filters.hltb_mode === 'completionist'", label)
        self.assertNotIn("&#x27;", label)

    def test_the_jump_box_carries_the_paging_state(self):
        box = render_controls().select_one(".jump-to-rank-input")
        self.assertEqual(box["data-total"], "500")
        self.assertEqual(box["data-loaded"], "100")
        self.assertEqual(box["data-per-page"], "100")
        self.assertEqual(box["placeholder"], "Album #")

    def test_the_view_toggle_can_be_turned_off(self):
        self.assertTrue(render_controls().select('[aria-label="Grid view"]'))
        self.assertFalse(
            render_controls(show_view_toggle=False).select('[aria-label="Grid view"]')
        )

    def test_the_jump_box_can_be_turned_off(self):
        self.assertFalse(
            render_controls(show_jump_to_rank=False).select(".jump-to-rank-input")
        )

    def test_both_count_lines_are_addressable(self):
        # A client-side renderer has to update the desktop and the mobile
        # line; querySelector would only ever find the first.
        soup = render_controls()
        found = {el["data-result-count"] for el in soup.select("[data-result-count]")}
        self.assertEqual(found, {"desktop", "mobile"})

    def test_the_empty_count_label_shows_when_nothing_matched(self):
        soup = render_controls(total_count=0, empty_count_label="Advanced Search")
        self.assertIn("Advanced Search", soup.get_text())


class BothRankingPagesRenderTheControlsTests(TestCase):
    """The point of the partial: one header on both rankings pages."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="controls", password="controlspass"
        )
        self.client.login(username="controls", password="controlspass")

        game_models.Game.objects.create(
            name="Tetris", rank=1, slug="tetris", year_of_release=1984, igdb_id=1
        )
        music_models.Album.objects.create(
            name="Doolittle", rank=1, slug="doolittle", year_released=1989
        )

    def _controls(self, url_name):
        # Each rankings page is on its own site's host
        site = sites.MUSIC if url_name.startswith("music:") else sites.GAMES
        page = get_on_site(self.client, site, url_name).content.decode()
        return BeautifulSoup(page, "html.parser")

    def test_each_page_renders_the_same_controls(self):
        for url_name in ("home", "music:home"):
            with self.subTest(page=url_name):
                soup = self._controls(url_name)
                self.assertTrue(soup.select('[x-text*="filters.sort"]'))
                self.assertTrue(soup.select('[\\@click="toggleSortDirection()"]'))
                self.assertTrue(soup.select('[aria-label="Grid view"]'))
                self.assertTrue(soup.select(".jump-to-rank-input"))

    def test_each_page_offers_its_own_sorts(self):
        # Playtime is games-only; albums have no equivalent metric, so the
        # album page offers the three shared sorts and nothing more.
        music = self._controls("music:home")
        self.assertTrue(music.select("[\\@click=\"updateSort('rank')\"]"))
        self.assertFalse(music.select("[\\@click=\"updateSort('playtime')\"]"))
        self.assertTrue(
            self._controls("home").select("[\\@click=\"updateSort('playtime')\"]")
        )

    def test_music_no_longer_carries_a_second_sort_control(self):
        # The sidebar's native selects were the visible divergence; the form
        # now carries the state as hidden fields instead.
        soup = self._controls("music:home")
        form = soup.select_one("#album-filters")
        self.assertEqual(form.select_one('[name="sort"]')["type"], "hidden")
        self.assertEqual(form.select_one('[name="dir"]')["type"], "hidden")


def render_saved_dropdown(**context):
    base = {"max_saved": 10, "user": AnonymousUser()}
    base.update(context)
    return BeautifulSoup(
        render_to_string("core/includes/_saved_filters_dropdown.html", base),
        "html.parser",
    )


class SavedFilterPartialTests(TestCase):
    """The three saved-filter partials are shared, so they are pinned here.

    They bind to a component contract rather than to a page -
    `loadSavedFilters`, `applySavedFilter`, `saveCurrentFilters`,
    `renameSavedFilter`, `deleteSavedFilter`, `hasActiveFilters` - and both
    `mediaListControls` and games' `filterComponent` expose those names. The
    contract is what lets games migrate onto them later, so a renamed method
    has to fail here.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="saved", password="savedpass")

    def test_a_signed_in_reader_gets_the_working_button(self):
        soup = render_saved_dropdown(user=self.user)
        trigger = soup.select_one('[\\@click="loadSavedFilters()"]')
        self.assertIsNotNone(trigger)
        self.assertNotIn("cursor-not-allowed", trigger.get("class", []))

    def test_a_signed_out_visitor_gets_a_disabled_button_that_says_why(self):
        soup = render_saved_dropdown(signed_out_hint="Sign in to save filters")
        button = soup.select_one("button")
        self.assertIn("cursor-not-allowed", button.get("class", []))
        self.assertEqual(button["aria-label"], "Saved. Sign in to save filters")
        # Nothing to drive, so none of the component's methods are bound.
        self.assertFalse(soup.select('[\\@click="loadSavedFilters()"]'))

    def test_the_row_actions_cover_apply_rename_and_delete(self):
        soup = render_saved_dropdown(user=self.user)
        self.assertTrue(soup.select('[\\@click="applySavedFilter(filter)"]'))
        self.assertTrue(soup.select('[\\@click\\.stop="renameSavedFilter(filter)"]'))
        self.assertTrue(soup.select('[\\@click\\.stop="deleteSavedFilter(filter)"]'))

    def test_saving_is_offered_only_when_there_is_something_to_save(self):
        rendered = render_to_string(
            "core/includes/_saved_filters_dropdown.html",
            {"max_saved": 10, "user": self.user},
        )
        self.assertIn("hasActiveFilters() && savedFiltersLoaded", rendered)

    def test_the_cap_is_rendered_rather_than_hard_coded(self):
        rendered = render_to_string(
            "core/includes/_saved_filters_dropdown.html",
            {"max_saved": 4, "user": self.user},
        )
        self.assertIn("savedFilters.length < 4", rendered)
        self.assertIn("Limit reached (4/4)", rendered)
        self.assertNotIn("(10/10)", rendered)

    def test_the_mobile_block_closes_the_sheet_when_a_filter_is_applied(self):
        rendered = render_to_string(
            "core/includes/_mobile_saved_filters.html",
            {"max_saved": 10, "user": self.user},
        )
        self.assertIn("applySavedFilter(filter); filterOpen = false;", rendered)

    def test_the_mobile_block_loads_lazily_on_first_expand(self):
        rendered = render_to_string(
            "core/includes/_mobile_saved_filters.html",
            {"max_saved": 10, "user": self.user},
        )
        self.assertIn("if (expanded && !savedFiltersLoaded)", rendered)

    def test_the_mobile_block_is_absent_for_a_signed_out_visitor(self):
        rendered = render_to_string(
            "core/includes/_mobile_saved_filters.html",
            {"max_saved": 10, "user": AnonymousUser()},
        )
        self.assertEqual(rendered.strip(), "")

    def test_the_modals_carry_the_ids_the_component_focuses(self):
        # `saveCurrentFilters` and `renameSavedFilter` focus these by id on
        # $nextTick, so a renamed id silently stops the focus working.
        soup = BeautifulSoup(
            render_to_string("core/includes/_saved_filter_modals.html", {}),
            "html.parser",
        )
        self.assertIsNotNone(soup.select_one("#save-filter-name-input"))
        self.assertIsNotNone(soup.select_one("#rename-filter-name-input"))

    def test_each_modal_submits_to_its_own_handler(self):
        rendered = render_to_string("core/includes/_saved_filter_modals.html", {})
        for handler in (
            "submitSaveFilter()",
            "submitRenameFilter()",
            "confirmDeleteFilter()",
        ):
            with self.subTest(handler=handler):
                self.assertIn(handler, rendered)

    def test_the_name_placeholder_is_the_sections_own(self):
        rendered = render_to_string(
            "core/includes/_saved_filter_modals.html",
            {"name_placeholder": "e.g., Jazz of the 1960s"},
        )
        self.assertIn("e.g., Jazz of the 1960s", rendered)


@music_site
class MusicRendersTheSavedFilterUiTests(TestCase):
    """Music is the section wired to the partials; games keeps its own copy."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="musicsaved", password="savedpass"
        )
        self.client.login(username="musicsaved", password="savedpass")
        music_models.Album.objects.create(
            name="Doolittle", rank=1, slug="doolittle", year_released=1989
        )

    def test_the_album_page_renders_the_dropdown_the_sheet_and_the_modals(self):
        page = self.client.get(reverse("music:home")).content.decode()
        self.assertIn("loadSavedFilters()", page)
        self.assertIn("Saved Filters", page)
        self.assertIn("save-filter-name-input", page)
        self.assertIn("rename-filter-name-input", page)

    def test_the_component_is_given_the_endpoint_and_the_cap(self):
        page = self.client.get(reverse("music:home")).content.decode()
        self.assertIn(
            f"savedFiltersUrl: '{reverse('music-api:saved-filter-list')}'", page
        )
        self.assertIn(f"maxSavedFilters: {music_config.MAX_SAVED_FILTERS}", page)

    def test_the_dropdowns_menu_has_a_positioned_parent(self):
        # The menu is absolutely positioned; without `relative` on the
        # actions row it anchors to the page instead of to the button.
        soup = BeautifulSoup(
            self.client.get(reverse("music:home")).content.decode(), "html.parser"
        )
        trigger = soup.select_one('[\\@click="loadSavedFilters()"]')
        self.assertIn("relative", trigger.parent.get("class", []))

    def test_only_one_copy_of_each_modal_is_rendered(self):
        # The sidebar and the sheet drive the same three; a second copy
        # would give two elements the same id and break the focus call.
        page = self.client.get(reverse("music:home")).content.decode()
        self.assertEqual(page.count('id="save-filter-name-input"'), 1)
        self.assertEqual(page.count('id="rename-filter-name-input"'), 1)

"""Dual-rendering tests for the album row.

`_album_row.html` serves twice: the server renders rows with it, and
`music/home.html` renders it empty inside <template> elements for
`album-list-renderer.js` to clone and fill. These tests pin the contract
between the two - every data-slot the renderer writes to has to exist in both
renderings, and in the empty one in particular, where a condition on the item
would quietly leave a slot out.

Reference files that must stay in sync:
- music/templates/music/includes/_album_row.html
- core/templates/core/includes/_base_media_row.html
- music/static/music/js/album-list-renderer.js
"""

import re
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from core import constants as core_constants
from core.models import User
from music import models
from music.tests.site import setUpModule, tearDownModule  # noqa: F401

RENDERER = Path(settings.BASE_DIR) / "music/static/music/js/album-list-renderer.js"

GRID_SLOTS = {
    "root-grid",
    "rank-container",
    "rank-grid",
    "global-rank-grid",
    "cover-link",
    "cover",
    "cover-placeholder",
    "overlay",
    "creator",
    "genres-grid",
    "list-count-grid",
    "title-link-grid",
    "name-grid",
    "year-grid",
}

DESKTOP_SLOTS = {
    "root",
    "media-row",
    "artist-credit-inline",
    "rank",
    "global-rank",
    "thumb-link",
    "thumbnail",
    "thumbnail-placeholder",
    "title-link",
    "name",
    "year-link",
    "year",
    "meta-row",
    "tracking-column",
}

MOBILE_SLOTS = {
    "root-mobile",
    "rank-mobile",
    "thumbnail-mobile",
    "thumbnail-mobile-placeholder",
    "title-mobile",
    "year-mobile",
    "meta-mobile",
    "tracking-column-mobile",
}


def slots(html):
    soup = BeautifulSoup(html, "html.parser")
    return {el["data-slot"] for el in soup.select("[data-slot]")}


def row_slots(variant=None):
    """The slots `_album_row.html` emits with no album, for one variant."""
    context = {"row_variant": variant} if variant else {}
    return slots(render_to_string("music/includes/_album_row.html", context))


TRACKING_SLOTS = {
    "tracking-wrapper",
    "tracking-button",
    "owned-icon",
    "tracked-icon",
    "wanted-icon",
    "untracked-icon",
    "dropdown-menu",
    "menu-owned",
    "menu-tracked",
    "menu-wanted",
    "menu-untracked",
    "btn-owned",
    "btn-tracked",
    "btn-wanted",
    "btn-untracked",
}


def grid_slots():
    """The slots `_album_card_grid.html` emits with no album."""
    return slots(render_to_string("music/includes/_album_card_grid.html", {}))


def tracking_slots():
    """The slots `_listen_button_template.html` emits with no album."""
    return slots(render_to_string("music/includes/_listen_button_template.html", {}))


class EmptyRowTemplateTests(TestCase):
    """The row as it is rendered into a <template>, with no album."""

    def test_the_desktop_variant_carries_every_slot(self):
        self.assertEqual(DESKTOP_SLOTS - row_slots("desktop"), set())

    def test_the_mobile_variant_carries_every_slot(self):
        self.assertEqual(MOBILE_SLOTS - row_slots("mobile"), set())

    def test_each_variant_renders_only_its_own_half(self):
        desktop = row_slots("desktop")
        mobile = row_slots("mobile")
        self.assertEqual(desktop & MOBILE_SLOTS, set())
        self.assertEqual(mobile & DESKTOP_SLOTS - {"meta-row"}, set())

    def test_both_halves_render_when_no_variant_is_given(self):
        # How games and books use the shared row, and how the server renders
        # an album row on the page itself.
        self.assertEqual((DESKTOP_SLOTS | MOBILE_SLOTS) - row_slots(), set())

    def test_the_cover_image_slot_survives_having_no_cover(self):
        # The trap this contract exists for: with the img inside a condition
        # on the album's thumbnail, a clone would have no thumbnail slot and
        # the renderer nowhere to write the cover URL.
        html = render_to_string(
            "music/includes/_album_row.html", {"row_variant": "desktop"}
        )
        soup = BeautifulSoup(html, "html.parser")
        img = soup.select_one('img[data-slot="thumbnail"]')
        self.assertIsNotNone(img)
        self.assertIsNone(img.get("src"))


class ServerRenderedRowTests(TestCase):
    """The same row with an album in it."""

    def setUp(self):
        self.user = User.objects.create_user(username="rowreader", password="rowpass")
        self.client.login(username="rowreader", password="rowpass")

        self.artist = models.Artist.objects.create(name="Pixies", slug="pixies")
        self.genre = models.MusicGenre.objects.create(name="Alternative Rock")
        self.album = models.Album.objects.create(
            name="Doolittle",
            rank=1,
            slug="doolittle",
            artist_credit="Pixies",
            year_released=1989,
        )
        self.album.artists.set([self.artist])
        self.album.genres.set([self.genre])

        publication = models.MusicPublication.objects.create(name="NME")
        source = models.MusicList.objects.create(
            name="Albums of the 1980s",
            year=2021,
            publisher=publication,
            order=1,
            type=core_constants.LIST_DECADE,
        )
        models.AlbumListMembership.objects.create(list=source, album=self.album, rank=1)

    def _page(self):
        return self.client.get(reverse("music:home")).content.decode()

    def test_the_rendered_row_carries_the_same_slots(self):
        found = slots(self._page())
        self.assertEqual((DESKTOP_SLOTS | MOBILE_SLOTS) - found, set())

    def test_the_metadata_line_holds_the_genres_and_list_count(self):
        soup = BeautifulSoup(self._page(), "html.parser")
        meta = soup.select_one('[data-slot="meta-row"]')
        self.assertIn("Alternative Rock", meta.get_text())
        self.assertIn("1 list", meta.get_text())
        # The credit sits beside the title now, not in this line.
        self.assertNotIn("Pixies", meta.get_text())

    def test_the_artist_credit_sits_beside_the_title_and_links(self):
        # `artist_links`, which the renderer reproduces.
        soup = BeautifulSoup(self._page(), "html.parser")
        credit = soup.select_one('[data-slot="artist-credit-inline"]')
        self.assertIsNotNone(credit)
        link = credit.select_one("a")
        self.assertEqual(link["href"], "/artists/pixies/")
        self.assertIn("Pixies", credit.get_text())

    def test_the_credit_sits_on_its_own_line_below_the_title(self):
        # Its own line, a size below the title and a step above the
        # metadata: beside the title it was the first thing truncated, and
        # on exactly the rows that needed it - the long ones.
        soup = BeautifulSoup(self._page(), "html.parser")
        title = soup.select_one('[data-slot="title-link"]')
        credit = soup.select_one('[data-slot="artist-credit-inline"]')
        meta = soup.select_one('[data-slot="meta-row"]')
        self.assertIn("text-lg", title["class"])
        self.assertIn("text-sm", credit["class"])
        self.assertIn("font-semibold", credit["class"])
        # A block of its own, not a span inside the title line.
        self.assertEqual(credit.name, "div")
        self.assertNotIn(credit, title.find_all())
        self.assertNotIn("Pixies", meta.get_text())

    def test_the_credit_is_indented_with_the_other_properties(self):
        # The credit and the metadata line start at the same x; only the
        # title hangs left of them.
        soup = BeautifulSoup(self._page(), "html.parser")
        credit = soup.select_one('[data-slot="artist-credit-inline"]')
        meta = soup.select_one('[data-slot="meta-row"]')
        self.assertIn("ml-4", credit["class"])
        self.assertIn("ml-4", meta["class"])

    def test_the_row_ids_match_what_the_renderer_writes(self):
        page = self._page()
        self.assertIn(f'id="music-{self.album.id}"', page)
        self.assertIn(f'id="music-{self.album.id}-mobile"', page)
        source = RENDERER.read_text()
        self.assertIn("`music-${album.id}`", source)
        self.assertIn("`music-${album.id}-mobile`", source)


class RendererContractTests(TestCase):
    """The renderer must not reach for a slot the templates do not emit."""

    def _declared_slots(self):
        """The slot list `album-list-renderer.js` declares for this purpose."""
        source = RENDERER.read_text()
        block = re.search(r"AlbumListRenderer\.SLOTS = \[(.*?)\];", source, re.S)
        self.assertIsNotNone(block, "AlbumListRenderer.SLOTS is gone")
        return set(re.findall(r"'([a-z-]+)'", block.group(1)))

    def test_the_renderer_declares_the_slots_it_fills(self):
        declared = self._declared_slots()
        self.assertIn("thumbnail", declared)
        self.assertEqual(declared & {"artist-credit", "genres", "list-count"}, set())

    def test_the_templates_emit_every_slot_the_renderer_declares(self):
        self.assertEqual(self._declared_slots() - row_slots(), set())

    def test_the_declared_slots_are_split_across_the_two_variants(self):
        # Each <template> only holds one half, so a slot the renderer fills
        # has to be in the half it clones for that row.
        variants = (("desktop", DESKTOP_SLOTS), ("mobile", MOBILE_SLOTS))
        for variant, expected in variants:
            with self.subTest(variant=variant):
                available = row_slots(variant)
                self.assertEqual(self._declared_slots() & expected - available, set())


class EmptyGridCardTemplateTests(TestCase):
    """The grid card as it is rendered into a <template>, with no album."""

    def test_the_empty_card_carries_every_slot(self):
        self.assertEqual(GRID_SLOTS - grid_slots(), set())

    def test_the_cover_slot_survives_having_no_cover(self):
        # The same trap as the row's thumbnail: with the img inside a
        # condition on the album's artwork, a clone would have nowhere to
        # write the cover URL.
        html = render_to_string("music/includes/_album_card_grid.html", {})
        soup = BeautifulSoup(html, "html.parser")
        img = soup.select_one('img[data-slot="cover"]')
        self.assertIsNotNone(img)
        self.assertIsNone(img.get("src"))

    def test_the_card_is_marked_as_square_artwork(self):
        # Sleeves are square; the shared card CSS reads the shape off this
        # class, and without it covers render in the 90:128 box box art uses.
        html = render_to_string("music/includes/_album_card_grid.html", {})
        soup = BeautifulSoup(html, "html.parser")
        card = soup.select_one(".media-card-grid")
        self.assertIn("media-card-square", card["class"])


class GridRendererContractTests(TestCase):
    """The grid renderer must not reach for a slot the template omits."""

    def _declared_grid_slots(self):
        source = RENDERER.read_text()
        block = re.search(r"AlbumListRenderer\.GRID_SLOTS = \[(.*?)\];", source, re.S)
        self.assertIsNotNone(block, "AlbumListRenderer.GRID_SLOTS is gone")
        return set(re.findall(r"'([a-z-]+)'", block.group(1)))

    def test_the_template_emits_every_slot_the_renderer_declares(self):
        self.assertEqual(self._declared_grid_slots() - grid_slots(), set())

    def test_the_renderer_implements_the_grid_card(self):
        # The base class throws from _renderGridCard, so a grid view that is
        # offered but not implemented fails only when someone clicks it.
        source = RENDERER.read_text()
        self.assertIn("_renderGridCard(compactAlbum, index, showRank)", source)
        self.assertNotIn("Albums have no grid view", source)


class RankedPageGridTests(TestCase):
    """The rankings page renders both views, as the games page does."""

    def setUp(self):
        self.user = User.objects.create_user(username="gridreader", password="gridpass")
        self.client.login(username="gridreader", password="gridpass")
        self.album = models.Album.objects.create(
            name="Doolittle",
            rank=1,
            slug="doolittle",
            artist_credit="Pixies",
            year_released=1989,
        )

    def test_the_page_renders_rows_and_cards_and_the_grid_template(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select(".media-row.desktop"))
        self.assertTrue(soup.select(".media-grid .media-card-grid"))
        self.assertTrue(soup.select("template#grid-card-template"))

    def test_the_view_toggle_and_jump_box_are_present(self):
        page = self.client.get(reverse("music:home")).content.decode()
        soup = BeautifulSoup(page, "html.parser")
        self.assertTrue(soup.select('[aria-label="Grid view"]'))
        self.assertTrue(soup.select('[aria-label="List view"]'))
        self.assertTrue(soup.select(".jump-to-rank-input"))


class EmptyTrackingButtonTemplateTests(TestCase):
    """The listen button as it is rendered into a <template>, with nothing."""

    def test_the_empty_button_carries_every_slot(self):
        self.assertEqual(TRACKING_SLOTS - tracking_slots(), set())

    def test_all_three_states_are_present_at_once(self):
        # The renderer shows one and hides the others, so all three have to
        # exist in the clone; rendering only the current state would leave it
        # with nothing to switch to.
        html = render_to_string("music/includes/_listen_button_template.html", {})
        soup = BeautifulSoup(html, "html.parser")
        for slot in ("tracked-icon", "wanted-icon", "untracked-icon"):
            with self.subTest(slot=slot):
                self.assertIsNotNone(soup.select_one(f'[data-slot="{slot}"]'))

    def test_it_carries_no_item_id_to_start_with(self):
        # The renderer writes one per row. A value here would mean every
        # clone posted to the same album.
        html = render_to_string("music/includes/_listen_button_template.html", {})
        soup = BeautifulSoup(html, "html.parser")
        wrapper = soup.select_one('[data-slot="tracking-wrapper"]')
        self.assertEqual(wrapper["data-item-id"], "")
        self.assertEqual(wrapper["data-status"], "none")

    def test_it_names_the_scope_the_sync_listener_looks_up(self):
        # media-tracking.js finds its config by this attribute; without it
        # the Sets stop being updated and the status filter goes stale.
        html = render_to_string("music/includes/_listen_button_template.html", {})
        soup = BeautifulSoup(html, "html.parser")
        wrapper = soup.select_one('[data-slot="tracking-wrapper"]')
        self.assertEqual(wrapper["data-tracking-scope"], "album")

    def test_it_ships_no_inline_script(self):
        # Games and books each ship a sync script inside the swapped markup.
        # This one is replaced by a single delegated listener, which is what
        # keeps the partial free of inline script.
        html = render_to_string("music/includes/_listen_button_template.html", {})
        self.assertNotIn("<script", html)


class TrackingRendererContractTests(TestCase):
    """The renderer must not reach for a button slot the template omits."""

    def _declared_tracking_slots(self):
        source = RENDERER.read_text()
        block = re.search(
            r"AlbumListRenderer\.TRACKING_SLOTS = \[(.*?)\];", source, re.S
        )
        self.assertIsNotNone(block, "AlbumListRenderer.TRACKING_SLOTS is gone")
        return set(re.findall(r"'([a-z-]+)'", block.group(1)))

    def test_the_template_emits_every_slot_the_renderer_declares(self):
        self.assertEqual(self._declared_tracking_slots() - tracking_slots(), set())

    def test_the_button_slots_are_declared_apart_from_the_row_slots(self):
        # They live in a different template, so a slot listed in SLOTS would
        # be looked for in `_album_row.html` and not found there.
        source = RENDERER.read_text()
        block = re.search(r"AlbumListRenderer\.SLOTS = \[(.*?)\];", source, re.S)
        declared_rows = set(re.findall(r"'([a-z-]+)'", block.group(1)))
        self.assertEqual(declared_rows & self._declared_tracking_slots(), set())


class TrackingColumnTests(TestCase):
    """Where the button sits in a row, and how much room it is given."""

    def test_the_column_is_emitted_with_no_album_and_no_user(self):
        # This is the clone case. Without the `or not item` arm of the guard
        # the <template> would carry no column and the renderer would have
        # nowhere to put the button.
        self.assertIn("tracking-column", row_slots("desktop"))
        self.assertIn("tracking-column-mobile", row_slots("mobile"))

    def test_the_desktop_column_is_the_width_the_games_rows_use(self):
        # 48px, so an album row and a game row line up down the page.
        html = render_to_string(
            "music/includes/_album_row.html", {"row_variant": "desktop"}
        )
        soup = BeautifulSoup(html, "html.parser")
        column = soup.select_one('[data-slot="tracking-column"]')
        for width in ("w-12", "min-w-12", "max-w-12"):
            with self.subTest(width=width):
                self.assertIn(width, column["class"])

    def test_the_button_sits_outside_the_hovered_row(self):
        # The core row places the block outside .media-row on purpose: the
        # row's hover effect would otherwise cover the button. Nothing else
        # pins that, so moving the block would go unnoticed.
        html = render_to_string(
            "music/includes/_album_row.html", {"row_variant": "desktop"}
        )
        soup = BeautifulSoup(html, "html.parser")
        column = soup.select_one('[data-slot="tracking-column"]')
        self.assertIsNone(column.find_parent(attrs={"data-slot": "media-row"}))
        self.assertIsNotNone(column.find_parent(attrs={"data-slot": "root"}))

    def test_the_mobile_row_reserves_a_column_for_the_button(self):
        html = render_to_string(
            "music/includes/_album_row.html", {"row_variant": "mobile"}
        )
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one('[data-slot="root-mobile"]')
        self.assertIn("auto auto 1fr", root["style"])

    def test_a_real_row_narrows_again_when_the_button_is_hidden(self):
        # The flag only means anything on a row that has an album: with no
        # album the guard's `or not item` arm keeps the column, which is the
        # clone case and deliberate. With one, the grid has to go back to two
        # columns or the thumbnail is pushed off centre.
        album = models.Album.objects.create(
            name="Doolittle", rank=1, slug="doolittle", year_released=1989
        )
        html = render_to_string(
            "music/includes/_album_row.html",
            {"row_variant": "mobile", "item": album, "hide_tracking_button": True},
        )
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one('[data-slot="root-mobile"]')
        self.assertIn("grid-template-columns: auto 1fr", root["style"])
        self.assertNotIn("auto auto 1fr", root["style"])

    def test_a_real_row_with_the_button_hidden_omits_the_column(self):
        album = models.Album.objects.create(
            name="Surfer Rosa", rank=2, slug="surfer-rosa", year_released=1988
        )
        html = render_to_string(
            "music/includes/_album_row.html",
            {"row_variant": "desktop", "item": album, "hide_tracking_button": True},
        )
        self.assertNotIn("tracking-column", slots(html))

    def test_the_clone_keeps_the_column_even_with_the_flag_set(self):
        # The contradictory combination, spelled out: a <template> is
        # rendered with no context at all, so it must never lose the column.
        html = render_to_string(
            "music/includes/_album_row.html",
            {"row_variant": "desktop", "hide_tracking_button": True},
        )
        self.assertIn("tracking-column", slots(html))

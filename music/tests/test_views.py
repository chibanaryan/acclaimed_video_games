"""Tests for the music views."""

import re
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import constants as core_constants
from core.models import User
from core.tests.utils import clear_all_caches
from games.models import SiteMetadata
from music import config, models, views
from music.api import views as music_api_views
from music.services import caching, landing_pages, listening_stats
from music.views import _filter_title, group_list_appearances
from music.tests.site import setUpModule, tearDownModule  # noqa: F401


class ClearsCachesMixin:
    """Starts each test with empty caches."""

    def setUp(self):
        super().setUp()
        # The sidebar's filter options and the per-user listened id sets are
        # cached, and `conftest.py` only clears caches for pytest. Under
        # `manage.py test` one test's cached genre tree was being served to
        # the next, which is how a genre created in setUp went missing from
        # the options it was supposed to appear in.
        clear_all_caches()


class SignedInReaderMixin(ClearsCachesMixin):
    """Provides a logged-in reader."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="musicreader", password="musicpass"
        )
        self.client.login(username="musicreader", password="musicpass")


class MusicDataMixin(SignedInReaderMixin):
    """A small but complete ranking: three albums over three lists."""

    def setUp(self):
        super().setUp()
        self.beatles = models.Artist.objects.create(
            name="The Beatles", slug="the-beatles"
        )
        # As ArtistInfo.txt has it: "Neil Young & Crazy Horse" is Neil
        # Young's second name, and "Neil Young & the Stray Gators" a third
        # that no album here uses.
        self.young = models.Artist.objects.create(
            name="Neil Young",
            slug="neil-young",
            name_variants=[
                "Neil Young",
                "Neil Young & Crazy Horse",
                "Neil Young & the Stray Gators",
            ],
        )
        self.rock = models.MusicGenre.objects.create(name="Rock")

        self.revolver = models.Album.objects.create(
            name="Revolver", rank=1, artist_credit="The Beatles", year_released=1966
        )
        self.revolver.artists.set([self.beatles])
        self.revolver.genres.set([self.rock])

        self.rust = models.Album.objects.create(
            name="Rust Never Sleeps",
            rank=2,
            artist_credit="Neil Young & Crazy Horse",
            year_released=1979,
        )
        models.AlbumCredit.objects.create(
            album=self.rust,
            artist=self.young,
            variant=1,
            credited_name="Neil Young & Crazy Horse",
        )

        self.kid_a = models.Album.objects.create(
            name="Kid A", rank=3, artist_credit="Radiohead", year_released=2000
        )

        self.publication = models.MusicPublication.objects.create(name="Pitchfork")
        self.all_time = models.MusicList.objects.create(
            name="The Greatest Albums of All Time",
            year=2020,
            publisher=self.publication,
            order=1,
            type=core_constants.LIST_ALLTIME,
        )
        self.decade = models.MusicList.objects.create(
            name="The Best Albums of the 1960s",
            year=2017,
            publisher=self.publication,
            order=2,
            type=core_constants.LIST_DECADE,
        )
        self.misc = models.MusicList.objects.create(
            name="Best of the Past 25 Years",
            year=2010,
            publisher=self.publication,
            order=3,
            type=core_constants.LIST_MISC,
        )

        models.AlbumListMembership.objects.create(
            list=self.all_time, album=self.revolver, rank=1
        )
        models.AlbumListMembership.objects.create(
            list=self.decade, album=self.revolver, rank=2
        )
        models.AlbumListMembership.objects.create(
            list=self.misc, album=self.rust, rank=5
        )


class AlbumHomePageViewTests(MusicDataMixin, TestCase):
    def test_renders_every_album_in_rank_order(self):
        response = self.client.get(reverse("music:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a.rank for a in response.context["albums"]], [1, 2, 3])

    def test_search_matches_the_album_title(self):
        response = self.client.get(reverse("music:home"), {"q": "revolver"})
        self.assertEqual([a.name for a in response.context["albums"]], ["Revolver"])

    def test_search_matches_the_artist_credit(self):
        response = self.client.get(reverse("music:home"), {"q": "crazy horse"})
        self.assertEqual(
            [a.name for a in response.context["albums"]], ["Rust Never Sleeps"]
        )

    def test_search_matches_the_normalized_name(self):
        album = models.Album.objects.create(
            name="Déjà Vu", rank=4, artist_credit="CSN", year_released=1970
        )
        response = self.client.get(reverse("music:home"), {"q": "Deja"})
        self.assertIn(album, response.context["albums"])

    def test_year_range_filters_both_ends(self):
        response = self.client.get(
            reverse("music:home"), {"start": "1970", "end": "1990"}
        )
        self.assertEqual(
            [a.name for a in response.context["albums"]], ["Rust Never Sleeps"]
        )

    def test_a_non_numeric_year_is_ignored(self):
        response = self.client.get(
            reverse("music:home"), {"start": "nineteen", "end": ""}
        )
        self.assertEqual(len(response.context["albums"]), 3)

    def test_artist_filter(self):
        response = self.client.get(reverse("music:home"), {"artists": "the-beatles"})
        self.assertEqual([a.name for a in response.context["albums"]], ["Revolver"])
        self.assertEqual(response.context["current_artists"], "the-beatles")
        self.assertContains(
            response,
            '<input type="hidden" name="artists" value="the-beatles" '
            'data-label="The Beatles">',
        )

    def test_a_numeric_artist_value_is_not_read_as_a_pk(self):
        # Pks would give away the provider's entry order, one link at a time.
        response = self.client.get(
            reverse("music:home"), {"artists": str(self.beatles.id)}
        )
        self.assertEqual(list(response.context["albums"]), [])
        self.assertNotContains(response, "by The Beatles")

    def test_an_unknown_artist_filters_to_nothing(self):
        response = self.client.get(reverse("music:home"), {"artists": "nobody"})
        self.assertEqual(list(response.context["albums"]), [])
        self.assertEqual(response.context["current_artists"], "nobody")

    def test_a_slug_is_read_in_any_case(self):
        response = self.client.get(reverse("music:home"), {"artists": "The-Beatles"})
        self.assertEqual([a.name for a in response.context["albums"]], ["Revolver"])

    def test_a_value_that_is_no_slug_leaves_the_page_unfiltered(self):
        response = self.client.get(reverse("music:home"), {"artists": "<b>"})
        self.assertFalse(response.context["is_filtered"])
        self.assertEqual(response.context["show_rank"], "alltime")

    def test_only_slug_shaped_values_are_kept(self):
        response = self.client.get(
            reverse("music:home"), {"artists": "the-beatles,<b>,the-beatles"}
        )
        self.assertEqual(response.context["current_artists"], "the-beatles")

    def test_the_artist_filter_finds_albums_under_any_of_their_names(self):
        # Rust Never Sleeps is credited to "Neil Young & Crazy Horse", one of
        # Neil Young's names, so filtering by him finds it.
        response = self.client.get(reverse("music:home"), {"artists": "neil-young"})
        self.assertEqual(
            [a.name for a in response.context["albums"]], ["Rust Never Sleeps"]
        )

    def test_genre_filter(self):
        response = self.client.get(reverse("music:home"), {"genres": str(self.rock.id)})
        self.assertEqual([a.name for a in response.context["albums"]], ["Revolver"])

    def test_a_malformed_filter_is_ignored(self):
        response = self.client.get(
            reverse("music:home"), {"artists": "<a b>", "genres": " , "}
        )
        self.assertEqual(len(response.context["albums"]), 3)

    def test_sort_by_name(self):
        response = self.client.get(reverse("music:home"), {"sort": "name"})
        self.assertEqual(
            [a.name for a in response.context["albums"]],
            ["Kid A", "Revolver", "Rust Never Sleeps"],
        )

    def test_sort_by_year(self):
        response = self.client.get(reverse("music:home"), {"sort": "year"})
        self.assertEqual(
            [a.year_released for a in response.context["albums"]], [1966, 1979, 2000]
        )

    def test_sort_by_list_appearances(self):
        response = self.client.get(
            reverse("music:home"), {"sort": "lists", "dir": "desc"}
        )
        self.assertEqual([a.name for a in response.context["albums"]][0], "Revolver")

    def test_sort_by_list_appearances_ascending_puts_the_unlisted_first(self):
        response = self.client.get(reverse("music:home"), {"sort": "lists"})
        self.assertEqual([a.name for a in response.context["albums"]][0], "Kid A")

    def test_descending_year_keeps_the_rank_tiebreak_ascending(self):
        tie = models.Album.objects.create(
            name="Also 2000", rank=10, artist_credit="Someone", year_released=2000
        )
        response = self.client.get(
            reverse("music:home"), {"sort": "year", "dir": "desc"}
        )
        names = [a.name for a in response.context["albums"]]
        # Both 2000 albums come first, and within them the better rank leads.
        self.assertEqual(names[:2], ["Kid A", tie.name])

    def test_descending_direction_reverses_a_string_sort(self):
        response = self.client.get(
            reverse("music:home"), {"sort": "year", "dir": "desc"}
        )
        self.assertEqual(
            [a.year_released for a in response.context["albums"]], [2000, 1979, 1966]
        )

    def test_descending_direction_reverses_an_expression_sort(self):
        response = self.client.get(
            reverse("music:home"), {"sort": "name", "dir": "desc"}
        )
        self.assertEqual(
            [a.name for a in response.context["albums"]],
            ["Rust Never Sleeps", "Revolver", "Kid A"],
        )

    def test_ascending_direction_is_the_default(self):
        response = self.client.get(reverse("music:home"), {"sort": "year"})
        self.assertEqual(
            [a.year_released for a in response.context["albums"]], [1966, 1979, 2000]
        )

    def test_an_unknown_sort_falls_back_to_rank(self):
        response = self.client.get(reverse("music:home"), {"sort": "bogus"})
        self.assertEqual([a.rank for a in response.context["albums"]], [1, 2, 3])

    def test_context_carries_counts_and_bounds(self):
        response = self.client.get(reverse("music:home"))
        context = response.context
        self.assertEqual(context["album_count"], 3)
        self.assertEqual(context["list_count"], 3)
        self.assertEqual(context["publication_count"], 1)
        self.assertEqual(context["min_year"], 1966)
        self.assertEqual(context["max_year"], 2000)
        self.assertEqual(context["total_count"], 3)
        self.assertEqual(context["loaded_count"], 3)
        self.assertEqual(context["remaining_count"], 0)
        self.assertFalse(context["has_more"])
        self.assertIsNone(context["next_page"])

    def test_context_echoes_the_filter_state(self):
        response = self.client.get(
            reverse("music:home"),
            {"q": "kid", "start": "1990", "end": "2010", "sort": "name", "dir": "desc"},
        )
        context = response.context
        self.assertEqual(context["current_q"], "kid")
        self.assertEqual(context["current_start"], "1990")
        self.assertEqual(context["current_end"], "2010")
        self.assertEqual(context["current_sort"], "name")
        self.assertEqual(context["current_dir"], "desc")
        self.assertTrue(context["is_filtered"])
        self.assertEqual(context["show_rank"], "filtered")

    def test_show_rank_is_alltime_when_unfiltered(self):
        response = self.client.get(reverse("music:home"))
        self.assertFalse(response.context["is_filtered"])
        self.assertEqual(response.context["show_rank"], "alltime")

    def test_query_string_drops_page_and_append(self):
        response = self.client.get(
            reverse("music:home"), {"q": "kid", "page": "1", "append": "true"}
        )
        self.assertEqual(response.context["query_string"], "q=kid")

    def test_highlight_is_parsed_as_an_integer(self):
        response = self.client.get(
            reverse("music:home"), {"highlight": str(self.revolver.id)}
        )
        self.assertEqual(response.context["highlight"], self.revolver.id)

    def test_pagination_reports_more_pages(self):
        for index in range(120):
            models.Album.objects.create(name=f"Filler {index}", rank=100 + index)
        response = self.client.get(reverse("music:home"))
        self.assertTrue(response.context["has_more"])
        self.assertEqual(response.context["next_page"], 2)
        self.assertEqual(response.context["loaded_count"], 100)
        self.assertEqual(response.context["remaining_count"], 23)

    def test_an_out_of_range_page_serves_the_last_page(self):
        response = self.client.get(reverse("music:home"), {"page": "99"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["albums"]), 3)

    def test_htmx_request_targeting_the_results_container(self):
        response = self.client.get(
            reverse("music:home"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="album-results-container",
        )
        self.assertTemplateUsed(response, "music/includes/_album_list_results.html")
        self.assertTemplateNotUsed(response, "base.html")

    def test_htmx_request_without_a_target_serves_the_content_partial(self):
        response = self.client.get(reverse("music:home"), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "music/includes/_album_list_content.html")

    def test_xhr_header_is_treated_as_htmx(self):
        response = self.client.get(
            reverse("music:home"), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertTemplateUsed(response, "music/includes/_album_list_content.html")

    def test_partial_query_param_is_treated_as_htmx(self):
        response = self.client.get(reverse("music:home"), {"partial": "true"})
        self.assertTemplateUsed(response, "music/includes/_album_list_content.html")

    def test_append_request_serves_the_append_partial(self):
        response = self.client.get(reverse("music:home"), {"append": "true"})
        self.assertTemplateUsed(response, "music/includes/_album_list_append.html")

    def test_full_page_request_uses_the_base_template(self):
        response = self.client.get(reverse("music:home"))
        self.assertTemplateUsed(response, "music/home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_empty_result_set_renders_the_empty_state(self):
        response = self.client.get(reverse("music:home"), {"q": "nothingmatches"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["albums"]), 0)
        self.assertContains(response, "No albums match your filters")


class FilterTitleTests(TestCase):
    """The heading describes the filter state, in the site's own wording.

    Composed like the games heading: genres fold into the noun phrase, the
    year range becomes an "of ..." suffix and an artist reads as "by ...".
    """

    BOUNDS = {"min_year": 1955, "max_year": 2019}
    GENRES = [{"id": 1, "name": "Rock"}, {"id": 2, "name": "Soul"}]
    ARTISTS = [{"id": 7, "name": "The Beatles", "slug": "the-beatles"}]

    def test_unfiltered(self):
        self.assertEqual(
            _filter_title({}, **self.BOUNDS), "Most Acclaimed Albums of All Time"
        )

    def test_with_no_bounds_it_omits_the_time_window(self):
        self.assertEqual(_filter_title({}), "Most Acclaimed Albums")

    def test_a_search_query_wins_over_a_year_range(self):
        title = _filter_title(
            {"q": "kid a", "start": "1990", "end": "1999"}, **self.BOUNDS
        )
        self.assertEqual(title, "Albums matching \u201ckid a\u201d")

    def test_a_single_year(self):
        self.assertEqual(
            _filter_title({"start": "1966", "end": "1966"}, **self.BOUNDS),
            "Most Acclaimed Albums of 1966",
        )

    def test_a_full_decade_reads_as_a_decade(self):
        self.assertEqual(
            _filter_title({"start": "1970", "end": "1979"}, **self.BOUNDS),
            "Most Acclaimed Albums of the 1970s",
        )

    def test_an_arbitrary_range_reads_as_a_range(self):
        self.assertEqual(
            _filter_title({"start": "1965", "end": "1972"}, **self.BOUNDS),
            "Most Acclaimed Albums of 1965-1972",
        )

    def test_one_sided_ranges_fill_from_the_data(self):
        # The grid has no notion of an open range; an absent bound is the
        # edge of the data, which is also what the queryset does.
        self.assertEqual(
            _filter_title({"start": "1990"}, **self.BOUNDS),
            "Most Acclaimed Albums of 1990-2019",
        )
        self.assertEqual(
            _filter_title({"end": "1990"}, **self.BOUNDS),
            "Most Acclaimed Albums of 1955-1990",
        )

    def test_a_genre_folds_into_the_phrase(self):
        self.assertEqual(
            _filter_title({"genres": "1"}, genres=self.GENRES, **self.BOUNDS),
            "Most Acclaimed Rock Albums of All Time",
        )

    def test_several_genres_read_as_a_list(self):
        self.assertEqual(
            _filter_title({"genres": "1,2"}, genres=self.GENRES, **self.BOUNDS),
            "Most Acclaimed Rock and Soul Albums of All Time",
        )

    def test_an_artist_reads_as_a_credit(self):
        models.Artist.objects.create(name="The Beatles", slug="the-beatles")
        self.assertEqual(
            _filter_title(
                {"artists": "the-beatles"}, artists=self.ARTISTS, **self.BOUNDS
            ),
            "Most Acclaimed Albums by The Beatles of All Time",
        )

    def test_a_genre_and_a_decade_together(self):
        self.assertEqual(
            _filter_title(
                {"genres": "1", "start": "1970", "end": "1979"},
                genres=self.GENRES,
                **self.BOUNDS,
            ),
            "Most Acclaimed Rock Albums of the 1970s",
        )

    def test_an_unknown_id_is_ignored_rather_than_shown(self):
        self.assertEqual(
            _filter_title({"genres": "999"}, genres=self.GENRES, **self.BOUNDS),
            "Most Acclaimed Albums of All Time",
        )

    def test_the_title_avoids_best_and_top_phrasing(self):
        # Matches the wording rule the games ranking pages follow.
        for params in [
            {},
            {"start": "1970", "end": "1979"},
            {"start": "1966", "end": "1966"},
        ]:
            with self.subTest(params=params):
                title = _filter_title(params).lower()
                self.assertNotIn("best", title)
                self.assertNotIn("top ", title)


class AlbumDetailViewTests(MusicDataMixin, TestCase):
    def test_renders_the_album(self):
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["album"], self.revolver)
        self.assertContains(response, "Revolver")

    def test_the_artist_is_linked_once_under_the_title(self):
        # The subtitle under the title carries the credit; the properties
        # table used to repeat it as an "Artist:" row.
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(
            response, f'href="{self.beatles.get_absolute_url()}"', count=1
        )
        self.assertNotContains(response, "Artist:")

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/no-such-album/").status_code, 404)

    def test_list_appearances_are_grouped_by_type(self):
        response = self.client.get(self.revolver.get_absolute_url())
        grouped = response.context["grouped_lists"]
        self.assertEqual([label for label, _ in grouped], ["All time", "Decade"])
        self.assertEqual(response.context["list_appearance_count"], 2)

    def test_the_grouped_lists_actually_render(self):
        # Books groups by a label map that never matches the stored codes, so
        # its equivalent block renders empty. This must not.
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(response, "Source Lists")
        self.assertContains(response, "All time")
        self.assertContains(response, "The Greatest Albums of All Time")

    def test_total_album_count_is_in_context(self):
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertEqual(response.context["total_album_count"], 3)

    def test_related_albums_exclude_the_album_itself(self):
        other = models.Album.objects.create(
            name="Abbey Road", rank=4, artist_credit="The Beatles"
        )
        other.artists.set([self.beatles])
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertEqual(list(response.context["related_albums"]), [other])

    def test_more_by_names_the_artist_behind_a_credited_name(self):
        # Rust is credited to "Neil Young & Crazy Horse"; "More by" is Neil
        # Young's, and lists everything credited to him.
        harvest = models.Album.objects.create(name="Harvest", rank=9)
        harvest.artists.set([self.young])
        response = self.client.get(self.rust.get_absolute_url())
        self.assertEqual(response.context["more_by_artists"], [self.young])
        self.assertEqual(list(response.context["related_albums"]), [harvest])
        self.assertContains(response, "More by Neil Young<")

    def test_more_by_joins_several_acts(self):
        self.revolver.artists.set([self.beatles, self.young])
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(response, "More by The Beatles &amp; Neil Young")
        self.assertEqual(list(response.context["related_albums"]), [self.rust])

    def test_a_credit_under_another_name_names_the_artist(self):
        response = self.client.get(self.rust.get_absolute_url())
        self.assertTrue(response.context["credits_use_variants"])
        # The credit line reads as credited and links to Neil Young's page.
        self.assertContains(
            response,
            '<a href="/artists/neil-young/" class="link link-accent" '
            'title="Neil Young">Neil Young &amp; Crazy Horse</a>',
        )
        self.assertContains(response, "Artist:")

    def test_a_plain_credit_is_not_spelled_out(self):
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertFalse(response.context["credits_use_variants"])
        self.assertNotContains(response, "Artist:")

    def test_og_image_is_absolute_for_a_stored_cover(self):
        with mock.patch.object(
            models.Album,
            "image",
            new_callable=mock.PropertyMock,
            return_value="/cover/abc/1-500.jpg",
        ):
            response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(
            response,
            '<meta property="og:image" '
            'content="https://music.acclaimedmedia.org/cover/abc/1-500.jpg">',
        )
        self.assertContains(
            response, '"image": "https://music.acclaimedmedia.org/cover/abc/1-500.jpg"'
        )

    def test_an_album_without_a_cover_has_no_preview_image(self):
        with mock.patch.object(
            models.Album, "image", new_callable=mock.PropertyMock, return_value=None
        ):
            response = self.client.get(self.revolver.get_absolute_url())
        self.assertNotContains(response, "og:image")
        self.assertNotContains(response, '"image":')

    def test_og_image_keeps_a_remote_cover_url(self):
        with mock.patch.object(
            models.Album,
            "image",
            new_callable=mock.PropertyMock,
            return_value="https://coverartarchive.org/release-group/x/front-500",
        ):
            response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(
            response,
            '<meta property="og:image" '
            'content="https://coverartarchive.org/release-group/x/front-500">',
        )

    def test_structured_data_names_each_credited_artist(self):
        self.revolver.artists.set([self.beatles, self.young])
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(response, '"byArtist": [')
        self.assertContains(
            response,
            '"url": "https://music.acclaimedmedia.org/artists/neil-young/"',
        )

    def test_a_compilation_has_no_by_artist(self):
        self.kid_a.artist_credit = "Various Artists"
        self.kid_a.save()
        response = self.client.get(self.kid_a.get_absolute_url())
        self.assertNotContains(response, "byArtist")
        self.assertContains(response, "Various Artists")

    def test_no_related_albums_key_without_artists(self):
        response = self.client.get(self.kid_a.get_absolute_url())
        self.assertIsNone(response.context.get("related_albums"))

    def test_an_album_with_no_list_appearances_renders(self):
        response = self.client.get(self.kid_a.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["grouped_lists"], [])

    def test_cover_placeholder_shows_when_there_is_no_cover_art(self):
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(response, "No cover art yet")

    def test_cover_image_renders_when_present(self):
        self.revolver.cover_image_url = "https://example.com/revolver.jpg"
        self.revolver.save()
        response = self.client.get(self.revolver.get_absolute_url())
        self.assertContains(response, "https://example.com/revolver.jpg")


class GroupListAppearancesTests(MusicDataMixin, TestCase):
    def test_groups_follow_the_shared_importance_order(self):
        memberships = list(
            models.AlbumListMembership.objects.select_related("list__publisher")
        )
        grouped = group_list_appearances(memberships)
        self.assertEqual(
            [label for label, _ in grouped],
            ["All time", "Decade", "Miscellaneous"],
        )

    def test_entries_carry_the_fields_the_template_reads(self):
        membership = models.AlbumListMembership.objects.select_related(
            "list__publisher"
        ).get(list=self.all_time)
        grouped = group_list_appearances([membership])
        entry = grouped[0][1][0]
        self.assertEqual(entry["name"], "The Greatest Albums of All Time")
        self.assertEqual(entry["publication"], "Pitchfork")
        self.assertEqual(entry["type"], core_constants.LIST_ALLTIME)
        self.assertEqual(entry["type_name"], "All time")
        self.assertEqual(entry["year"], 2020)
        self.assertEqual(entry["rank"], 1)

    def test_a_list_without_a_publisher_yields_an_empty_publication(self):
        orphan_list = models.MusicList.objects.create(
            name="Unattributed", year=2001, order=9
        )
        membership = models.AlbumListMembership.objects.create(
            list=orphan_list, album=self.kid_a, rank=1
        )
        grouped = group_list_appearances([membership])
        self.assertEqual(grouped[0][1][0]["publication"], "")

    def test_no_memberships_yields_no_groups(self):
        self.assertEqual(group_list_appearances([]), [])


class SearchDropdownTests(MusicDataMixin, TestCase):
    """The sidebar and navbar search boxes place their groups by `order`."""

    def test_the_default_group_order_is_the_server_tie_order(self):
        # createMediaSearchData orders the groups by its limits' keys until a
        # response says otherwise.
        html = self.client.get(reverse("music:home")).content.decode()
        limits = re.findall(r"createMediaSearchData\('[^']*', \{([^}]*)\}\)", html)
        self.assertEqual(len(limits), 2)
        for keys in limits:
            with self.subTest(keys=keys):
                self.assertEqual(
                    tuple(re.findall(r"(\w+):", keys)), music_api_views.SEARCH_GROUPS
                )

    def test_the_groups_are_rendered_in_the_order_the_response_gives(self):
        html = self.client.get(reverse("music:home")).content.decode()
        # Sidebar and mobile navbar each loop over `order` once...
        self.assertEqual(
            html.count('<template x-for="group in order" :key="group">'), 2
        )
        # ...with each group's rows gated on its name.
        for group in ("artists", "albums"):
            with self.subTest(group=group):
                self.assertEqual(
                    html.count(f"x-if=\"group === '{group}' && has('{group}')\""), 2
                )


class ArtistListViewTests(MusicDataMixin, TestCase):
    def test_lists_only_artists_with_albums(self):
        models.Artist.objects.create(name="No Albums", slug="no-albums")
        response = self.client.get(reverse("music:artist-list"))
        names = [a.name for a in response.context["artists"]]
        self.assertNotIn("No Albums", names)
        self.assertIn("The Beatles", names)

    def test_search_filters_by_name(self):
        response = self.client.get(reverse("music:artist-list"), {"q": "beatles"})
        self.assertEqual([a.name for a in response.context["artists"]], ["The Beatles"])

    def test_default_sort_is_album_count_descending(self):
        for index in range(3):
            album = models.Album.objects.create(
                name=f"Beatles {index}", rank=50 + index, artist_credit="The Beatles"
            )
            album.artists.set([self.beatles])
        response = self.client.get(reverse("music:artist-list"))
        self.assertEqual(response.context["artists"][0].name, "The Beatles")

    def test_sort_by_name(self):
        response = self.client.get(
            reverse("music:artist-list"), {"sort": "name", "dir": "asc"}
        )
        self.assertEqual(
            [a.name for a in response.context["artists"]],
            ["Neil Young", "The Beatles"],
        )

    def test_counts_include_albums_credited_under_another_name(self):
        response = self.client.get(reverse("music:artist-list"))
        artists = {a.name: a for a in response.context["artists"]}
        self.assertEqual(artists["Neil Young"].albums_count, 1)
        self.assertEqual(artists["Neil Young"].best_rank, 2)
        self.assertEqual(artists["Neil Young"].top_album, self.rust)

    def test_a_row_shows_the_other_names_in_use(self):
        response = self.client.get(reverse("music:artist-list"))
        artists = {a.name: a for a in response.context["artists"]}
        self.assertEqual(
            artists["Neil Young"].variant_names, ["Neil Young & Crazy Horse"]
        )
        self.assertEqual(artists["The Beatles"].variant_names, [])
        # The desktop row and the mobile card.
        self.assertContains(
            response, "Also credited as Neil Young &amp; Crazy Horse", count=2
        )
        # A name no ranked album carries is not offered.
        self.assertNotContains(response, "Stray Gators")

    def test_columns_put_the_album_count_second(self):
        # A Rank column of its own read as a ranking of the artists.
        html = self.client.get(reverse("music:artist-list")).content.decode()
        self.assertEqual(
            re.findall(r'<th class="font-semibold[^"]*">([^<]+)</th>', html),
            ["Name", "Albums", "Top Album"],
        )

    def test_the_rank_is_inside_the_top_album_link(self):
        for params in ({}, {"append": "true"}):
            with self.subTest(params=params):
                html = self.client.get(
                    reverse("music:artist-list"), params
                ).content.decode()
                # Inside the top album's own link, not a cell of its own.
                self.assertRegex(
                    html,
                    rf'(?s)<a href="{self.rust.get_absolute_url()}"'
                    r"(?:(?!</a>).)*>#2</span>(?:(?!</a>).)*</a>",
                )

    def test_sort_by_top_rank_and_by_name_descending(self):
        response = self.client.get(reverse("music:artist-list"), {"sort": "rank"})
        self.assertEqual(response.context["artists"][0].name, "The Beatles")
        response = self.client.get(
            reverse("music:artist-list"), {"sort": "name", "dir": "desc"}
        )
        self.assertEqual(response.context["artists"][0].name, "The Beatles")

    def test_a_search_matches_a_name_an_album_is_credited_under(self):
        response = self.client.get(reverse("music:artist-list"), {"q": "crazy"})
        self.assertEqual([a.name for a in response.context["artists"]], ["Neil Young"])

    def test_a_search_does_not_match_an_unused_name(self):
        response = self.client.get(reverse("music:artist-list"), {"q": "stray"})
        self.assertEqual(list(response.context["artists"]), [])

    def test_an_unknown_sort_falls_back_to_album_count(self):
        response = self.client.get(reverse("music:artist-list"), {"sort": "nope"})
        self.assertEqual(response.status_code, 200)

    def test_album_count_sort_keeps_the_name_tiebreak_ascending(self):
        # Two acts with one album each must come back A-Z, even though the
        # primary sort is descending.
        response = self.client.get(reverse("music:artist-list"))
        names = [a.name for a in response.context["artists"]]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_context_carries_the_filter_state_and_counts(self):
        response = self.client.get(reverse("music:artist-list"), {"q": "neil"})
        self.assertEqual(response.context["current_q"], "neil")
        self.assertEqual(response.context["current_sort"], "albums")
        self.assertEqual(response.context["current_dir"], "desc")
        self.assertEqual(response.context["total_count"], 1)
        self.assertEqual(response.context["loaded_count"], 1)
        self.assertFalse(response.context["has_more"])

    def test_htmx_request_serves_the_results_partial(self):
        response = self.client.get(reverse("music:artist-list"), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(
            response, "music/artists/includes/_artist_list_results.html"
        )

    def test_append_request_serves_the_append_partial(self):
        response = self.client.get(reverse("music:artist-list"), {"append": "true"})
        self.assertTemplateUsed(
            response, "music/artists/includes/_artist_list_append.html"
        )

    def test_pagination_reports_more_pages(self):
        for index in range(120):
            artist = models.Artist.objects.create(
                name=f"Act {index:03d}", slug=f"act-{index:03d}"
            )
            album = models.Album.objects.create(name=f"LP {index}", rank=200 + index)
            album.artists.set([artist])
        response = self.client.get(reverse("music:artist-list"))
        self.assertTrue(response.context["has_more"])
        self.assertEqual(response.context["next_page"], 2)

    def test_an_empty_search_renders_the_empty_state(self):
        response = self.client.get(reverse("music:artist-list"), {"q": "zzzznope"})
        self.assertEqual(response.context["total_count"], 0)
        self.assertEqual(response.context["loaded_count"], 0)
        self.assertContains(response, "No artists found")

    def _add_artists(self, count):
        for index in range(count):
            artist = models.Artist.objects.create(
                name=f"Act {index:03d}", slug=f"act-{index:03d}"
            )
            album = models.Album.objects.create(name=f"LP {index}", rank=200 + index)
            album.artists.set([artist])

    def test_append_feeds_the_mobile_cards_out_of_band(self):
        # The button targets the desktop <tbody>, so without this the mobile
        # card list never grew past the first page.
        self._add_artists(120)
        response = self.client.get(
            reverse("music:artist-list"), {"page": "2", "append": "true"}
        )
        self.assertContains(
            response, 'hx-swap-oob="beforeend:#artist-list-container-mobile"'
        )
        self.assertTemplateUsed(
            response, "music/artists/includes/_artist_card_mobile.html"
        )
        self.assertContains(response, '<tbody id="artist-append-rows">')

    def test_append_replaces_the_button_while_pages_remain(self):
        # The button removed itself after its request and no response sent
        # a new one, so only page 2 could ever be loaded.
        self._add_artists(250)
        response = self.client.get(
            reverse("music:artist-list"), {"page": "2", "append": "true"}
        )
        self.assertContains(response, 'id="artist-load-more"')
        self.assertContains(response, "page=3&append=true")
        self.assertContains(response, 'hx-select="#artist-append-rows > tr"')
        self.assertContains(response, '<span id="loaded-count" hx-swap-oob="true">')

    def test_the_last_append_clears_the_button(self):
        self._add_artists(120)
        response = self.client.get(
            reverse("music:artist-list"), {"page": "2", "append": "true"}
        )
        self.assertContains(
            response, '<div id="artist-load-more" hx-swap-oob="true"></div>', html=True
        )
        self.assertNotContains(response, "Load more artists")

    def test_the_first_page_button_is_not_out_of_band(self):
        self._add_artists(120)
        response = self.client.get(reverse("music:artist-list"))
        self.assertContains(response, "Load more artists")
        self.assertNotContains(response, 'id="artist-load-more" hx-swap-oob')


class ArtistDetailViewTests(MusicDataMixin, TestCase):
    def test_renders_the_artist_and_their_albums(self):
        response = self.client.get(self.beatles.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["artist"], self.beatles)
        self.assertEqual(response.context["albums_count"], 1)
        self.assertEqual(response.context["best_album"], self.revolver)
        self.assertContains(response, "Revolver")

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/artists/nobody/").status_code, 404)

    def test_an_artist_with_no_albums_renders_the_empty_state(self):
        artist = models.Artist.objects.create(name="Silent", slug="silent")
        response = self.client.get(artist.get_absolute_url())
        self.assertEqual(response.context["albums_count"], 0)
        self.assertIsNone(response.context["best_album"])
        self.assertContains(response, "No ranked albums")

    def test_albums_under_another_name_are_the_artists(self):
        response = self.client.get(self.young.get_absolute_url())
        self.assertEqual(response.context["artist_albums"], [self.rust])
        self.assertEqual(response.context["albums_count"], 1)
        self.assertEqual(
            response.context["also_credited_as"], ["Neil Young & Crazy Horse"]
        )
        self.assertContains(response, "Also credited as")
        # Only the names a ranked album uses.
        self.assertNotContains(response, "Stray Gators")

    def test_albums_with_other_artists_are_listed_apart_and_still_count(self):
        together = models.Album.objects.create(
            name="Together", rank=4, artist_credit="Neil Young & The Beatles"
        )
        models.AlbumCredit.objects.create(album=together, artist=self.young)
        models.AlbumCredit.objects.create(
            album=together, artist=self.beatles, position=1
        )
        response = self.client.get(self.young.get_absolute_url())
        self.assertEqual(response.context["artist_albums"], [self.rust])
        self.assertEqual(response.context["joint_albums"], [together])
        self.assertEqual(response.context["albums_count"], 2)
        self.assertContains(response, "With other artists")
        self.assertEqual(
            sum(bin["count"] for bin in response.context["rank_distribution"]), 2
        )

    def test_a_various_artists_tail_is_not_another_artist(self):
        self.rust.various_artists = True
        self.rust.save()
        response = self.client.get(self.young.get_absolute_url())
        self.assertEqual(response.context["artist_albums"], [self.rust])
        self.assertEqual(response.context["joint_albums"], [])
        self.assertNotContains(response, "With other artists")

    def test_an_artist_only_credited_with_others_has_no_empty_notice(self):
        nico = models.Artist.objects.create(name="Nico", slug="nico")
        models.AlbumCredit.objects.create(album=self.rust, artist=nico, position=1)
        response = self.client.get(nico.get_absolute_url())
        self.assertEqual(response.context["joint_albums"], [self.rust])
        self.assertNotContains(response, "No ranked albums")

    def test_an_artist_credited_only_as_themselves_lists_no_other_names(self):
        response = self.client.get(self.beatles.get_absolute_url())
        self.assertEqual(response.context["also_credited_as"], [])
        self.assertNotContains(response, "Also credited as")

    def test_external_links_render_when_ids_are_set(self):
        self.beatles.wikidata_id = "Q1299"
        self.beatles.musicbrainz_id = "b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d"
        self.beatles.save()
        response = self.client.get(self.beatles.get_absolute_url())
        self.assertContains(response, "wikidata.org/wiki/Q1299")
        self.assertContains(response, "musicbrainz.org/artist/")


class ArtistDetailAlbumSortTests(MusicDataMixin, TestCase):
    """An artist's albums by rank, or in release order."""

    def setUp(self):
        super().setUp()
        self.bowie = models.Artist.objects.create(name="David Bowie", slug="bowie")
        # Rank order is Ziggy, Low, Man; release order Man, Ziggy, Low.
        self.ziggy = self._album("Ziggy Stardust", rank=10, year=1972)
        self.low = self._album("Low", rank=20, year=1977)
        self.man = self._album("The Man Who Sold the World", rank=30, year=1970)

    def _album(self, name, rank, year):
        album = models.Album.objects.create(
            name=name, rank=rank, artist_credit="David Bowie", year_released=year
        )
        album.artists.set([self.bowie])
        return album

    def _albums(self, query="", **headers):
        response = self.client.get(self.bowie.get_absolute_url() + query, **headers)
        self.assertEqual(response.status_code, 200)
        return response, response.context["artist_albums"]

    def test_rank_is_the_default(self):
        response, albums = self._albums()
        self.assertEqual(albums, [self.ziggy, self.low, self.man])
        self.assertEqual(response.context["current_sort"], "rank")
        self.assertEqual(response.context["current_dir"], "asc")

    def test_year_sort_is_oldest_first(self):
        _, albums = self._albums("?sort=year")
        self.assertEqual(albums, [self.man, self.ziggy, self.low])

    def test_year_sort_descending_is_newest_first(self):
        _, albums = self._albums("?sort=year&dir=desc")
        self.assertEqual(albums, [self.low, self.ziggy, self.man])

    def test_an_unknown_sort_falls_back_to_rank(self):
        response, albums = self._albums("?sort=bogus&dir=sideways")
        self.assertEqual(albums, [self.ziggy, self.low, self.man])
        self.assertEqual(response.context["current_sort"], "rank")
        self.assertEqual(response.context["current_dir"], "asc")

    def test_best_album_is_the_top_ranked_in_any_order(self):
        response, _ = self._albums("?sort=year")
        self.assertEqual(response.context["best_album"], self.ziggy)
        self.assertContains(response, "at #10")

    def test_the_control_shows_from_three_albums(self):
        response, _ = self._albums()
        self.assertTrue(response.context["show_album_sort"])
        self.assertContains(response, "Release Date")
        self.assertContains(response, "media-list-controls.min.js")

    def test_the_control_is_hidden_below_three_albums(self):
        response = self.client.get(self.beatles.get_absolute_url())
        self.assertFalse(response.context["show_album_sort"])
        self.assertNotContains(response, "Release Date")

    def test_an_htmx_request_gets_only_the_albums(self):
        response, albums = self._albums("?sort=year", HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(
            response, "music/artists/includes/_artist_album_results.html"
        )
        self.assertNotContains(response, "<h1")
        content = response.content.decode()
        self.assertLess(
            content.index("The Man Who Sold the World"), content.index("Ziggy")
        )

    def test_sorting_by_year_costs_no_extra_queries(self):
        self.client.get(self.bowie.get_absolute_url())  # warm the caches
        with CaptureQueriesContext(connection) as default:
            self.client.get(self.bowie.get_absolute_url())
        with self.assertNumQueries(len(default)):
            self.client.get(self.bowie.get_absolute_url() + "?sort=year")


class AlbumSearchViewTests(MusicDataMixin, TestCase):
    def test_returns_matching_albums(self):
        response = self.client.get(reverse("music:search"), {"q": "revolver"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revolver")

    def test_matches_on_the_artist_credit(self):
        response = self.client.get(reverse("music:search"), {"q": "radiohead"})
        self.assertContains(response, "Kid A")

    def test_no_query_returns_nothing(self):
        response = self.client.get(reverse("music:search"))
        self.assertEqual(len(response.context["albums"]), 0)
        self.assertContains(response, "No albums found")


class MusicListListViewTests(MusicDataMixin, TestCase):
    def test_lists_every_source_in_order(self):
        response = self.client.get(reverse("music:list-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [source.order for source in response.context["music_lists"]], [1, 2, 3]
        )

    def test_album_count_is_annotated(self):
        response = self.client.get(reverse("music:list-list"))
        counts = {s.name: s.album_count for s in response.context["music_lists"]}
        self.assertEqual(counts["The Greatest Albums of All Time"], 1)

    def test_search_matches_the_list_name(self):
        response = self.client.get(reverse("music:list-list"), {"q": "1960s"})
        self.assertEqual(len(response.context["music_lists"]), 1)

    def test_search_matches_the_publication_name(self):
        response = self.client.get(reverse("music:list-list"), {"q": "pitchfork"})
        self.assertEqual(len(response.context["music_lists"]), 3)

    def test_type_filter(self):
        response = self.client.get(
            reverse("music:list-list"), {"type": core_constants.LIST_DECADE}
        )
        self.assertEqual(
            [s.name for s in response.context["music_lists"]],
            ["The Best Albums of the 1960s"],
        )

    def test_an_unknown_type_filter_is_ignored(self):
        response = self.client.get(reverse("music:list-list"), {"type": "Z"})
        self.assertEqual(len(response.context["music_lists"]), 3)

    def test_lists_are_grouped_under_their_publication(self):
        # The page renders one collapsible row per publication, as the games
        # source-lists page does, rather than a card per list.
        response = self.client.get(reverse("music:list-list"))
        groups = response.context["publication_groups"]
        self.assertEqual([g["publication"].name for g in groups], ["Pitchfork"])
        self.assertEqual(len(groups[0]["lists"]), 3)
        self.assertEqual(response.context["publication_count"], 1)

    def test_a_group_counts_its_lists_by_type(self):
        group = self.client.get(reverse("music:list-list")).context[
            "publication_groups"
        ][0]
        self.assertEqual(group["alltime_count"], 1)
        self.assertEqual(group["decade_count"], 1)
        self.assertEqual(group["misc_count"], 1)
        self.assertEqual(group["eoy_count"], 0)

    def test_publications_sort_by_weight_then_by_name(self):
        quiet = models.MusicPublication.objects.create(name="Aardvark Weekly")
        models.MusicList.objects.create(
            name="Our favourite records of 2021",
            year=2021,
            publisher=quiet,
            order=4,
            type=core_constants.LIST_EOY,
        )
        response = self.client.get(reverse("music:list-list"))
        names = [g["publication"].name for g in response.context["publication_groups"]]
        # An all-time list outweighs a year-end one, so Pitchfork leads even
        # though Aardvark sorts first alphabetically.
        self.assertEqual(names, ["Pitchfork", "Aardvark Weekly"])

        alphabetical = self.client.get(reverse("music:list-list"), {"sort": "alpha"})
        self.assertEqual(
            [g["publication"].name for g in alphabetical.context["publication_groups"]],
            ["Aardvark Weekly", "Pitchfork"],
        )

    def test_the_direction_toggle_reverses_the_publications(self):
        models.MusicPublication.objects.create(name="Aardvark Weekly")
        models.MusicList.objects.create(
            name="Our favourite records of 2021",
            year=2021,
            publisher=models.MusicPublication.objects.get(name="Aardvark Weekly"),
            order=4,
            type=core_constants.LIST_EOY,
        )
        response = self.client.get(
            reverse("music:list-list"), {"sort": "alpha", "dir": "desc"}
        )
        self.assertEqual(
            [g["publication"].name for g in response.context["publication_groups"]],
            ["Pitchfork", "Aardvark Weekly"],
        )

    def test_an_unknown_sort_falls_back_to_the_default(self):
        response = self.client.get(reverse("music:list-list"), {"sort": "nonsense"})
        self.assertEqual(response.context["current_sort"], "importance")

    def test_the_year_filter_narrows_the_lists(self):
        response = self.client.get(reverse("music:list-list"), {"year": "2010"})
        self.assertEqual([s.year for s in response.context["music_lists"]], [2010])

    def test_the_filters_count_each_other_but_not_themselves(self):
        # A type count reflects the year filter and vice versa, so neither
        # offers an option that would empty the page.
        response = self.client.get(reverse("music:list-list"), {"year": "2010"})
        counts = {e["code"]: e["count"] for e in response.context["list_types"]}
        self.assertEqual(sum(counts.values()), 1)
        years = {e["year"] for e in response.context["list_years"]}
        self.assertEqual(years, {2010, 2017, 2020})

    def test_context_carries_the_type_summary(self):
        response = self.client.get(reverse("music:list-list"))
        summary = {
            entry["code"]: entry["count"] for entry in response.context["list_types"]
        }
        self.assertEqual(summary[core_constants.LIST_ALLTIME], 1)
        self.assertEqual(summary[core_constants.LIST_DECADE], 1)
        self.assertEqual(summary[core_constants.LIST_MISC], 1)
        self.assertEqual(summary[core_constants.LIST_EOY], 0)
        self.assertEqual(response.context["total_count"], 3)
        self.assertEqual(response.context["current_sort"], "importance")

    def test_htmx_request_serves_the_results_partial(self):
        response = self.client.get(reverse("music:list-list"), HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(
            response, "music/lists/includes/_list_list_results.html"
        )

    def test_an_empty_result_set_renders_the_empty_state(self):
        response = self.client.get(reverse("music:list-list"), {"q": "zzzznope"})
        self.assertEqual(len(response.context["music_lists"]), 0)
        self.assertContains(response, "No lists match these filters")

    def test_a_list_without_a_publisher_renders(self):
        models.MusicList.objects.create(name="Unattributed", year=2001, order=9)
        response = self.client.get(reverse("music:list-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["music_lists"]), 4)


class AlbumCoverViewTests(ClearsCachesMixin, TestCase):
    """Serving our own stored copy of a cover.

    The remote Cover Art Archive URL redirects to archive.org, which 500s
    intermittently, so a page of a hundred covers shows several broken images
    on every load. These are served from here instead.
    """

    def setUp(self):
        super().setUp()
        self.cover = models.AlbumCover.objects.create(
            release_mbid="f04cce33-b9a0-4bed-af11-f84d649652b2",
            image_id="25254108559",
            size=250,
            data=b"\xff\xd8binary",
            content_type="image/jpeg",
            byte_size=8,
        )
        self.url = reverse(
            "music:cover",
            kwargs={
                "release_mbid": self.cover.release_mbid,
                "image_id": self.cover.image_id,
                "size": 250,
            },
        )

    def test_the_bytes_are_served_with_their_content_type(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertEqual(response.content, b"\xff\xd8binary")
        # Computed from the bytes actually served, not the stored count.
        self.assertEqual(response["Content-Length"], "8")

    def test_the_response_is_cached_immutably(self):
        """The URL carries identifiers that never change for an image."""
        response = self.client.get(self.url)
        self.assertIn("immutable", response["Cache-Control"])
        self.assertIn("max-age=31536000", response["Cache-Control"])

    def test_an_unknown_cover_is_404(self):
        url = reverse(
            "music:cover",
            kwargs={"release_mbid": "nope", "image_id": "nope", "size": 250},
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_the_wrong_size_is_404(self):
        url = reverse(
            "music:cover",
            kwargs={
                "release_mbid": self.cover.release_mbid,
                "image_id": self.cover.image_id,
                "size": 1200,
            },
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_the_cover_route_is_not_read_as_an_album_slug(self):
        """It sits above the catch-all <slug:slug>/ pattern."""
        models.Album.objects.create(name="Cover", slug="cover", rank=1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class GenreGroupingTests(TestCase):
    """The genre filter presents a two-level taxonomy, so it uses optgroups."""

    def test_children_are_grouped_under_their_root(self):
        rock = {
            "id": 1,
            "name": "Rock",
            "level": 0,
            "parent_id": None,
            "albums_count": 10,
        }
        punk = {
            "id": 2,
            "name": "Punk",
            "level": 0,
            "parent_id": None,
            "albums_count": 4,
        }
        post_punk = {
            "id": 3,
            "name": "Post-Punk",
            "level": 1,
            "parent_id": 2,
            "albums_count": 3,
        }
        groups = views.group_genre_options([rock, punk, post_punk])
        self.assertEqual([g["root"]["name"] for g in groups], ["Rock", "Punk"])
        self.assertEqual(
            [o["name"] for o in groups[1]["options"]], ["Punk", "Post-Punk"]
        )

    def test_a_root_is_selectable_as_well_as_a_label(self):
        rock = {
            "id": 1,
            "name": "Rock",
            "level": 0,
            "parent_id": None,
            "albums_count": 10,
        }
        groups = views.group_genre_options([rock])
        self.assertEqual(groups[0]["options"], [rock])

    def test_an_orphaned_child_becomes_its_own_group(self):
        """A parent filtered out for having no albums must not lose its child."""
        child = {
            "id": 3,
            "name": "Post-Punk",
            "level": 1,
            "parent_id": 99,
            "albums_count": 3,
        }
        groups = views.group_genre_options([child])
        self.assertEqual(groups[0]["root"]["name"], "Post-Punk")

    def test_children_sort_after_their_root_then_by_name(self):
        rock = {
            "id": 1,
            "name": "Rock",
            "level": 0,
            "parent_id": None,
            "albums_count": 10,
        }
        b = {"id": 2, "name": "B Rock", "level": 1, "parent_id": 1, "albums_count": 1}
        a = {"id": 3, "name": "A Rock", "level": 1, "parent_id": 1, "albums_count": 1}
        groups = views.group_genre_options([rock, b, a])
        self.assertEqual(
            [o["name"] for o in groups[0]["options"]], ["Rock", "A Rock", "B Rock"]
        )

    def test_no_options_means_no_groups(self):
        self.assertEqual(views.group_genre_options([]), [])

    def test_the_album_count_is_selected_for_display(self):
        """Annotating without selecting left the template rendering a blank."""
        genre = models.MusicGenre.objects.create(name="Rock")
        album = models.Album.objects.create(name="A", rank=1)
        album.genres.set([genre])
        options = views._cached_genre_options()
        self.assertEqual(options[0]["albums_count"], 1)


class ClientSideFilteringContextTests(MusicDataMixin, TestCase):
    """What the rankings page hands the client-side filtering bundle."""

    def test_client_side_filtering_is_enabled(self):
        # The bundle's <script> and the <template> elements it clones are
        # both gated on this flag.
        response = self.client.get(reverse("music:home"))
        self.assertTrue(response.context["enable_client_filtering"])

    def test_the_album_data_version_is_rendered_into_the_page(self):
        # This is what lets the client tell a stale copy of the bulk payload
        # from a current one, which is why there is no version/ endpoint.
        response = self.client.get(reverse("music:home"))
        version = response.context["album_data_version"]
        self.assertEqual(len(version), 12)
        self.assertContains(response, f'window.albumDataVersion = "{version}"')

    def test_the_row_templates_are_declared_for_cloning(self):
        response = self.client.get(reverse("music:home"))
        self.assertContains(response, 'id="desktop-row-template"')
        self.assertContains(response, 'id="mobile-row-template"')


class MusicCacheInvalidationTests(MusicDataMixin, TestCase):
    """Every cached key has to be reachable from one invalidation call."""

    def test_invalidation_clears_every_declared_key(self):
        for key in config.CACHE_KEYS:
            cache.set(key, "stale", 60)
        caching.invalidate_music_caches()
        for key in config.CACHE_KEYS:
            with self.subTest(key=key):
                self.assertIsNone(cache.get(key))

    def test_every_cached_key_is_declared_for_invalidation(self):
        # Renders the page, the detail page and the landing index, so each
        # helper populates its key, then checks nothing was cached under a
        # key the invalidation list does not know about.
        self.client.get(reverse("music:home"))
        # Filtered, for the year heatmap's whole-corpus colour scale.
        self.client.get(reverse("music:home"), {"q": "revolver"})
        self.client.get(
            reverse("music:album-detail", kwargs={"slug": self.revolver.slug})
        )
        self.client.get(reverse("music:browse"))
        # The Account modal's, which no page here renders.
        listening_stats.get_listener_counts()
        populated = [key for key in config.CACHE_KEYS if cache.get(key) is not None]
        self.assertEqual(sorted(populated), sorted(config.CACHE_KEYS))

    def test_every_key_carries_the_cache_version(self):
        # One of them did not, so bumping CACHE_VERSION would have left the
        # year bounds stale while invalidating everything else.
        for key in config.CACHE_KEYS:
            with self.subTest(key=key):
                self.assertTrue(key.startswith(f"{config.CACHE_VERSION}:"))


class LastUpdatedStampTests(MusicDataMixin, TestCase):
    """The rankings heading says when the data was last imported.

    `SiteMetadata` is keyed per section, so the album rankings carry their
    own stamp rather than reporting the games import date.
    """

    def test_the_stamp_starts_empty_and_the_heading_omits_it(self):
        response = self.client.get(reverse("music:home"))
        self.assertIsNone(response.context["last_update"])
        self.assertNotContains(response, "Updated:")

    def test_an_import_stamps_the_music_row_only(self):
        SiteMetadata.stamp_update(config.SITE_METADATA_KEY)
        music_row = SiteMetadata.get_instance(config.SITE_METADATA_KEY)
        self.assertIsNotNone(music_row.last_full_update)
        self.assertIsNone(SiteMetadata.get_instance().last_full_update)

    def test_the_heading_shows_the_date_once_stamped(self):
        SiteMetadata.stamp_update(config.SITE_METADATA_KEY)
        clear_all_caches()
        response = self.client.get(reverse("music:home"))
        self.assertIsNotNone(response.context["last_update"])
        self.assertContains(response, "Updated:")


class RankDistributionTests(MusicDataMixin, TestCase):
    """The chart the games rankings and developer pages carry.

    Bins are built from the global maximum rank, not the filtered one, so a
    filtered set is always read against the same axis.
    """

    def test_the_rankings_page_bins_the_filtered_albums(self):
        response = self.client.get(reverse("music:home"))
        bins = response.context["rank_distribution"]
        self.assertEqual(len(bins), config.RANK_DISTRIBUTION_BIN_COUNT)
        self.assertEqual(sum(entry["count"] for entry in bins), 3)
        self.assertEqual(bins[0]["binStart"], 1)
        self.assertEqual(bins[-1]["binEnd"], response.context["max_rank"])

    def test_filtering_narrows_the_bins_but_not_the_axis(self):
        response = self.client.get(reverse("music:home"), {"q": "revolver"})
        bins = response.context["rank_distribution"]
        self.assertEqual(sum(entry["count"] for entry in bins), 1)
        self.assertEqual(bins[-1]["binEnd"], response.context["max_rank"])

    def test_the_page_renders_the_chart(self):
        page = self.client.get(reverse("music:home")).content.decode()
        self.assertIn("rank-distribution", page)
        self.assertIn('id="rank-distribution-update"', page)

    def test_the_artist_page_bins_that_artist(self):
        response = self.client.get(self.beatles.get_absolute_url())
        bins = response.context["rank_distribution"]
        self.assertEqual(sum(entry["count"] for entry in bins), 1)
        self.assertIn("rank-distribution", response.content.decode())


class ArtistSortTests(MusicDataMixin, TestCase):
    """Artists sort the way developers do, including by their best work."""

    def test_sorting_by_top_rank_puts_the_best_album_first(self):
        response = self.client.get(reverse("music:artist-list"), {"sort": "rank"})
        names = [artist.name for artist in response.context["artists"]]
        # Revolver is rank 1, so The Beatles lead.
        self.assertEqual(names[0], "The Beatles")

    def test_sorting_by_albums_still_works(self):
        response = self.client.get(reverse("music:artist-list"), {"sort": "albums"})
        self.assertEqual(response.context["current_sort"], "albums")
        self.assertTrue(response.context["artists"])

    def test_the_control_offers_every_sort(self):
        page = self.client.get(reverse("music:artist-list")).content.decode()
        for option in config.ARTIST_SORT_OPTIONS:
            with self.subTest(sort=option["value"]):
                self.assertIn(f"updateSort('{option['value']}')", page)

    def test_the_search_box_can_clear_itself(self):
        # Every games search input has a clear button; the shared one had
        # none, so these pages could not empty their own search.
        page = self.client.get(reverse("music:artist-list")).content.decode()
        self.assertIn('aria-label="Clear search"', page)


class ListenStatusPageTests(MusicDataMixin, TestCase):
    """What the rankings page renders once tracking exists."""

    def setUp(self):
        super().setUp()
        # The button needs an external id to key its row on, so the shared
        # fixture's albums - which carry none - get one here.
        for album, qid in (
            (self.revolver, "Q-revolver"),
            (self.rust, "Q-rust"),
            (self.kid_a, "Q-kid-a"),
        ):
            album.wikidata_id = qid
            album.save(update_fields=["wikidata_id"])

        models.ListenedAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        models.WantToListenAlbum.objects.create(
            user=self.user, album=self.rust, wikidata_id="Q-rust"
        )
        self.url = reverse("music:home")

    def test_the_status_filter_counts_as_filtering(self):
        # Which is what switches the rank column from all-time positions to
        # positions within the filtered set.
        response = self.client.get(self.url + "?listened=yes")
        self.assertTrue(response.context["is_filtered"])
        self.assertEqual(response.context["show_rank"], "filtered")

    def test_an_absent_status_filter_is_not_filtering(self):
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_filtered"])
        self.assertEqual(response.context["show_rank"], "alltime")

    def test_the_heading_names_the_status(self):
        response = self.client.get(self.url + "?listened=yes")
        self.assertIn(": Heard", response.context["filter_title"])

    def test_the_heading_joins_several_statuses(self):
        # Games appends one label by hand and so cannot say this, although
        # its parameter is multi-select too.
        response = self.client.get(self.url + "?listened=no,yes")
        self.assertIn(": Untracked and Heard", response.context["filter_title"])

    def test_the_heading_joins_three_statuses(self):
        response = self.client.get(self.url + "?listened=no,want,yes")
        self.assertIn(
            ": Untracked, Want to Listen, and Heard",
            response.context["filter_title"],
        )

    def test_the_heading_keeps_the_year_window_too(self):
        response = self.client.get(self.url + "?listened=yes&start=1960&end=1969")
        title = response.context["filter_title"]
        self.assertIn("of the 1960s", title)
        self.assertIn(": Heard", title)

    def test_an_unknown_status_leaves_the_heading_alone(self):
        response = self.client.get(self.url + "?listened=sideways")
        self.assertNotIn(":", response.context["filter_title"])

    def test_the_state_is_echoed_back_for_the_form(self):
        response = self.client.get(self.url + "?listened=yes,want")
        self.assertEqual(response.context["current_listened"], "yes,want")
        self.assertEqual(response.context["filters"]["listened"], ["yes", "want"])

    def test_an_unknown_status_is_dropped_from_the_alpine_state(self):
        response = self.client.get(self.url + "?listened=sideways")
        self.assertEqual(response.context["filters"]["listened"], [])

    def test_the_status_options_reach_the_template(self):
        response = self.client.get(self.url)
        values = [o["value"] for o in response.context["listen_status_options"]]
        self.assertEqual(values, ["no", "want", "yes", "own"])

    def test_every_status_option_shows_its_mark_in_its_colours(self):
        # The filter showed the two gold records in colour and the other two
        # in the text colour; games' showed plain Unicode stars.
        html = self.client.get(self.url).content.decode()
        for mark in (
            "mdi mdi-record-circle-outline opacity-60",
            "mdi mdi-record-plus text-warning",
            "music/images/gold-record",
            "music/images/record-sleeve",
        ):
            with self.subTest(mark=mark):
                self.assertIn(mark, html)

    def test_the_page_renders_the_tracking_id_sets(self):
        # The client-side predicate reads these, which is why they are album
        # pks and not Wikidata ids.
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn(f"window.listenedAlbumIds = new Set([{self.revolver.id}])", html)
        self.assertIn(f"window.wantToListenAlbumIds = new Set([{self.rust.id}])", html)
        self.assertIn("window.isAuthenticated = true", html)

    def test_an_orphaned_row_is_left_out_of_the_sets(self):
        # Between an import and the reconnection pass there is no album id
        # to put in the set.
        models.ListenedAlbum.objects.filter(album=self.revolver).update(album=None)
        response = self.client.get(self.url)
        self.assertIn(
            "window.listenedAlbumIds = new Set([])", response.content.decode()
        )

    def test_the_sidebar_renders_the_status_control(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("Album Status", html)
        self.assertIn("toggleStatusValue('listened', 'yes')", html)
        self.assertIn('name="listened"', html)

    def test_the_sidebar_offers_every_status(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        for option in config.LISTEN_STATUS_OPTIONS:
            with self.subTest(status=option["value"]):
                self.assertIn(
                    f"toggleStatusValue('listened', '{option['value']}')", html
                )

    def test_the_row_renders_the_button_for_a_tracked_album(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn('data-tracking-scope="album"', html)
        self.assertIn(f'data-item-id="{self.revolver.id}"', html)
        self.assertIn('data-status="listened"', html)
        self.assertIn('data-status="want"', html)
        self.assertIn('data-status="none"', html)

    def test_the_button_template_is_declared_for_cloning(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'id="tracking-button-template"')

    def test_the_sync_listener_is_loaded_and_registered(self):
        # Not part of the filtering bundle, so it is here in its own right.
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("media-tracking.min.js", html)
        self.assertIn("window.MediaTracking.register('album'", html)

    def test_the_download_respects_the_status_filter(self):
        response = self.client.get(reverse("music:download") + "?listened=yes")
        body = response.content.decode()
        self.assertIn("Revolver", body)
        self.assertNotIn("Kid A", body)

    def test_the_rank_distribution_respects_the_status_filter(self):
        response = self.client.get(self.url + "?listened=yes")
        total = sum(b["count"] for b in response.context["rank_distribution"])
        self.assertEqual(total, 1)

    def test_the_results_are_filtered(self):
        response = self.client.get(self.url + "?listened=want")
        names = [album.name for album in response.context["albums"]]
        self.assertEqual(names, ["Rust Never Sleeps"])

    # Have: the fourth state, exclusive of Heard

    def _own_kid_a(self):
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.kid_a, wikidata_id="Q-kid-a", owned=True
        )

    def _names(self, query):
        response = self.client.get(self.url + query)
        return sorted(album.name for album in response.context["albums"])

    def test_the_have_filter_shows_only_owned_albums(self):
        self._own_kid_a()
        self.assertEqual(self._names("?listened=own"), ["Kid A"])

    def test_the_heard_filter_leaves_owned_albums_out(self):
        self._own_kid_a()
        self.assertEqual(self._names("?listened=yes"), ["Revolver"])

    def test_the_untracked_filter_leaves_owned_albums_out(self):
        self._own_kid_a()
        self.assertNotIn("Kid A", self._names("?listened=no"))

    def test_the_heading_names_the_owned_status(self):
        response = self.client.get(self.url + "?listened=own")
        self.assertIn(": Owned", response.context["filter_title"])

    def test_the_page_renders_the_owned_id_set(self):
        self._own_kid_a()
        html = self.client.get(self.url).content.decode()
        self.assertIn(f"window.ownedAlbumIds = new Set([{self.kid_a.id}])", html)
        self.assertIn(f"window.listenedAlbumIds = new Set([{self.revolver.id}])", html)

    def test_an_owned_row_renders_its_own_state(self):
        self._own_kid_a()
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-status="own"', html)
        self.assertIn("music/images/record-sleeve", html)

    def test_the_sync_listener_is_given_every_set(self):
        html = self.client.get(self.url).content.decode()
        for name in ("ownedAlbumIds", "listenedAlbumIds", "wantToListenAlbumIds"):
            with self.subTest(name=name):
                self.assertIn(f"'{name}'", html)

    def test_the_quick_mark_picker_is_offered(self):
        html = self.client.get(self.url).content.decode()
        # Two copies: the results header on desktop, and beside the Filters
        # button on mobile, whose controls row has no room left at 360px.
        self.assertEqual(html.count('data-quick-mark-scope="album"'), 2)
        self.assertIn("quick-mark.min.js", html)
        for option in config.QUICK_MARK_OPTIONS:
            with self.subTest(status=option["status"]):
                self.assertIn(
                    f"window.QuickMark.set('album', '{option['status']}')", html
                )

    def test_the_quick_mark_picker_survives_a_results_swap(self):
        # It sits in the results header, which every filter change replaces.
        response = self.client.get(self.url + "?partial=true")
        html = response.content.decode()
        self.assertEqual(html.count('data-quick-mark-scope="album"'), 1)


class ListenStatusAnonymousPageTests(MusicDataMixin, TestCase):
    """The control is visible but inert without a sign-in."""

    def test_the_sets_are_empty_for_a_user_who_tracks_nothing(self):
        response = self.client.get(reverse("music:home"))
        html = response.content.decode()
        self.assertIn("window.listenedAlbumIds = new Set([])", html)
        self.assertIn("window.wantToListenAlbumIds = new Set([])", html)

    def test_the_status_filter_does_nothing_for_an_untracking_user(self):
        response = self.client.get(reverse("music:home") + "?listened=yes")
        self.assertEqual(len(response.context["albums"]), 0)

    def test_a_signed_out_reader_gets_no_quick_mark_picker(self):
        # There is nothing they could mark.
        self.client.logout()
        response = self.client.get(reverse("music:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-quick-mark-scope")


class AlbumDetailListenButtonTests(MusicDataMixin, TestCase):
    """The large button on an album page."""

    def setUp(self):
        super().setUp()
        self.revolver.wikidata_id = "Q-revolver"
        self.revolver.save()
        self.url = reverse("music:album-detail", args=[self.revolver.slug])

    def test_the_flags_reach_the_template(self):
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_listened"])
        self.assertFalse(response.context["is_want_to_listen"])

    def test_the_owned_flag_reaches_the_template(self):
        models.ListenedAlbum.objects.create(
            user=self.user,
            album=self.revolver,
            wikidata_id="Q-revolver",
            owned=True,
        )
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_owned"])
        self.assertFalse(response.context["is_listened"])
        self.assertContains(response, 'data-status="own"')

    def test_the_detail_page_offers_no_quick_mark_picker(self):
        # Without a picker on the page a stored mode does nothing, so the
        # button here always opens its menu.
        response = self.client.get(self.url)
        self.assertNotContains(response, "data-quick-mark-scope")

    def test_the_want_flag_reaches_the_template(self):
        models.WantToListenAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_want_to_listen"])
        self.assertFalse(response.context["is_listened"])

    def test_the_page_renders_the_button_at_the_large_size(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertIn("h-12 w-12", html)
        self.assertIn("size=large", html)

    def test_the_menu_opens_downward_on_a_detail_page(self):
        # The button is in the heading, with nothing above it to open into.
        html = self.client.get(self.url).content.decode()
        self.assertIn("top-full", html)

    def test_the_page_loads_the_sync_listener_itself(self):
        # It loads no filtering bundle, so the listener has to come from here
        # or the Sets would go stale after a toggle.
        html = self.client.get(self.url).content.decode()
        self.assertIn("media-tracking.min.js", html)

    def test_no_button_without_a_wikidata_id(self):
        # Nothing to key a tracking row on.
        self.kid_a.wikidata_id = None
        self.kid_a.save()
        response = self.client.get(
            reverse("music:album-detail", args=[self.kid_a.slug])
        )
        self.assertNotIn("tracking-button-wrapper", response.content.decode())

    def test_the_related_albums_carry_the_listen_annotation(self):
        # They render the same row partial, so without the annotation every
        # button there would read "untracked".
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.rust, wikidata_id="Q-rust"
        )
        other = models.Album.objects.create(
            name="Harvest", rank=9, year_released=1972, wikidata_id="Q-harvest"
        )
        other.artists.set([self.young])
        self.rust.wikidata_id = "Q-rust"
        self.rust.save()

        response = self.client.get(reverse("music:album-detail", args=[other.slug]))
        related = list(response.context["related_albums"])
        self.assertTrue(
            any(getattr(album, "is_listened_by_user", False) for album in related)
        )


class ArtistDetailListenButtonTests(MusicDataMixin, TestCase):
    """The artist page renders the same rows, so it needs the annotation."""

    def test_the_prefetched_albums_carry_the_listen_annotation(self):
        self.revolver.wikidata_id = "Q-revolver"
        self.revolver.save()
        models.ListenedAlbum.objects.create(
            user=self.user, album=self.revolver, wikidata_id="Q-revolver"
        )
        response = self.client.get(
            reverse("music:artist-detail", args=[self.beatles.slug])
        )
        albums = response.context["artist_albums"]
        self.assertTrue(albums)
        self.assertTrue(albums[0].is_listened_by_user)


class MusicQueryBudgetTests(MusicDataMixin, TestCase):
    """The music pages cost a constant number of queries, not one per row.

    `/music/` cost 443 queries and `/music/artists/` 305, measured against
    the 1000-album corpus: 418 identical `music_musicgenre` selects from
    walking the genre tree through `children`, and 200 `music_album` plus 100
    `music_musicbrainzalbumdata` selects from `artist.albums.first` and the
    thumbnail behind it.

    An absolute count drifts for unrelated reasons, so each page is pinned
    two ways: the offending SQL shape must be absent, and adding rows must
    not add queries. The second is what actually catches a reintroduction -
    `games/tests/test_main_views.py` pins its own N+1s the same way.
    """

    # The `children.all()` lookup, which nothing else emits.
    GENRE_WALK = 'music_musicgenre"."parent_id" ='
    # An artist's albums looked up one artist at a time.
    ALBUM_PER_ARTIST = 'music_albumcredit"."artist_id" ='
    # A lazy load of the OneToOne `Album.thumbnail` reads: a lookup by pk.
    # Joined through `select_related` the row arrives with the album instead.
    # Matching the table alone would also catch the legitimate cover-art
    # COUNT(*) in `compute_album_data_version`.
    METADATA_LAZY_LOAD = 'music_musicbrainzalbumdata"."id" ='

    def _capture(self, url):
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return [query["sql"] for query in captured.captured_queries]

    def _matching(self, sqls, *fragments):
        return [sql for sql in sqls if all(f in sql for f in fragments)]

    def _add_genres(self, count):
        """A three-level tree, so a per-node walk has somewhere to recurse.

        Names carry the current row count so a second call does not collide
        with the first on the unique slug.
        """
        start = models.MusicGenre.objects.count()
        roots = []
        for index in range(start, start + count):
            root = models.MusicGenre.objects.create(name=f"Root Genre {index:03d}")
            child = models.MusicGenre.objects.create(
                name=f"Style {index:03d}", parent=root
            )
            models.MusicGenre.objects.create(name=f"Substyle {index:03d}", parent=child)
            self.revolver.genres.add(child)
            roots.append(root)
        return roots

    def _add_artists(self, count):
        start = models.Artist.objects.count()
        for index in range(start, start + count):
            artist = models.Artist.objects.create(
                name=f"Budget Act {index:03d}", slug=f"budget-act-{index:03d}"
            )
            for album_index in range(2):
                album = models.Album.objects.create(
                    name=f"Budget LP {index:03d}-{album_index}",
                    rank=500 + index * 2 + album_index,
                )
                album.artists.set([artist])
                models.MusicBrainzAlbumData.objects.create(
                    album=album,
                    is_primary=True,
                    cover_art_release_mbid=f"rel-{index}-{album_index}",
                    cover_art_image_id=f"img-{index}-{album_index}",
                    cover_art_stored=True,
                )
                album.primary_musicbrainz_album_data = (
                    models.MusicBrainzAlbumData.objects.filter(album=album).first()
                )
                album.save(update_fields=["primary_musicbrainz_album_data"])

    def test_the_rankings_page_never_walks_the_genre_tree_per_node(self):
        self._add_genres(10)
        clear_all_caches()
        sqls = self._capture(reverse("music:home"))
        self.assertEqual(self._matching(sqls, self.GENRE_WALK), [])

    def test_the_rankings_page_cost_does_not_grow_with_the_genre_count(self):
        self._add_genres(3)
        clear_all_caches()
        before = self._capture(reverse("music:home"))
        self._add_genres(30)
        # Without this the second render reads the cached filter options and
        # the invariant would pass whatever the tree did.
        clear_all_caches()
        after = self._capture(reverse("music:home"))
        self.assertEqual(
            len(self._matching(after, 'FROM "music_musicgenre"')),
            len(self._matching(before, 'FROM "music_musicgenre"')),
        )

    def test_a_genre_filter_never_walks_the_tree_per_node(self):
        root = self._add_genres(5)[0]
        clear_all_caches()
        sqls = self._capture(f"{reverse('music:home')}?genres={root.id}")
        self.assertEqual(self._matching(sqls, self.GENRE_WALK), [])

    def test_the_artist_list_fetches_its_albums_in_one_query(self):
        self._add_artists(12)
        clear_all_caches()
        sqls = self._capture(reverse("music:artist-list"))
        self.assertEqual(self._matching(sqls, self.ALBUM_PER_ARTIST, "LIMIT 1"), [])
        self.assertEqual(self._matching(sqls, self.METADATA_LAZY_LOAD), [])

    def test_the_artist_list_cost_does_not_grow_with_the_artist_count(self):
        self._add_artists(3)
        clear_all_caches()
        before = self._capture(reverse("music:artist-list"))
        self._add_artists(30)
        clear_all_caches()
        after = self._capture(reverse("music:artist-list"))
        self.assertEqual(len(after), len(before))

    def test_the_artist_append_partial_has_the_same_budget(self):
        # Load More renders the same row partial, so it needs the same
        # prefetch - and it is a separate view call that could miss it.
        self._add_artists(12)
        clear_all_caches()
        sqls = self._capture(f"{reverse('music:artist-list')}?append=true&page=1")
        self.assertEqual(self._matching(sqls, self.ALBUM_PER_ARTIST, "LIMIT 1"), [])
        self.assertEqual(self._matching(sqls, self.METADATA_LAZY_LOAD), [])

    def test_the_artist_page_cost_does_not_grow_with_its_album_count(self):
        self._add_artists(1)
        artist = models.Artist.objects.get(name__startswith="Budget Act")
        self._capture(artist.get_absolute_url())
        clear_all_caches()
        before = self._capture(artist.get_absolute_url())
        for index in range(10):
            album = models.Album.objects.create(name=f"Extra {index}", rank=900 + index)
            album.artists.set([artist])
        clear_all_caches()
        after = self._capture(artist.get_absolute_url())
        self.assertEqual(len(after), len(before))

    def test_the_album_page_cost_does_not_grow_with_more_by(self):
        url = self.rust.get_absolute_url()
        # One related album first: with none the "More by" query never runs.
        models.Album.objects.create(name="Harvest", rank=899).artists.set([self.young])
        self._capture(url)
        clear_all_caches()
        before = self._capture(url)
        for index in range(10):
            album = models.Album.objects.create(name=f"Young {index}", rank=900 + index)
            album.artists.set([self.young])
        clear_all_caches()
        after = self._capture(url)
        self.assertEqual(len(after), len(before))

    def test_the_bulk_payload_neither_walks_genres_nor_loads_covers_lazily(self):
        self._add_genres(5)
        self._add_artists(5)
        clear_all_caches()
        sqls = self._capture(reverse("music-api:album-all-data"))
        self.assertEqual(self._matching(sqls, self.GENRE_WALK), [])
        self.assertEqual(self._matching(sqls, self.METADATA_LAZY_LOAD), [])

    def _landing_urls(self):
        return [
            reverse("music:by-genre", kwargs={"slug": self.rock.slug}),
            reverse("music:by-decade", kwargs={"decade": 1960}),
        ]

    def test_the_landing_pages_never_walk_the_genre_tree_per_node(self):
        self._add_genres(10)
        with mock.patch.object(landing_pages, "MIN_GENRE_ALBUMS", 1), mock.patch.object(
            landing_pages, "MIN_DECADE_ALBUMS", 1
        ):
            for url in self._landing_urls():
                with self.subTest(url=url):
                    clear_all_caches()
                    sqls = self._capture(url)
                    self.assertEqual(self._matching(sqls, self.GENRE_WALK), [])

    def test_a_landing_page_cost_does_not_grow_with_the_genre_count(self):
        url = self._landing_urls()[0]
        with mock.patch.object(landing_pages, "MIN_GENRE_ALBUMS", 1):
            self._add_genres(3)
            clear_all_caches()
            before = self._capture(url)
            self._add_genres(30)
            clear_all_caches()
            after = self._capture(url)
        self.assertEqual(
            len(self._matching(after, 'FROM "music_musicgenre"')),
            len(self._matching(before, 'FROM "music_musicgenre"')),
        )

    def test_the_pages_stay_inside_a_loose_ceiling(self):
        self._add_genres(10)
        self._add_artists(12)
        clear_all_caches()
        landing = self._landing_urls()
        for url, ceiling in (
            (reverse("music:home"), 40),
            (landing[0], 45),
            (landing[1], 45),
            (reverse("music:browse"), 15),
            (reverse("music:artist-list"), 20),
            (reverse("music-api:album-all-data"), 20),
        ):
            with self.subTest(url=url), mock.patch.object(
                landing_pages, "MIN_GENRE_ALBUMS", 1
            ), mock.patch.object(landing_pages, "MIN_DECADE_ALBUMS", 1):
                clear_all_caches()
                self.assertLessEqual(len(self._capture(url)), ceiling)


class HiddenFilterUIDeferralTests(MusicDataMixin, TestCase):
    """The album rankings page skips the filter UI the visitor cannot see.

    At a 4x CPU slowdown Alpine's init on /music/ cost ~360 ms, most of it
    for the desktop sidebar (display:none on a phone) and the closed mobile
    sheet. The same deferral as the games page: the sheet's filters render
    on first open, and the sidebar is x-ignored on a narrow first load.
    """

    def _html(self):
        response = self.client.get(reverse("music:home"))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_closed_mobile_sheet_renders_its_filters_lazily(self):
        html = self._html()
        form = html.index('id="mobile-filter-form"')
        self.assertLess(
            html.index('<template x-if="hasOpenedBefore">', form) - form, 200
        )

    def test_hidden_sidebar_is_deferred_below_the_breakpoint(self):
        html = self._html()
        self.assertIn('id="album-filter-sidebar"', html)
        script = html[html.index('id="album-filter-sidebar"') :]
        self.assertIn("document.getElementById('album-filter-sidebar')", script)
        self.assertIn("sidebar.setAttribute('x-ignore', '')", script)

    def test_controls_know_the_client_engine(self):
        # Without it the leading-edge commit could never fire, and the
        # sheet could only re-send the counts the server rendered.
        self.assertIn("clientEngine: () =>", self._html())

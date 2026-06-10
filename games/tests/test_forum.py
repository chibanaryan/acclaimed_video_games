"""
Tests for the django-machina forum integration.

Covers the forum setup helpers (games/forum.py), the Publication
reputation-score topic sync, the staff-to-moderator signal, and the
permission model (anonymous read, authenticated post, staff moderate).
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from machina.core.db.models import get_model

from games.forum import (
    ANONYMOUS_PERMISSIONS,
    FORUM_MODERATORS_GROUP_NAME,
    PUBLICATIONS_FORUM_NAME,
    SCORES_TOPIC_SUBJECT,
    SITE_FEEDBACK_FORUM_NAME,
    ensure_anonymous_read_permissions,
    ensure_forum_moderators_group,
    ensure_forum_structure,
    sync_publication_scores_topic,
)
from games.signals import add_staff_to_forum_moderators, sync_publication_forum_topic
from games.models import Publication

User = get_user_model()
Forum = get_model("forum", "Forum")
Topic = get_model("forum_conversation", "Topic")
ForumPost = get_model("forum_conversation", "Post")
UserForumPermission = get_model("forum_permission", "UserForumPermission")
GroupForumPermission = get_model("forum_permission", "GroupForumPermission")


class ForumStructureTests(TestCase):
    def test_ensure_forum_structure_creates_both_forums(self):
        forums = ensure_forum_structure()
        self.assertEqual(forums["site_feedback"].name, SITE_FEEDBACK_FORUM_NAME)
        self.assertEqual(forums["publications"].name, PUBLICATIONS_FORUM_NAME)

    def test_ensure_forum_structure_is_idempotent(self):
        ensure_forum_structure()
        ensure_forum_structure()
        self.assertEqual(Forum.objects.count(), 2)

    def test_setup_forum_command_runs_cleanly(self):
        Publication.objects.create(name="Edge")
        User.objects.create_user("staffer", "s@example.com", "pw", is_staff=True)
        call_command("setup_forum", verbosity=0)
        self.assertEqual(Forum.objects.count(), 2)
        self.assertTrue(Topic.objects.filter(subject=SCORES_TOPIC_SUBJECT).exists())


class PublicationScoresTopicTests(TestCase):
    def scores_post(self):
        return sync_publication_scores_topic().first_post.content.raw

    def test_topic_created_in_publications_forum(self):
        topic = sync_publication_scores_topic()
        self.assertEqual(topic.subject, SCORES_TOPIC_SUBJECT)
        self.assertEqual(topic.forum.name, PUBLICATIONS_FORUM_NAME)
        self.assertEqual(topic.type, topic.TOPIC_STICKY)

    def test_publication_save_adds_table_row(self):
        Publication.objects.create(name="Famitsu", reputation_score=85)
        self.assertIn("| 1 | Famitsu | 85 |", self.scores_post())

    def test_scores_sorted_descending_with_ranks(self):
        Publication.objects.create(name="Low", reputation_score=10)
        Publication.objects.create(name="High", reputation_score=90)
        content = self.scores_post()
        self.assertIn("| 1 | High | 90 |", content)
        self.assertIn("| 2 | Low | 10 |", content)

    def test_unrated_publications_listed_without_rank(self):
        Publication.objects.create(name="Polygon")
        self.assertIn("| — | Polygon | not yet rated |", self.scores_post())

    def test_score_change_updates_table(self):
        publication = Publication.objects.create(name="IGN", reputation_score=70)
        publication.reputation_score = 90
        publication.save()
        content = self.scores_post()
        self.assertIn("| 1 | IGN | 90 |", content)
        self.assertNotIn("| 70 |", content)

    def test_publication_delete_removes_row(self):
        publication = Publication.objects.create(name="Kotaku", reputation_score=50)
        publication.delete()
        self.assertNotIn("Kotaku", self.scores_post())

    def test_only_one_topic_created(self):
        Publication.objects.create(name="Edge", reputation_score=80)
        Publication.objects.create(name="Wired", reputation_score=60)
        sync_publication_scores_topic()
        self.assertEqual(Topic.objects.filter(subject=SCORES_TOPIC_SUBJECT).count(), 1)

    def test_topic_renders_with_html_table(self):
        Publication.objects.create(name="Eurogamer", reputation_score=77)
        topic = sync_publication_scores_topic()
        ensure_anonymous_read_permissions()
        url = reverse(
            "forum_conversation:topic",
            kwargs={
                "forum_slug": topic.forum.slug,
                "forum_pk": topic.forum.pk,
                "slug": topic.slug,
                "pk": topic.pk,
            },
        )
        response = Client().get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<table>")
        self.assertContains(response, "Eurogamer")


class ForumSignalRobustnessTests(TestCase):
    """The forum sync must never break a Publication or User save."""

    def test_publication_save_survives_forum_error(self):
        with mock.patch(
            "games.forum.sync_publication_scores_topic",
            side_effect=RuntimeError("boom"),
        ):
            publication = Publication.objects.create(name="Destructoid")
        self.assertTrue(Publication.objects.filter(pk=publication.pk).exists())

    def test_staff_save_survives_forum_error(self):
        with mock.patch(
            "games.forum.ensure_forum_moderators_group",
            side_effect=RuntimeError("boom"),
        ):
            staff = User.objects.create_user(
                "errstaff", "e@example.com", "pw", is_staff=True
            )
        self.assertFalse(staff.groups.filter(name=FORUM_MODERATORS_GROUP_NAME).exists())

    def test_publication_signal_skips_fixture_loading(self):
        publication = Publication.objects.create(name="VG247")
        with mock.patch("games.forum.sync_publication_scores_topic") as mocked:
            sync_publication_forum_topic(Publication, publication, raw=True)
        mocked.assert_not_called()

    def test_staff_signal_skips_fixture_loading(self):
        staff = User.objects.create_user(
            "rawstaff", "raw@example.com", "pw", is_staff=True
        )
        with mock.patch("games.forum.ensure_forum_moderators_group") as mocked:
            add_staff_to_forum_moderators(User, staff, raw=True)
        mocked.assert_not_called()

    def test_anonymous_permission_grant_tolerates_missing_permission(self):
        # machina creates its ForumPermission rows in post_migrate; on a
        # brand-new database setup_forum may run before they exist
        ForumPermission = get_model("forum_permission", "ForumPermission")
        ForumPermission.objects.filter(codename=ANONYMOUS_PERMISSIONS[0]).delete()
        ensure_anonymous_read_permissions()
        self.assertFalse(
            UserForumPermission.objects.filter(
                permission__codename=ANONYMOUS_PERMISSIONS[0]
            ).exists()
        )
        self.assertTrue(
            UserForumPermission.objects.filter(
                permission__codename=ANONYMOUS_PERMISSIONS[1]
            ).exists()
        )


class StaffModeratorSignalTests(TestCase):
    def test_staff_user_added_to_moderators_group(self):
        staff = User.objects.create_user(
            "modstaff", "m@example.com", "pw", is_staff=True
        )
        self.assertTrue(staff.groups.filter(name=FORUM_MODERATORS_GROUP_NAME).exists())

    def test_regular_user_not_added_to_moderators_group(self):
        user = User.objects.create_user("regular", "r@example.com", "pw")
        self.assertFalse(user.groups.filter(name=FORUM_MODERATORS_GROUP_NAME).exists())

    def test_promoting_user_to_staff_adds_group(self):
        user = User.objects.create_user("later", "l@example.com", "pw")
        user.is_staff = True
        user.save()
        self.assertTrue(user.groups.filter(name=FORUM_MODERATORS_GROUP_NAME).exists())

    def test_moderators_group_has_global_permissions(self):
        group = ensure_forum_moderators_group()
        self.assertTrue(
            GroupForumPermission.objects.filter(
                group=group, forum=None, has_perm=True
            ).exists()
        )


class ForumPermissionViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.forums = ensure_forum_structure()
        ensure_anonymous_read_permissions()
        cls.user = User.objects.create_user("poster", "p@example.com", "pw")
        cls.staff = User.objects.create_user(
            "moderator", "mod@example.com", "pw", is_staff=True
        )

    def setUp(self):
        self.client = Client()
        self.feedback = self.forums["site_feedback"]
        self.create_url = reverse(
            "forum_conversation:topic_create",
            kwargs={"forum_slug": self.feedback.slug, "forum_pk": self.feedback.pk},
        )

    def test_forum_index_renders_for_anonymous(self):
        response = self.client.get(reverse("forum:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, SITE_FEEDBACK_FORUM_NAME)
        self.assertContains(response, PUBLICATIONS_FORUM_NAME)

    def test_forum_index_uses_site_chrome(self):
        response = self.client.get(reverse("forum:index"))
        # the site sidebar nav is present (not machina's standalone page)
        self.assertContains(response, "Developers")

    def test_anonymous_cannot_create_topic(self):
        response = self.client.get(self.create_url)
        self.assertIn(response.status_code, (302, 403))

    def test_authenticated_user_can_create_topic(self):
        self.client.force_login(self.user)
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_can_post_topic(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.create_url,
            {
                "subject": "Great site",
                "content": "Love the rankings, one suggestion though...",
            },
        )
        self.assertEqual(response.status_code, 302)
        topic = Topic.objects.get(subject="Great site")
        self.assertTrue(topic.approved)
        self.assertEqual(topic.poster, self.user)

    def test_staff_can_access_moderation_queue(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("forum_moderation:queue"))
        self.assertEqual(response.status_code, 200)

    def test_regular_user_cannot_access_moderation_queue(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("forum_moderation:queue"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_can_read_scores_topic(self):
        Publication.objects.create(name="Retro Gamer", reputation_score=77)
        topic = sync_publication_scores_topic()
        url = reverse(
            "forum_conversation:topic",
            kwargs={
                "forum_slug": topic.forum.slug,
                "forum_pk": topic.forum.pk,
                "slug": topic.slug,
                "pk": topic.pk,
            },
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retro Gamer")


class ForumNavLinkTests(TestCase):
    def test_sidebar_contains_forum_link_when_enabled(self):
        ensure_forum_structure()
        ensure_anonymous_read_permissions()
        response = Client().get(reverse("forum:index"))
        self.assertContains(response, 'href="/forum/"')
        self.assertContains(response, "mdi-forum")


class ForumSearchTests(TestCase):
    """The custom search form/view that replaces machina's stock search
    (whose SearchQuerySet filters silently return nothing on haystack's
    simple backend)."""

    @classmethod
    def setUpTestData(cls):
        ensure_forum_structure()
        ensure_anonymous_read_permissions()
        cls.user = User.objects.create_user("searcher", "se@example.com", "pw")
        Publication.objects.create(name="Edge Magazine", reputation_score=88)
        cls.topic = sync_publication_scores_topic()
        ForumPost.objects.create(
            topic=cls.topic,
            poster=cls.user,
            subject="Edge Magazine",
            content="I disagree with this exemplary score",
            approved=True,
        )

    def search(self, **params):
        response = Client().get(reverse("forum_search:search"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def test_blank_query_shows_form(self):
        self.search()

    def test_content_search_finds_posts(self):
        response = self.search(q="exemplary")
        self.assertContains(response, SCORES_TOPIC_SUBJECT)
        self.assertContains(response, "<b>1</b>", html=False)

    def test_search_finds_reputation_score_post(self):
        response = self.search(q="Edge Magazine")
        self.assertContains(response, SCORES_TOPIC_SUBJECT)

    def test_topic_only_search(self):
        # "exemplary" appears in a post body but in no topic subject
        response = self.search(q="exemplary", search_topics="on")
        self.assertContains(response, "<b>0</b>", html=False)
        response = self.search(q="reputation scores", search_topics="on")
        self.assertContains(response, "Your search has returned")

    def test_poster_name_filter(self):
        # NB: assert on the highlighted query term - haystack's highlight
        # tag trims the excerpt to start at the first match
        response = self.search(q="exemplary", search_poster_name="searcher")
        self.assertContains(response, "<b>1</b>", html=False)
        response = self.search(q="exemplary", search_poster_name="someoneelse")
        self.assertContains(response, "<b>0</b>", html=False)

    def test_forum_filter(self):
        publications_forum = self.topic.forum
        feedback_forum = Forum.objects.get(name=SITE_FEEDBACK_FORUM_NAME)
        response = self.search(q="exemplary", search_forums=publications_forum.pk)
        self.assertContains(response, "<b>1</b>", html=False)
        response = self.search(q="exemplary", search_forums=feedback_forum.pk)
        self.assertContains(response, "<b>0</b>", html=False)

    def test_result_links_resolve(self):
        response = self.search(q="exemplary")
        url = reverse(
            "forum_conversation:topic",
            kwargs={
                "forum_slug": self.topic.forum.slug,
                "forum_pk": self.topic.forum.pk,
                "slug": self.topic.slug,
                "pk": self.topic.pk,
            },
        )
        self.assertContains(response, url)

    def test_stale_index_entry_is_skipped(self):
        # a result whose post vanished between indexing and hydration
        from games import forum as forum_module

        class FakeResult:
            pk = "999999"

        with mock.patch.object(
            forum_module.HaystackSearchForm,
            "search",
            return_value=[FakeResult()],
        ):
            response = self.search(q="anything")
        self.assertContains(response, "Your search has returned")
        self.assertContains(response, "<b>0</b>", html=False)

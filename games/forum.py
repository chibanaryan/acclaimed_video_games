"""
django-machina forum integration.

Provides the canonical forum structure (Site Feedback + Publications),
default permission grants, and the sync that maintains the consolidated
"Publication reputation scores" topic, whose first post is a table of
every publication's score so they can be compared directly.

Idempotent entry points:
- ensure_forum_structure()
- ensure_anonymous_read_permissions()
- ensure_forum_moderators_group()
- sync_publication_scores_topic()

Run `python manage.py setup_forum` to apply all of them at once.
"""

import logging

from django.contrib.auth.models import Group
from haystack import views as haystack_views
from haystack.forms import SearchForm as HaystackSearchForm
from machina.core.db.models import get_model
from machina.core.loading import get_class

logger = logging.getLogger(__name__)

MachinaSearchForm = get_class("forum_search.forms", "SearchForm")

Forum = get_model("forum", "Forum")
Topic = get_model("forum_conversation", "Topic")
ForumPost = get_model("forum_conversation", "Post")
ForumPermission = get_model("forum_permission", "ForumPermission")
GroupForumPermission = get_model("forum_permission", "GroupForumPermission")
UserForumPermission = get_model("forum_permission", "UserForumPermission")

SITE_FEEDBACK_FORUM_NAME = "Site Feedback"
PUBLICATIONS_FORUM_NAME = "Publications"
FORUM_MODERATORS_GROUP_NAME = "Forum Moderators"
SYSTEM_POSTER_NAME = "Acclaimed Video Games"
SCORES_TOPIC_SUBJECT = "Publication reputation scores"

# Permissions anonymous visitors get globally (read-only access)
ANONYMOUS_PERMISSIONS = [
    "can_see_forum",
    "can_read_forum",
    "can_download_file",
]


class ForumSearchForm(MachinaSearchForm):
    """
    Forum search form that works with haystack's simple backend.

    machina's stock form narrows results with SearchQuerySet field
    filters (forum__in, topic_subject, poster_name), which the simple
    backend silently ignores - making every search return zero results.
    Our forums are all world-readable (global permission grants), so the
    permission narrowing is redundant; the optional filters are applied
    in Python on the hydrated results instead.
    """

    def search(self):
        if not self.is_valid() or not self.cleaned_data.get("q"):
            return self.no_query_found()

        raw_results = list(HaystackSearchForm.search(self))

        # The simple backend stores no index fields, but machina's search
        # template reads them (forum_slug, topic_subject, poster_name...).
        # Hydrate everything from the database in one query.
        posts = ForumPost.objects.filter(
            pk__in=[r.pk for r in raw_results]
        ).select_related("topic__forum", "poster")
        posts_by_pk = {str(post.pk): post for post in posts}

        results = []
        for result in raw_results:
            post = posts_by_pk.get(str(result.pk))
            if post is None:
                continue
            result._object = post
            result.forum = post.topic.forum_id
            result.forum_slug = post.topic.forum.slug
            result.topic = post.topic_id
            result.topic_slug = post.topic.slug
            result.topic_subject = post.topic.subject
            result.poster = post.poster_id
            result.poster_name = (
                post.poster.username if post.poster else post.username or ""
            )
            result.created = post.created
            result.text = post.content.raw
            results.append(result)

        query = self.cleaned_data["q"].lower()
        if self.cleaned_data.get("search_topics"):
            results = [r for r in results if query in r.topic_subject.lower()]

        poster_name = self.cleaned_data.get("search_poster_name")
        if poster_name:
            poster_name = poster_name.lower()
            results = [r for r in results if poster_name in r.poster_name.lower()]

        selected_forums = self.cleaned_data.get("search_forums")
        if selected_forums:
            forum_ids = {int(pk) for pk in selected_forums}
            results = [r for r in results if r.forum in forum_ids]

        return results


class ForumSearchView(haystack_views.SearchView):
    """
    machina's stock view is a FacetedSearchView, which requires a
    SearchQuerySet for facet_counts(); ForumSearchForm returns a plain
    list (machina's search template renders no facets anyway).
    """

    template = "forum_search/search.html"

    def build_form(self, form_kwargs=None):
        return super().build_form(form_kwargs={"user": self.request.user})


def ensure_forum_structure():
    """Create the two root forums if missing. Returns {key: Forum}."""
    site_feedback, _ = Forum.objects.get_or_create(
        name=SITE_FEEDBACK_FORUM_NAME,
        defaults={
            "type": Forum.FORUM_POST,
            "description": (
                "Feedback, suggestions and bug reports for the "
                "Acclaimed Video Games site."
            ),
        },
    )
    publications, _ = Forum.objects.get_or_create(
        name=PUBLICATIONS_FORUM_NAME,
        defaults={
            "type": Forum.FORUM_POST,
            "description": (
                "Discussion of the publications whose lists feed our "
                "rankings, including their reputation scores."
            ),
        },
    )
    return {"site_feedback": site_feedback, "publications": publications}


def ensure_anonymous_read_permissions():
    """Grant anonymous visitors global read access to all forums."""
    for codename in ANONYMOUS_PERMISSIONS:
        try:
            permission = ForumPermission.objects.get(codename=codename)
        except ForumPermission.DoesNotExist:
            # machina creates its permissions in a post_migrate hook;
            # on a brand new database run `setup_forum` after migrating
            logger.warning("Forum permission %s does not exist yet", codename)
            continue
        UserForumPermission.objects.get_or_create(
            permission=permission,
            forum=None,
            anonymous_user=True,
            authenticated_user=False,
            user=None,
            defaults={"has_perm": True},
        )


def ensure_forum_moderators_group():
    """
    Create the Forum Moderators group with every machina permission
    granted globally. Staff users are added to it automatically via a
    post_save signal on User (see games/signals.py).
    """
    group, _ = Group.objects.get_or_create(name=FORUM_MODERATORS_GROUP_NAME)
    for permission in ForumPermission.objects.all():
        GroupForumPermission.objects.get_or_create(
            group=group,
            permission=permission,
            forum=None,
            defaults={"has_perm": True},
        )
    return group


def _scores_post_content():
    """Markdown body of the consolidated reputation scores topic."""
    from django.db.models import Count

    from games.models import Publication

    publications = list(
        Publication.objects.annotate(num_lists=Count("lists")).order_by("name")
    )
    scored = sorted(
        (p for p in publications if p.reputation_score is not None),
        key=lambda p: (-p.reputation_score, p.name.lower()),
    )
    unscored = [p for p in publications if p.reputation_score is None]

    lines = [
        "Reputation scores for the publications whose lists feed our "
        "rankings, maintained by the site staff and ranked here so they "
        "can be compared directly.",
        "",
        "Use this topic to discuss the scores: which publications deserve "
        "more or less weight, and why.",
        "",
        "| Rank | Publication | Score | Tracked lists |",
        "| ---: | --- | ---: | ---: |",
    ]
    for rank, publication in enumerate(scored, 1):
        lines.append(
            f"| {rank} | {publication.name} "
            f"| {publication.reputation_score} | {publication.num_lists} |"
        )
    for publication in unscored:
        lines.append(
            f"| — | {publication.name} | not yet rated " f"| {publication.num_lists} |"
        )
    return "\n".join(lines)


def sync_publication_scores_topic():
    """
    Ensure the Publications forum has a single sticky topic listing all
    publication reputation scores, and that its first post reflects the
    current data. Safe to call repeatedly.
    """
    forum = ensure_forum_structure()["publications"]
    content = _scores_post_content()

    topic = Topic.objects.filter(forum=forum, subject=SCORES_TOPIC_SUBJECT).first()
    if topic is None:
        topic = Topic.objects.create(
            forum=forum,
            subject=SCORES_TOPIC_SUBJECT,
            type=Topic.TOPIC_STICKY,
            status=Topic.TOPIC_UNLOCKED,
            approved=True,
        )
        ForumPost.objects.create(
            topic=topic,
            subject=SCORES_TOPIC_SUBJECT,
            content=content,
            username=SYSTEM_POSTER_NAME,
            approved=True,
        )
        return topic

    first_post = topic.first_post
    if first_post and first_post.content.raw != content:
        first_post.content = content
        first_post.save()
    return topic

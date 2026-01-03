"""Tests for the Article (Blog) feature."""

from django.test import TestCase
from django.urls import reverse

from games.models import Article, User


class ArticleModelTest(TestCase):
    """Test Article model behavior."""

    def test_auto_publish_date(self):
        """Test that published_at is set automatically on first publish."""
        article = Article.objects.create(
            title="Test Article",
            slug="test-article",
            content="Test content",
            status=Article.Status.DRAFT,
        )
        self.assertIsNone(article.published_at)

        article.status = Article.Status.PUBLISHED
        article.save()
        self.assertIsNotNone(article.published_at)

    def test_published_at_not_overwritten(self):
        """Test that published_at is not overwritten on subsequent saves."""
        article = Article.objects.create(
            title="Test Article",
            slug="test-article",
            content="Test content",
            status=Article.Status.PUBLISHED,
        )
        original_published_at = article.published_at

        # Make another save
        article.title = "Updated Title"
        article.save()

        article.refresh_from_db()
        self.assertEqual(article.published_at, original_published_at)

    def test_content_rendered(self):
        """Test markdown rendering."""
        article = Article.objects.create(
            title="Test",
            slug="test",
            content="**Bold** and *italic*",
        )
        rendered = article.content_rendered
        self.assertIn("<strong>Bold</strong>", rendered)
        self.assertIn("<em>italic</em>", rendered)

    def test_content_rendered_with_code(self):
        """Test markdown rendering with fenced code blocks."""
        article = Article.objects.create(
            title="Test",
            slug="test",
            content="```python\nprint('hello')\n```",
        )
        rendered = article.content_rendered
        self.assertIn("<code", rendered)

    def test_get_absolute_url(self):
        """Test that get_absolute_url returns correct URL."""
        article = Article.objects.create(
            title="Test",
            slug="my-test-article",
            content="Content",
        )
        self.assertEqual(article.get_absolute_url(), "/blog/my-test-article/")

    def test_str_representation(self):
        """Test string representation of Article."""
        article = Article(title="My Article Title")
        self.assertEqual(str(article), "My Article Title")

    def test_ordering(self):
        """Test that articles are ordered by published_at descending."""
        article1 = Article.objects.create(
            title="First",
            slug="first",
            content="Content",
            status=Article.Status.PUBLISHED,
        )
        # Small delay to ensure different published_at times
        article2 = Article.objects.create(
            title="Second",
            slug="second",
            content="Content",
            status=Article.Status.PUBLISHED,
        )

        articles = list(Article.objects.all())
        # Second article should come first (more recent)
        self.assertEqual(articles[0], article2)
        self.assertEqual(articles[1], article1)


class ArticleViewTest(TestCase):
    """Test Article views."""

    def setUp(self):
        self.published = Article.objects.create(
            title="Published Article",
            slug="published-article",
            content="Published content",
            excerpt="This is the excerpt",
            status=Article.Status.PUBLISHED,
        )
        self.draft = Article.objects.create(
            title="Draft Article",
            slug="draft-article",
            content="Draft content",
            status=Article.Status.DRAFT,
        )

    def test_article_list_shows_published_only(self):
        """Test that article list only shows published articles."""
        response = self.client.get(reverse("article-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Article")
        self.assertNotContains(response, "Draft Article")

    def test_article_list_template(self):
        """Test that article list uses correct template."""
        response = self.client.get(reverse("article-list"))
        self.assertTemplateUsed(response, "articles/article_list.html")

    def test_article_detail_published(self):
        """Test accessing published article."""
        response = self.client.get(
            reverse("article-detail", kwargs={"slug": "published-article"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Published Article")
        self.assertContains(response, "Published content")

    def test_article_detail_draft_anonymous(self):
        """Test that anonymous users cannot view drafts."""
        response = self.client.get(
            reverse("article-detail", kwargs={"slug": "draft-article"})
        )
        self.assertEqual(response.status_code, 404)

    def test_article_detail_draft_staff(self):
        """Test that staff can preview drafts."""
        User.objects.create_user(
            username="staff",
            email="staff@test.com",
            password="testpass",
            is_staff=True,
        )
        self.client.login(username="staff", password="testpass")
        response = self.client.get(
            reverse("article-detail", kwargs={"slug": "draft-article"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draft Article")
        # Should show draft warning
        self.assertContains(response, "draft")

    def test_article_detail_template(self):
        """Test that article detail uses correct template."""
        response = self.client.get(
            reverse("article-detail", kwargs={"slug": "published-article"})
        )
        self.assertTemplateUsed(response, "articles/article_detail.html")

    def test_article_list_shows_excerpt(self):
        """Test that article list shows excerpt."""
        response = self.client.get(reverse("article-list"))
        self.assertContains(response, "This is the excerpt")

    def test_article_detail_nonexistent(self):
        """Test 404 for nonexistent article."""
        response = self.client.get(
            reverse("article-detail", kwargs={"slug": "nonexistent"})
        )
        self.assertEqual(response.status_code, 404)


class ArticleHTMXTest(TestCase):
    """Test HTMX partial responses for articles."""

    def setUp(self):
        # Create enough articles to test pagination
        for i in range(15):
            Article.objects.create(
                title=f"Article {i}",
                slug=f"article-{i}",
                content=f"Content {i}",
                status=Article.Status.PUBLISHED,
            )

    def test_article_list_htmx_partial(self):
        """Test that HTMX requests get partial template."""
        response = self.client.get(
            reverse("article-list"),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "articles/includes/_article_list_content.html"
        )

    def test_article_list_pagination(self):
        """Test article list pagination."""
        response = self.client.get(reverse("article-list"))
        self.assertEqual(response.status_code, 200)
        # Should show pagination since we have 15 articles and paginate_by=10
        self.assertContains(response, "Page 1 of 2")

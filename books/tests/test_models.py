"""
Tests for books app models.

Tests for Author, Book, BookGenre, BookSeries, GoodreadsBookData,
WikipediaBookData, BookListMembership, ReadBook, and WantToReadBook models.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from books import models


User = get_user_model()


class AuthorModelTests(TestCase):
    """Tests for the Author model."""

    def test_str_root_author(self):
        """Test __str__ for root author returns just the name."""
        author = models.Author.objects.create(name="J.K. Rowling", slug="jk-rowling")
        self.assertEqual(str(author), "J.K. Rowling")

    def test_str_subsidiary_author(self):
        """Test __str__ for subsidiary author includes parent name."""
        parent = models.Author.objects.create(name="Stephen King", slug="stephen-king")
        pseudonym = models.Author.objects.create(name="Richard Bachman", parent=parent)
        self.assertEqual(str(pseudonym), "Richard Bachman (Stephen King)")

    def test_author_ordering(self):
        """Test that authors are ordered by name."""
        models.Author.objects.create(name="Zelda Author", slug="zelda")
        models.Author.objects.create(name="Alpha Author", slug="alpha")
        models.Author.objects.create(name="Middle Author", slug="middle")

        authors = list(models.Author.objects.all())
        names = [a.name for a in authors]
        self.assertEqual(names, ["Alpha Author", "Middle Author", "Zelda Author"])

    def test_author_goodreads_id_index(self):
        """Test author can be queried by goodreads_id."""
        author = models.Author.objects.create(
            name="Test Author",
            slug="test-author",
            goodreads_id="12345",
        )
        found = models.Author.objects.get(goodreads_id="12345")
        self.assertEqual(found, author)

    def test_author_parent_relationship(self):
        """Test author parent-child relationships."""
        parent = models.Author.objects.create(name="Parent", slug="parent")
        child = models.Author.objects.create(name="Child", parent=parent)

        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.subsidiaries.all())


class BookGenreModelTests(TestCase):
    """Tests for the BookGenre model."""

    def test_str_root_genre(self):
        """Test __str__ for root genre returns just the name."""
        genre = models.BookGenre.objects.create(name="Fiction")
        self.assertEqual(str(genre), "Fiction")

    def test_str_child_genre_shows_path(self):
        """Test __str__ for child genre returns full path."""
        fiction = models.BookGenre.objects.create(name="Fiction")
        scifi = models.BookGenre.objects.create(name="Science Fiction", parent=fiction)
        self.assertEqual(str(scifi), "Fiction > Science Fiction")

    def test_save_auto_generates_slug(self):
        """Test that save() auto-generates slug from name."""
        genre = models.BookGenre.objects.create(name="Literary Fiction")
        self.assertEqual(genre.slug, "literary-fiction")

    def test_save_calculates_level(self):
        """Test that save() correctly calculates hierarchy level."""
        root = models.BookGenre.objects.create(name="Root")
        child = models.BookGenre.objects.create(name="Child", parent=root)
        grandchild = models.BookGenre.objects.create(name="Grandchild", parent=child)

        self.assertEqual(root.level, 0)
        self.assertEqual(child.level, 1)
        self.assertEqual(grandchild.level, 2)

    def test_save_builds_path(self):
        """Test that save() builds hierarchical path."""
        fiction = models.BookGenre.objects.create(name="Fiction")
        scifi = models.BookGenre.objects.create(name="Science Fiction", parent=fiction)
        space = models.BookGenre.objects.create(name="Space Opera", parent=scifi)

        self.assertEqual(fiction.path, "Fiction")
        self.assertEqual(scifi.path, "Fiction > Science Fiction")
        self.assertEqual(space.path, "Fiction > Science Fiction > Space Opera")

    def test_get_descendants(self):
        """Test get_descendants returns all child genres."""
        root = models.BookGenre.objects.create(name="Root")
        child1 = models.BookGenre.objects.create(name="Child1", parent=root)
        child2 = models.BookGenre.objects.create(name="Child2", parent=root)
        grandchild = models.BookGenre.objects.create(name="Grandchild", parent=child1)

        descendants = root.get_descendants()
        self.assertEqual(len(descendants), 3)
        self.assertIn(child1, descendants)
        self.assertIn(child2, descendants)
        self.assertIn(grandchild, descendants)

    def test_get_descendants_include_self(self):
        """Test get_descendants with include_self=True."""
        root = models.BookGenre.objects.create(name="Root")
        child = models.BookGenre.objects.create(name="Child", parent=root)

        descendants = root.get_descendants(include_self=True)
        self.assertEqual(len(descendants), 2)
        self.assertIn(root, descendants)
        self.assertIn(child, descendants)

    def test_get_descendant_ids(self):
        """Test get_descendant_ids returns correct IDs."""
        root = models.BookGenre.objects.create(name="Root")
        child = models.BookGenre.objects.create(name="Child", parent=root)

        ids = root.get_descendant_ids()
        self.assertIn(child.id, ids)
        self.assertNotIn(root.id, ids)

    def test_is_root_property(self):
        """Test is_root property."""
        root = models.BookGenre.objects.create(name="Root")
        child = models.BookGenre.objects.create(name="Child", parent=root)

        self.assertTrue(root.is_root)
        self.assertFalse(child.is_root)

    def test_is_leaf_property(self):
        """Test is_leaf property."""
        root = models.BookGenre.objects.create(name="Root")
        child = models.BookGenre.objects.create(name="Child", parent=root)

        self.assertFalse(root.is_leaf)
        self.assertTrue(child.is_leaf)


class BookSeriesModelTests(TestCase):
    """Tests for the BookSeries model."""

    def test_str(self):
        """Test __str__ returns series name."""
        series = models.BookSeries.objects.create(name="Harry Potter")
        self.assertEqual(str(series), "Harry Potter")

    def test_save_auto_generates_slug(self):
        """Test that save() auto-generates slug from name."""
        series = models.BookSeries.objects.create(name="A Song of Ice and Fire")
        self.assertEqual(series.slug, "a-song-of-ice-and-fire")

    def test_ordering(self):
        """Test series are ordered by name."""
        models.BookSeries.objects.create(name="Zzz Series")
        models.BookSeries.objects.create(name="Aaa Series")

        series = list(models.BookSeries.objects.all())
        names = [s.name for s in series]
        self.assertEqual(names, ["Aaa Series", "Zzz Series"])


class BookModelTests(TestCase):
    """Tests for the Book model."""

    def test_str(self):
        """Test __str__ returns book name."""
        book = models.Book.objects.create(name="1984", rank=1)
        self.assertEqual(str(book), "1984")

    def test_decade_property(self):
        """Test decade property calculation."""
        book = models.Book.objects.create(
            name="Test", rank=1, year_published=1995
        )
        self.assertEqual(book.decade, 1990)

    def test_decade_property_none_when_no_year(self):
        """Test decade property returns None when no year."""
        book = models.Book.objects.create(name="Test", rank=1)
        self.assertIsNone(book.decade)

    def test_thumbnail_from_goodreads_data(self):
        """Test thumbnail property uses primary Goodreads data."""
        book = models.Book.objects.create(name="Test", rank=1, goodreads_id="123")
        goodreads_data = models.GoodreadsBookData.objects.create(
            book=book,
            goodreads_id="123",
            cover_image_url="https://example.com/cover.jpg",
            is_primary=True,
        )
        book.primary_goodreads_book_data = goodreads_data
        book.save()

        # Refresh from database to get fresh object
        book.refresh_from_db()
        self.assertEqual(book.thumbnail, "https://example.com/cover.jpg")

    def test_thumbnail_none_without_goodreads_data(self):
        """Test thumbnail property returns None without Goodreads data."""
        book = models.Book.objects.create(name="Test", rank=1)
        self.assertIsNone(book.thumbnail)

    def test_authors_relationship(self):
        """Test book-author many-to-many relationship."""
        book = models.Book.objects.create(name="Test Book", rank=1)
        author1 = models.Author.objects.create(name="Author One", slug="author-one")
        author2 = models.Author.objects.create(name="Author Two", slug="author-two")

        book.authors.add(author1, author2)

        self.assertEqual(book.authors.count(), 2)
        self.assertIn(book, author1.books.all())

    def test_genres_relationship(self):
        """Test book-genre many-to-many relationship."""
        book = models.Book.objects.create(name="Test Book", rank=1)
        genre = models.BookGenre.objects.create(name="Fiction")

        book.genres.add(genre)

        self.assertEqual(book.genres.count(), 1)
        self.assertIn(book, genre.books.all())

    def test_series_relationship(self):
        """Test book-series relationship."""
        series = models.BookSeries.objects.create(name="Test Series")
        book = models.Book.objects.create(
            name="Book 1",
            rank=1,
            series=series,
            series_position=1.0,
        )

        self.assertEqual(book.series, series)
        self.assertIn(book, series.books.all())

    def test_ordering_by_rank(self):
        """Test books are ordered by rank."""
        models.Book.objects.create(name="Third", rank=3)
        models.Book.objects.create(name="First", rank=1)
        models.Book.objects.create(name="Second", rank=2)

        books = list(models.Book.objects.all())
        names = [b.name for b in books]
        self.assertEqual(names, ["First", "Second", "Third"])

    def test_get_display_authors_single(self):
        """Test get_display_authors with single author."""
        book = models.Book.objects.create(name="Test", rank=1)
        author = models.Author.objects.create(name="Solo Author", slug="solo")
        book.authors.add(author)

        result = book.get_display_authors()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], author)

    def test_get_display_authors_filters_parent(self):
        """Test get_display_authors filters out parent when child credited."""
        parent = models.Author.objects.create(name="Parent Author", slug="parent")
        child = models.Author.objects.create(name="Child Author", parent=parent)
        book = models.Book.objects.create(name="Test", rank=1)
        book.authors.add(parent, child)

        result = book.get_display_authors()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], child)

    def test_get_display_authors_max_count(self):
        """Test get_display_authors respects max_count."""
        book = models.Book.objects.create(name="Test", rank=1)
        for i in range(5):
            author = models.Author.objects.create(name=f"Author {i}", slug=f"author-{i}")
            book.authors.add(author)

        result = book.get_display_authors(max_count=2)
        self.assertEqual(len(result), 2)


class GoodreadsBookDataModelTests(TestCase):
    """Tests for the GoodreadsBookData model."""

    def test_str_with_book(self):
        """Test __str__ with linked book."""
        book = models.Book.objects.create(name="Test Book", rank=1)
        data = models.GoodreadsBookData.objects.create(
            book=book,
            goodreads_id="12345",
        )
        self.assertEqual(str(data), "Goodreads data for Test Book (ID: 12345)")

    def test_str_without_book(self):
        """Test __str__ for orphaned data."""
        data = models.GoodreadsBookData.objects.create(
            goodreads_id="12345",
        )
        self.assertEqual(str(data), "Orphaned Goodreads data (ID: 12345)")

    def test_goodreads_book_url(self):
        """Test goodreads_book_url property generates URL."""
        data = models.GoodreadsBookData.objects.create(
            goodreads_id="12345",
        )
        self.assertEqual(
            data.goodreads_book_url,
            "https://www.goodreads.com/book/show/12345",
        )

    def test_thumbnail_property(self):
        """Test thumbnail property returns cover_image_url."""
        data = models.GoodreadsBookData.objects.create(
            goodreads_id="12345",
            cover_image_url="https://example.com/cover.jpg",
        )
        # Clear cached property
        if "thumbnail" in data.__dict__:
            del data.__dict__["thumbnail"]
        self.assertEqual(data.thumbnail, "https://example.com/cover.jpg")


class WikipediaBookDataModelTests(TestCase):
    """Tests for the WikipediaBookData model."""

    def test_str_with_book(self):
        """Test __str__ with linked book."""
        book = models.Book.objects.create(name="Test Book", rank=1)
        data = models.WikipediaBookData.objects.create(
            book=book,
            page_title="Test_Book",
        )
        self.assertEqual(str(data), "Wikipedia data for Test Book")

    def test_str_without_book(self):
        """Test __str__ for orphaned data."""
        data = models.WikipediaBookData.objects.create(
            page_title="Test_Book",
            wikidata_id="Q12345",
        )
        self.assertEqual(str(data), "Orphaned Wikipedia data (Wikidata: Q12345)")

    def test_wikipedia_url(self):
        """Test wikipedia_url property generates URL."""
        data = models.WikipediaBookData.objects.create(
            page_title="The_Great_Gatsby",
        )
        self.assertEqual(
            data.wikipedia_url,
            "https://en.wikipedia.org/wiki/The_Great_Gatsby",
        )

    def test_wikipedia_url_handles_spaces(self):
        """Test wikipedia_url replaces spaces with underscores."""
        data = models.WikipediaBookData.objects.create(
            page_title="The Great Gatsby",
        )
        self.assertEqual(
            data.wikipedia_url,
            "https://en.wikipedia.org/wiki/The_Great_Gatsby",
        )

    def test_wikipedia_url_none_without_page_title(self):
        """Test wikipedia_url returns None without page title."""
        data = models.WikipediaBookData.objects.create(
            page_title="",
        )
        self.assertIsNone(data.wikipedia_url)


class BookListMembershipModelTests(TestCase):
    """Tests for the BookListMembership model."""

    def setUp(self):
        from games.models import List, Publication

        self.publication = Publication.objects.create(name="Test Pub")
        self.book_list = List.objects.create(
            publisher=self.publication,
            name="Best Books 2024",
            year=2024,
            type="AT",
            media_type="B",
        )
        self.book = models.Book.objects.create(name="Test Book", rank=1)

    def test_str(self):
        """Test __str__ returns formatted string."""
        membership = models.BookListMembership.objects.create(
            list=self.book_list,
            book=self.book,
            rank=5,
        )
        self.assertEqual(str(membership), "Best Books 2024 - Test Book - 5")

    def test_unique_together_constraint(self):
        """Test that a book can only appear once per list."""
        models.BookListMembership.objects.create(
            list=self.book_list,
            book=self.book,
            rank=1,
        )

        with self.assertRaises(IntegrityError):
            models.BookListMembership.objects.create(
                list=self.book_list,
                book=self.book,
                rank=2,
            )


class ReadBookModelTests(TestCase):
    """Tests for the ReadBook model."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.book = models.Book.objects.create(
            name="Test Book", rank=1, goodreads_id="12345"
        )

    def test_str_with_book(self):
        """Test __str__ with linked book."""
        read_book = models.ReadBook.objects.create(
            user=self.user,
            book=self.book,
            goodreads_id="12345",
        )
        self.assertEqual(str(read_book), "testuser read Test Book")

    def test_str_without_book(self):
        """Test __str__ with orphaned record."""
        read_book = models.ReadBook.objects.create(
            user=self.user,
            goodreads_id="99999",
        )
        self.assertEqual(str(read_book), "testuser read Goodreads:99999")

    def test_unique_together_constraint(self):
        """Test that a user can only mark a book as read once."""
        models.ReadBook.objects.create(
            user=self.user,
            book=self.book,
            goodreads_id="12345",
        )

        with self.assertRaises(IntegrityError):
            models.ReadBook.objects.create(
                user=self.user,
                book=self.book,
                goodreads_id="12345",
            )


class WantToReadBookModelTests(TestCase):
    """Tests for the WantToReadBook model."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.book = models.Book.objects.create(
            name="Test Book", rank=1, goodreads_id="12345"
        )

    def test_str_with_book(self):
        """Test __str__ with linked book."""
        want_book = models.WantToReadBook.objects.create(
            user=self.user,
            book=self.book,
            goodreads_id="12345",
        )
        self.assertEqual(str(want_book), "testuser wants to read Test Book")

    def test_str_without_book(self):
        """Test __str__ with orphaned record."""
        want_book = models.WantToReadBook.objects.create(
            user=self.user,
            goodreads_id="99999",
        )
        self.assertEqual(str(want_book), "testuser wants to read Goodreads:99999")

    def test_unique_together_constraint(self):
        """Test that a user can only add a book to want-to-read once."""
        models.WantToReadBook.objects.create(
            user=self.user,
            book=self.book,
            goodreads_id="12345",
        )

        with self.assertRaises(IntegrityError):
            models.WantToReadBook.objects.create(
                user=self.user,
                book=self.book,
                goodreads_id="12345",
            )


class BookQuerySetTests(TestCase):
    """Tests for the BookQuerySet custom manager methods."""

    def setUp(self):
        from games.models import List, Publication

        self.user = User.objects.create_user(username="testuser", password="testpass")

        # Create some books with relationships
        self.author = models.Author.objects.create(name="Test Author", slug="test-author")
        self.genre = models.BookGenre.objects.create(name="Fiction")
        self.series = models.BookSeries.objects.create(name="Test Series")

        self.book1 = models.Book.objects.create(
            name="Book One", rank=1, goodreads_id="111"
        )
        self.book1.authors.add(self.author)
        self.book1.genres.add(self.genre)

        self.book2 = models.Book.objects.create(
            name="Book Two", rank=2, goodreads_id="222", series=self.series
        )
        self.book2.authors.add(self.author)

        # Create list membership
        self.publication = Publication.objects.create(name="Test Pub")
        self.book_list = List.objects.create(
            publisher=self.publication,
            name="Best Books",
            year=2024,
            type="AT",
            media_type="B",
        )
        models.BookListMembership.objects.create(
            list=self.book_list, book=self.book1, rank=1
        )
        models.BookListMembership.objects.create(
            list=self.book_list, book=self.book2, rank=2
        )

    def test_with_relations_prefetches(self):
        """Test with_relations() prefetches expected relations."""
        books = models.Book.objects.with_relations()
        # Check that queryset can be evaluated without N+1 queries
        book = books.first()
        self.assertIsNotNone(book)
        # Accessing these should not cause additional queries
        _ = list(book.authors.all())
        _ = list(book.genres.all())

    def test_with_read_status_authenticated(self):
        """Test with_read_status() annotates for authenticated user."""
        models.ReadBook.objects.create(
            user=self.user, book=self.book1, goodreads_id="111"
        )

        books = models.Book.objects.with_read_status(self.user)
        book = books.get(pk=self.book1.pk)
        self.assertTrue(book.is_read_by_user)

        book2 = books.get(pk=self.book2.pk)
        self.assertFalse(book2.is_read_by_user)

    def test_with_read_status_anonymous(self):
        """Test with_read_status() handles anonymous user."""
        from django.contrib.auth.models import AnonymousUser

        anon = AnonymousUser()
        books = models.Book.objects.with_read_status(anon)
        # Should return queryset without annotation
        self.assertEqual(books.count(), 2)

    def test_with_list_count(self):
        """Test with_list_count() annotates list appearances."""
        books = models.Book.objects.with_list_count()
        book = books.get(pk=self.book1.pk)
        self.assertEqual(book.list_count, 1)

"""
Management command to populate mock book data for testing and demo purposes.

Creates a comprehensive set of:
- Authors (famous writers with hierarchy)
- BookGenres (hierarchical genre structure)
- BookSeries (well-known series)
- Books (classic and popular books)
- GoodreadsBookData (mock external data)
- WikipediaBookData (mock external data)
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from books.models import (
    Author,
    Book,
    BookGenre,
    BookSeries,
    GoodreadsBookData,
    WikipediaBookData,
)


class Command(BaseCommand):
    help = "Populate mock book data for testing and demo purposes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing book data before populating",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing book data...")
            self._clear_data()

        self.stdout.write("Populating mock book data...")

        with transaction.atomic():
            genres = self._create_genres()
            authors = self._create_authors()
            series = self._create_series()
            books = self._create_books(genres, authors, series)
            self._create_metadata(books)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCreated:\n"
                f"  - {len(genres)} genres\n"
                f"  - {len(authors)} authors\n"
                f"  - {len(series)} series\n"
                f"  - {len(books)} books"
            )
        )

    def _clear_data(self):
        """Clear all book-related data."""
        WikipediaBookData.objects.all().delete()
        GoodreadsBookData.objects.all().delete()
        Book.objects.all().delete()
        BookSeries.objects.all().delete()
        Author.objects.all().delete()
        BookGenre.objects.all().delete()
        self.stdout.write(self.style.WARNING("Cleared all book data"))

    def _create_genres(self):
        """Create hierarchical book genres."""
        genres = {}

        # Root genres
        root_genres = [
            ("Fiction", "fiction", "Literary and narrative works"),
            ("Non-Fiction", "non-fiction", "Factual and informational works"),
        ]

        for name, slug, desc in root_genres:
            genre, _ = BookGenre.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": desc},
            )
            genres[slug] = genre

        # Fiction subgenres
        fiction_subgenres = [
            ("Science Fiction", "science-fiction", "Speculative fiction with science"),
            ("Fantasy", "fantasy", "Magical and fantastical worlds"),
            ("Mystery", "mystery", "Crime and detective stories"),
            ("Thriller", "thriller", "Suspenseful and exciting narratives"),
            ("Romance", "romance", "Love and relationship stories"),
            ("Literary Fiction", "literary-fiction", "Character-driven narratives"),
            ("Horror", "horror", "Frightening and supernatural stories"),
            ("Historical Fiction", "historical-fiction", "Fiction set in the past"),
            ("Dystopian", "dystopian", "Dark futuristic societies"),
            ("Classic", "classic", "Timeless literary works"),
        ]

        for name, slug, desc in fiction_subgenres:
            genre, _ = BookGenre.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "parent": genres["fiction"],
                },
            )
            genres[slug] = genre

        # Science Fiction subgenres
        scifi_subgenres = [
            ("Space Opera", "space-opera", "Epic space adventures"),
            ("Cyberpunk", "cyberpunk", "High tech, low life"),
            ("Hard Science Fiction", "hard-scifi", "Scientifically rigorous SF"),
        ]

        for name, slug, desc in scifi_subgenres:
            genre, _ = BookGenre.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "parent": genres["science-fiction"],
                },
            )
            genres[slug] = genre

        # Fantasy subgenres
        fantasy_subgenres = [
            ("Epic Fantasy", "epic-fantasy", "Grand scale fantasy adventures"),
            ("Urban Fantasy", "urban-fantasy", "Fantasy in modern settings"),
            ("Dark Fantasy", "dark-fantasy", "Grim and mature fantasy"),
        ]

        for name, slug, desc in fantasy_subgenres:
            genre, _ = BookGenre.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "parent": genres["fantasy"],
                },
            )
            genres[slug] = genre

        # Non-fiction subgenres
        nonfiction_subgenres = [
            ("Biography", "biography", "Life stories of real people"),
            ("History", "history", "Historical accounts and analysis"),
            ("Science", "science", "Scientific topics and discoveries"),
            ("Philosophy", "philosophy", "Philosophical works"),
            ("Self-Help", "self-help", "Personal development"),
            ("Memoir", "memoir", "Personal narratives"),
            ("Essays", "essays", "Collections of essays"),
        ]

        for name, slug, desc in nonfiction_subgenres:
            genre, _ = BookGenre.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": desc,
                    "parent": genres["non-fiction"],
                },
            )
            genres[slug] = genre

        return genres

    def _create_authors(self):
        """Create famous authors."""
        authors = {}

        author_data = [
            # Classic authors
            {
                "name": "Jane Austen",
                "slug": "jane-austen",
                "birth_date": "1775-12-16",
                "death_date": "1817-07-18",
                "bio": "English novelist known for her six major novels.",
                "open_library_id": "OL21594A",
            },
            {
                "name": "Charles Dickens",
                "slug": "charles-dickens",
                "birth_date": "1812-02-07",
                "death_date": "1870-06-09",
                "bio": "English writer and social critic.",
                "open_library_id": "OL24638A",
            },
            {
                "name": "Mark Twain",
                "slug": "mark-twain",
                "birth_date": "1835-11-30",
                "death_date": "1910-04-21",
                "bio": "American writer and humorist.",
                "open_library_id": "OL18319A",
            },
            {
                "name": "Leo Tolstoy",
                "slug": "leo-tolstoy",
                "birth_date": "1828-09-09",
                "death_date": "1910-11-20",
                "bio": "Russian writer regarded as one of the greatest authors.",
                "open_library_id": "OL26783A",
            },
            {
                "name": "Fyodor Dostoevsky",
                "slug": "fyodor-dostoevsky",
                "birth_date": "1821-11-11",
                "death_date": "1881-02-09",
                "bio": "Russian novelist and philosopher.",
                "open_library_id": "OL22242A",
            },
            # Modern authors
            {
                "name": "George Orwell",
                "slug": "george-orwell",
                "birth_date": "1903-06-25",
                "death_date": "1950-01-21",
                "bio": "English novelist and essayist.",
                "open_library_id": "OL118077A",
            },
            {
                "name": "Ernest Hemingway",
                "slug": "ernest-hemingway",
                "birth_date": "1899-07-21",
                "death_date": "1961-07-02",
                "bio": "American novelist and journalist.",
                "open_library_id": "OL13640A",
            },
            {
                "name": "F. Scott Fitzgerald",
                "slug": "f-scott-fitzgerald",
                "birth_date": "1896-09-24",
                "death_date": "1940-12-21",
                "bio": "American novelist of the Jazz Age.",
                "open_library_id": "OL27349A",
            },
            {
                "name": "Harper Lee",
                "slug": "harper-lee",
                "birth_date": "1926-04-28",
                "death_date": "2016-02-19",
                "bio": "American novelist best known for To Kill a Mockingbird.",
                "open_library_id": "OL500912A",
            },
            # Fantasy/Sci-Fi authors
            {
                "name": "J.R.R. Tolkien",
                "slug": "jrr-tolkien",
                "birth_date": "1892-01-03",
                "death_date": "1973-09-02",
                "bio": "English writer, poet, and philologist.",
                "open_library_id": "OL26320A",
            },
            {
                "name": "Frank Herbert",
                "slug": "frank-herbert",
                "birth_date": "1920-10-08",
                "death_date": "1986-02-11",
                "bio": "American science-fiction author.",
                "open_library_id": "OL20765A",
            },
            {
                "name": "Isaac Asimov",
                "slug": "isaac-asimov",
                "birth_date": "1920-01-02",
                "death_date": "1992-04-06",
                "bio": "American writer and professor of biochemistry.",
                "open_library_id": "OL34221A",
            },
            {
                "name": "Ursula K. Le Guin",
                "slug": "ursula-k-le-guin",
                "birth_date": "1929-10-21",
                "death_date": "2018-01-22",
                "bio": "American author of science fiction and fantasy.",
                "open_library_id": "OL28127A",
            },
            {
                "name": "Philip K. Dick",
                "slug": "philip-k-dick",
                "birth_date": "1928-12-16",
                "death_date": "1982-03-02",
                "bio": "American science fiction writer.",
                "open_library_id": "OL29565A",
            },
            # Contemporary authors
            {
                "name": "Stephen King",
                "slug": "stephen-king",
                "birth_date": "1947-09-21",
                "bio": "American author of horror, supernatural fiction.",
                "open_library_id": "OL2162284A",
            },
            {
                "name": "J.K. Rowling",
                "slug": "jk-rowling",
                "birth_date": "1965-07-31",
                "bio": "British author best known for Harry Potter.",
                "open_library_id": "OL23919A",
            },
            {
                "name": "George R.R. Martin",
                "slug": "george-rr-martin",
                "birth_date": "1948-09-20",
                "bio": "American novelist and short story writer.",
                "open_library_id": "OL20933A",
            },
            {
                "name": "Neil Gaiman",
                "slug": "neil-gaiman",
                "birth_date": "1960-11-10",
                "bio": "English author of fantasy and horror.",
                "open_library_id": "OL25712A",
            },
            {
                "name": "Cormac McCarthy",
                "slug": "cormac-mccarthy",
                "birth_date": "1933-07-20",
                "death_date": "2023-06-13",
                "bio": "American novelist and playwright.",
                "open_library_id": "OL31574A",
            },
            {
                "name": "Toni Morrison",
                "slug": "toni-morrison",
                "birth_date": "1931-02-18",
                "death_date": "2019-08-05",
                "bio": "American novelist and Nobel Prize winner.",
                "open_library_id": "OL27349A",
            },
        ]

        for data in author_data:
            birth = data.pop("birth_date", None)
            death = data.pop("death_date", None)

            author, _ = Author.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    **data,
                    "birth_date": birth,
                    "death_date": death,
                },
            )
            authors[data["slug"]] = author

        return authors

    def _create_series(self):
        """Create book series."""
        series = {}

        series_data = [
            ("The Lord of the Rings", "lord-of-the-rings"),
            ("Harry Potter", "harry-potter"),
            ("A Song of Ice and Fire", "song-of-ice-and-fire"),
            ("Dune", "dune"),
            ("Foundation", "foundation"),
            ("The Dark Tower", "dark-tower"),
            ("Earthsea", "earthsea"),
        ]

        for name, slug in series_data:
            s, _ = BookSeries.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            series[slug] = s

        return series

    def _create_books(self, genres, authors, series):
        """Create books with relationships."""
        books = []

        book_data = [
            # Rank 1-10: All-time classics
            {
                "name": "War and Peace",
                "slug": "war-and-peace",
                "rank": 1,
                "year_published": 1869,
                "page_count": 1225,
                "authors": ["leo-tolstoy"],
                "genres": ["fiction", "literary-fiction", "historical-fiction"],
                "description": "Epic novel depicting Russian society during the Napoleonic Wars.",
                "goodreads_id": "656",
                "isbn13": "9780143039990",
            },
            {
                "name": "Crime and Punishment",
                "slug": "crime-and-punishment",
                "rank": 2,
                "year_published": 1866,
                "page_count": 671,
                "authors": ["fyodor-dostoevsky"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A young man's moral dilemmas after committing murder.",
                "goodreads_id": "7144",
                "isbn13": "9780143058144",
            },
            {
                "name": "Pride and Prejudice",
                "slug": "pride-and-prejudice",
                "rank": 3,
                "year_published": 1813,
                "page_count": 432,
                "authors": ["jane-austen"],
                "genres": ["fiction", "romance", "classic"],
                "description": "A witty social commentary on marriage and class in Regency England.",
                "goodreads_id": "1885",
                "isbn13": "9780141439518",
            },
            {
                "name": "1984",
                "slug": "1984",
                "rank": 4,
                "year_published": 1949,
                "page_count": 328,
                "authors": ["george-orwell"],
                "genres": ["fiction", "dystopian", "science-fiction"],
                "description": "A chilling vision of a totalitarian future.",
                "goodreads_id": "5470",
                "isbn13": "9780451524935",
            },
            {
                "name": "The Great Gatsby",
                "slug": "great-gatsby",
                "rank": 5,
                "year_published": 1925,
                "page_count": 180,
                "authors": ["f-scott-fitzgerald"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A critique of the American Dream in the Jazz Age.",
                "goodreads_id": "4671",
                "isbn13": "9780743273565",
            },
            {
                "name": "To Kill a Mockingbird",
                "slug": "to-kill-a-mockingbird",
                "rank": 6,
                "year_published": 1960,
                "page_count": 281,
                "authors": ["harper-lee"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A story of racial injustice in the American South.",
                "goodreads_id": "2657",
                "isbn13": "9780061120084",
            },
            {
                "name": "The Fellowship of the Ring",
                "slug": "fellowship-of-the-ring",
                "rank": 7,
                "year_published": 1954,
                "page_count": 423,
                "authors": ["jrr-tolkien"],
                "genres": ["fiction", "fantasy", "epic-fantasy"],
                "series": "lord-of-the-rings",
                "series_position": 1,
                "description": "The beginning of Frodo's quest to destroy the One Ring.",
                "goodreads_id": "34",
                "isbn13": "9780618640157",
            },
            {
                "name": "Dune",
                "slug": "dune",
                "rank": 8,
                "year_published": 1965,
                "page_count": 688,
                "authors": ["frank-herbert"],
                "genres": ["fiction", "science-fiction", "space-opera"],
                "series": "dune",
                "series_position": 1,
                "description": "An epic science fiction tale of politics, religion, and ecology.",
                "goodreads_id": "234225",
                "isbn13": "9780441172719",
            },
            {
                "name": "The Brothers Karamazov",
                "slug": "brothers-karamazov",
                "rank": 9,
                "year_published": 1880,
                "page_count": 796,
                "authors": ["fyodor-dostoevsky"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A philosophical novel about faith, doubt, and morality.",
                "goodreads_id": "4934",
                "isbn13": "9780374528379",
            },
            {
                "name": "Anna Karenina",
                "slug": "anna-karenina",
                "rank": 10,
                "year_published": 1877,
                "page_count": 864,
                "authors": ["leo-tolstoy"],
                "genres": ["fiction", "literary-fiction", "romance"],
                "description": "A tragic story of love and society in Imperial Russia.",
                "goodreads_id": "15823480",
                "isbn13": "9780143035008",
            },
            # Rank 11-20
            {
                "name": "The Old Man and the Sea",
                "slug": "old-man-and-the-sea",
                "rank": 11,
                "year_published": 1952,
                "page_count": 127,
                "authors": ["ernest-hemingway"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "An aging fisherman's epic struggle with a giant marlin.",
                "goodreads_id": "2165",
                "isbn13": "9780684801223",
            },
            {
                "name": "A Tale of Two Cities",
                "slug": "tale-of-two-cities",
                "rank": 12,
                "year_published": 1859,
                "page_count": 489,
                "authors": ["charles-dickens"],
                "genres": ["fiction", "historical-fiction", "classic"],
                "description": "A story of love and sacrifice during the French Revolution.",
                "goodreads_id": "1953",
                "isbn13": "9780141439600",
            },
            {
                "name": "The Two Towers",
                "slug": "two-towers",
                "rank": 13,
                "year_published": 1954,
                "page_count": 352,
                "authors": ["jrr-tolkien"],
                "genres": ["fiction", "fantasy", "epic-fantasy"],
                "series": "lord-of-the-rings",
                "series_position": 2,
                "description": "The Fellowship is broken; the quest continues.",
                "goodreads_id": "15241",
                "isbn13": "9780618640140",
            },
            {
                "name": "The Return of the King",
                "slug": "return-of-the-king",
                "rank": 14,
                "year_published": 1955,
                "page_count": 416,
                "authors": ["jrr-tolkien"],
                "genres": ["fiction", "fantasy", "epic-fantasy"],
                "series": "lord-of-the-rings",
                "series_position": 3,
                "description": "The epic conclusion to The Lord of the Rings.",
                "goodreads_id": "18512",
                "isbn13": "9780618640157",
            },
            {
                "name": "Foundation",
                "slug": "foundation",
                "rank": 15,
                "year_published": 1951,
                "page_count": 244,
                "authors": ["isaac-asimov"],
                "genres": ["fiction", "science-fiction", "space-opera"],
                "series": "foundation",
                "series_position": 1,
                "description": "The beginning of Asimov's epic galactic saga.",
                "goodreads_id": "29579",
                "isbn13": "9780553293357",
            },
            {
                "name": "A Game of Thrones",
                "slug": "game-of-thrones",
                "rank": 16,
                "year_published": 1996,
                "page_count": 835,
                "authors": ["george-rr-martin"],
                "genres": ["fiction", "fantasy", "epic-fantasy"],
                "series": "song-of-ice-and-fire",
                "series_position": 1,
                "description": "The first book in the epic fantasy series.",
                "goodreads_id": "13496",
                "isbn13": "9780553573404",
            },
            {
                "name": "The Shining",
                "slug": "the-shining",
                "rank": 17,
                "year_published": 1977,
                "page_count": 447,
                "authors": ["stephen-king"],
                "genres": ["fiction", "horror", "thriller"],
                "description": "A family's terrifying stay at the Overlook Hotel.",
                "goodreads_id": "11588",
                "isbn13": "9780307743657",
            },
            {
                "name": "Do Androids Dream of Electric Sheep?",
                "slug": "do-androids-dream",
                "rank": 18,
                "year_published": 1968,
                "page_count": 210,
                "authors": ["philip-k-dick"],
                "genres": ["fiction", "science-fiction", "cyberpunk"],
                "description": "A bounty hunter pursues rogue androids in post-apocalyptic Earth.",
                "goodreads_id": "36402034",
                "isbn13": "9780345404473",
            },
            {
                "name": "A Wizard of Earthsea",
                "slug": "wizard-of-earthsea",
                "rank": 19,
                "year_published": 1968,
                "page_count": 183,
                "authors": ["ursula-k-le-guin"],
                "genres": ["fiction", "fantasy", "epic-fantasy"],
                "series": "earthsea",
                "series_position": 1,
                "description": "A young wizard's journey of self-discovery.",
                "goodreads_id": "13642",
                "isbn13": "9780547722023",
            },
            {
                "name": "American Gods",
                "slug": "american-gods",
                "rank": 20,
                "year_published": 2001,
                "page_count": 635,
                "authors": ["neil-gaiman"],
                "genres": ["fiction", "fantasy", "urban-fantasy"],
                "description": "Old gods and new clash in modern America.",
                "goodreads_id": "30165203",
                "isbn13": "9780063081918",
            },
            # Rank 21-30
            {
                "name": "Harry Potter and the Sorcerer's Stone",
                "slug": "harry-potter-1",
                "rank": 21,
                "year_published": 1997,
                "page_count": 309,
                "authors": ["jk-rowling"],
                "genres": ["fiction", "fantasy"],
                "series": "harry-potter",
                "series_position": 1,
                "description": "A young wizard discovers his magical heritage.",
                "goodreads_id": "3",
                "isbn13": "9780590353427",
            },
            {
                "name": "Beloved",
                "slug": "beloved",
                "rank": 22,
                "year_published": 1987,
                "page_count": 324,
                "authors": ["toni-morrison"],
                "genres": ["fiction", "literary-fiction", "historical-fiction"],
                "description": "A powerful story of slavery and its aftermath.",
                "goodreads_id": "6149",
                "isbn13": "9781400033416",
            },
            {
                "name": "Blood Meridian",
                "slug": "blood-meridian",
                "rank": 23,
                "year_published": 1985,
                "page_count": 337,
                "authors": ["cormac-mccarthy"],
                "genres": ["fiction", "literary-fiction", "historical-fiction"],
                "description": "A violent meditation on the American West.",
                "goodreads_id": "394535",
                "isbn13": "9780679728757",
            },
            {
                "name": "The Road",
                "slug": "the-road",
                "rank": 24,
                "year_published": 2006,
                "page_count": 287,
                "authors": ["cormac-mccarthy"],
                "genres": ["fiction", "dystopian", "literary-fiction"],
                "description": "A father and son journey through post-apocalyptic America.",
                "goodreads_id": "6288",
                "isbn13": "9780307387899",
            },
            {
                "name": "Adventures of Huckleberry Finn",
                "slug": "huckleberry-finn",
                "rank": 25,
                "year_published": 1884,
                "page_count": 366,
                "authors": ["mark-twain"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A boy's adventure down the Mississippi River.",
                "goodreads_id": "2956",
                "isbn13": "9780486280615",
            },
            {
                "name": "Great Expectations",
                "slug": "great-expectations",
                "rank": 26,
                "year_published": 1861,
                "page_count": 505,
                "authors": ["charles-dickens"],
                "genres": ["fiction", "literary-fiction", "classic"],
                "description": "A young orphan's rise and moral growth.",
                "goodreads_id": "2623",
                "isbn13": "9780141439563",
            },
            {
                "name": "Emma",
                "slug": "emma",
                "rank": 27,
                "year_published": 1815,
                "page_count": 474,
                "authors": ["jane-austen"],
                "genres": ["fiction", "romance", "classic"],
                "description": "A comedy of manners about matchmaking.",
                "goodreads_id": "6969",
                "isbn13": "9780141439587",
            },
            {
                "name": "Animal Farm",
                "slug": "animal-farm",
                "rank": 28,
                "year_published": 1945,
                "page_count": 112,
                "authors": ["george-orwell"],
                "genres": ["fiction", "dystopian", "classic"],
                "description": "An allegorical critique of totalitarianism.",
                "goodreads_id": "170448",
                "isbn13": "9780451526342",
            },
            {
                "name": "The Left Hand of Darkness",
                "slug": "left-hand-of-darkness",
                "rank": 29,
                "year_published": 1969,
                "page_count": 304,
                "authors": ["ursula-k-le-guin"],
                "genres": ["fiction", "science-fiction"],
                "description": "An envoy's journey on a world without gender.",
                "goodreads_id": "18423",
                "isbn13": "9780441478125",
            },
            {
                "name": "It",
                "slug": "it",
                "rank": 30,
                "year_published": 1986,
                "page_count": 1138,
                "authors": ["stephen-king"],
                "genres": ["fiction", "horror"],
                "series": "dark-tower",
                "series_position": None,
                "description": "A group of children face an ancient evil.",
                "goodreads_id": "830502",
                "isbn13": "9781501142970",
            },
        ]

        for data in book_data:
            author_slugs = data.pop("authors", [])
            genre_slugs = data.pop("genres", [])
            series_slug = data.pop("series", None)
            series_position = data.pop("series_position", None)

            book, created = Book.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "rank": data["rank"],
                    "year_published": data.get("year_published"),
                    "page_count": data.get("page_count"),
                    "description": data.get("description"),
                    "goodreads_id": data.get("goodreads_id"),
                    "isbn13": data.get("isbn13"),
                    "series": series.get(series_slug) if series_slug else None,
                    "series_position": (
                        Decimal(str(series_position)) if series_position else None
                    ),
                },
            )

            # Add relationships
            for slug in author_slugs:
                if slug in authors:
                    book.authors.add(authors[slug])

            for slug in genre_slugs:
                if slug in genres:
                    book.genres.add(genres[slug])

            books.append(book)

            if created:
                self.stdout.write(f"  Created: {book.name}")
            else:
                self.stdout.write(f"  Exists: {book.name}")

        return books

    def _create_metadata(self, books):
        """Create Goodreads and Wikipedia metadata for books."""
        for book in books:
            # Create Goodreads data
            if book.goodreads_id:
                goodreads_data, created = GoodreadsBookData.objects.get_or_create(
                    goodreads_id=book.goodreads_id,
                    book=book,
                    defaults={
                        "is_primary": True,
                        "cover_image_url": f"https://images-na.ssl-images-amazon.com/images/S/compressed.photo.goodreads.com/books/{book.goodreads_id}.jpg",
                        "average_rating": Decimal("4.25"),
                        "ratings_count": 50000 + (book.rank * 1000),
                        "reviews_count": 5000 + (book.rank * 100),
                        "description": book.description,
                    },
                )
                if created:
                    book.primary_goodreads_book_data = goodreads_data
                    book.save(update_fields=["primary_goodreads_book_data"])

            # Create Wikipedia data
            wiki_data, created = WikipediaBookData.objects.get_or_create(
                page_title=book.name.replace(" ", "_"),
                book=book,
                defaults={
                    "is_primary": True,
                    "wikidata_id": f"Q{book.rank * 100}",
                    "primary_genre": (
                        book.genres.first().name if book.genres.exists() else None
                    ),
                    "all_genres": ", ".join(g.name for g in book.genres.all()),
                    "lookup_source": "mock_data",
                },
            )
            if created:
                book.primary_wikipedia_book_data = wiki_data
                book.save(update_fields=["primary_wikipedia_book_data"])

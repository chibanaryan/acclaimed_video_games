from django.core.cache import cache
from django.core.management.base import BaseCommand

from books.models import ReadBook, WantToReadBook
from books.services.goodreads_importer import (
    GoodreadsImportSummary,
    match_goodreads_records,
    parse_goodreads_records,
)


class Command(BaseCommand):
    help = "Relink orphaned Goodreads read/want entries to Book records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            help="Optional Goodreads export CSV to improve matching.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without writing changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        csv_path = options.get("csv")

        orphaned_read = ReadBook.objects.filter(book__isnull=True)
        orphaned_want = WantToReadBook.objects.filter(book__isnull=True)

        orphaned_ids = set(
            orphaned_read.values_list("goodreads_id", flat=True)
        ) | set(orphaned_want.values_list("goodreads_id", flat=True))

        if not orphaned_ids:
            self.stdout.write(self.style.SUCCESS("No orphaned entries found."))
            return

        summary = GoodreadsImportSummary()

        records = {}
        if csv_path:
            try:
                with open(csv_path, "rb") as fh:
                    parsed_records, summary = parse_goodreads_records(fh, summary)
            except FileNotFoundError:
                self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
                return

            for goodreads_id in orphaned_ids:
                record = parsed_records.get(goodreads_id)
                if record:
                    records[goodreads_id] = record
                else:
                    records[goodreads_id] = {
                        "status": "",
                        "title": "",
                        "author": "",
                        "isbn": "",
                        "isbn13": "",
                        "title_key": "",
                        "author_key": "",
                    }
        else:
            for goodreads_id in orphaned_ids:
                records[goodreads_id] = {
                    "status": "",
                    "title": "",
                    "author": "",
                    "isbn": "",
                    "isbn13": "",
                    "title_key": "",
                    "author_key": "",
                }

        matches, summary = match_goodreads_records(
            records,
            summary,
            allow_backfill=True,
        )

        relinked_ids = 0
        relinked_read = 0
        relinked_want = 0
        user_ids = set()

        for goodreads_id in orphaned_ids:
            book = matches.get(goodreads_id)
            if not book:
                continue
            relinked_ids += 1

            read_qs = ReadBook.objects.filter(
                book__isnull=True, goodreads_id=goodreads_id
            )
            want_qs = WantToReadBook.objects.filter(
                book__isnull=True, goodreads_id=goodreads_id
            )

            user_ids.update(read_qs.values_list("user_id", flat=True))
            user_ids.update(want_qs.values_list("user_id", flat=True))

            if dry_run:
                relinked_read += read_qs.count()
                relinked_want += want_qs.count()
            else:
                relinked_read += read_qs.update(book=book)
                relinked_want += want_qs.update(book=book)

        if not dry_run:
            for user_id in user_ids:
                cache.delete(f"read_books_{user_id}")
                cache.delete(f"want_to_read_books_{user_id}")

        self.stdout.write(
            f"Orphaned entries: {orphaned_read.count()} read, "
            f"{orphaned_want.count()} want-to-read"
        )
        self.stdout.write(f"Unique Goodreads IDs: {len(orphaned_ids)}")
        self.stdout.write(
            f"Relinked IDs: {relinked_ids} "
            f"(read rows: {relinked_read}, want rows: {relinked_want})"
        )
        self.stdout.write(
            "Match breakdown: "
            f"goodreads={summary.matched_by_goodreads}, "
            f"isbn={summary.matched_by_isbn}, "
            f"title_author={summary.matched_by_title_author}"
        )
        self.stdout.write(
            "Backfill/conflicts: "
            f"backfilled={summary.goodreads_id_backfilled}, "
            f"conflicts={summary.goodreads_id_conflicts}"
        )
        self.stdout.write(
            "Ambiguous matches: "
            f"isbn={summary.isbn_ambiguous}, "
            f"title_author={summary.title_author_ambiguous}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes written."))
        else:
            self.stdout.write(self.style.SUCCESS("Relink complete."))

"""
Goodreads CSV import service for user shelves.
"""

import csv
from dataclasses import dataclass
from io import TextIOBase, TextIOWrapper
from typing import Dict, Optional, Tuple

from django.core.cache import cache
from django.db import transaction

from books.models import Book, ReadBook, WantToReadBook


READ_SHELVES = {"read"}
WANT_SHELVES = {"to-read", "want-to-read"}
CURRENT_SHELVES = {"currently-reading"}


@dataclass
class GoodreadsImportSummary:
    total_rows: int = 0
    processed_books: int = 0
    duplicate_rows: int = 0
    skipped_no_id: int = 0
    skipped_no_status: int = 0
    matched_by_goodreads: int = 0
    matched_by_isbn: int = 0
    matched_by_title_author: int = 0
    isbn_ambiguous: int = 0
    title_author_ambiguous: int = 0
    goodreads_id_backfilled: int = 0
    goodreads_id_conflicts: int = 0
    read_added: int = 0
    read_existing: int = 0
    want_added: int = 0
    want_existing: int = 0
    removed_from_want: int = 0
    read_overrides_want: int = 0
    linked_books: int = 0
    unmatched_books: int = 0


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace("-", " ").replace("_", " ")


def _normalize_shelf(value: str) -> str:
    return value.strip().lower()


def _normalize_isbn(value: str) -> str:
    if not value:
        return ""
    cleaned = []
    for ch in value.upper():
        if ch.isdigit() or ch == "X":
            cleaned.append(ch)
    return "".join(cleaned)


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def _open_text_file(file_obj):
    if isinstance(file_obj, TextIOBase):
        file_obj.seek(0)
        return file_obj, False
    file_obj.seek(0)
    return TextIOWrapper(file_obj, encoding="utf-8-sig", newline=""), True


def _build_header_map(fieldnames) -> Dict[str, str]:
    return {_normalize_header(name): name for name in fieldnames if name}


def _get_value(row: Dict[str, str], header_map: Dict[str, str], *names) -> str:
    for name in names:
        key = header_map.get(_normalize_header(name))
        if key:
            return (row.get(key) or "").strip()
    return ""


def _split_shelves(value: str) -> Tuple[str, ...]:
    if not value:
        return tuple()
    cleaned = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if " (" in part:
            part = part.split(" (", 1)[0]
        cleaned.append(_normalize_shelf(part))
    return tuple(cleaned)


def _determine_status(row: Dict[str, str], header_map: Dict[str, str]) -> Optional[str]:
    date_read = _get_value(row, header_map, "date read")
    if date_read:
        return "read"

    exclusive_shelf = _normalize_shelf(_get_value(row, header_map, "exclusive shelf"))
    shelves = set(_split_shelves(_get_value(row, header_map, "bookshelves")))
    shelves_with_positions = set(
        _split_shelves(_get_value(row, header_map, "bookshelves with positions"))
    )

    if exclusive_shelf:
        shelves.add(exclusive_shelf)

    shelves |= shelves_with_positions

    if shelves & READ_SHELVES:
        return "read"
    if shelves & WANT_SHELVES:
        return "want"
    if shelves & CURRENT_SHELVES:
        return "want"

    return None


def _merge_record(existing: Dict[str, str], incoming: Dict[str, str]) -> None:
    """Fill missing record fields when duplicates are encountered."""
    for key in ("title", "author", "isbn", "isbn13", "title_key", "author_key"):
        if not existing.get(key) and incoming.get(key):
            existing[key] = incoming[key]


def _build_isbn_map(candidate_isbns, books_queryset):
    isbn_map = {}
    ambiguous = set()
    if not candidate_isbns:
        return isbn_map, ambiguous

    for book in books_queryset:
        for raw in (book.isbn, book.isbn13):
            norm = _normalize_isbn(raw or "")
            if not norm or norm not in candidate_isbns:
                continue
            if norm in ambiguous:
                continue
            existing = isbn_map.get(norm)
            if existing and existing.id != book.id:
                isbn_map.pop(norm, None)
                ambiguous.add(norm)
                continue
            isbn_map[norm] = book
    return isbn_map, ambiguous


def parse_goodreads_records(file_obj, summary: Optional[GoodreadsImportSummary] = None):
    """Parse Goodreads export CSV into a record map keyed by Goodreads ID."""
    if summary is None:
        summary = GoodreadsImportSummary()

    handle, should_detach = _open_text_file(file_obj)
    try:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Missing header row in CSV.")

        header_map = _build_header_map(reader.fieldnames)
        if "book id" not in header_map:
            raise ValueError("Missing required 'Book Id' column in CSV.")

        records: Dict[str, Dict[str, str]] = {}

        for row in reader:
            summary.total_rows += 1
            goodreads_id = _get_value(
                row,
                header_map,
                "book id",
                "goodreads id",
                "book_id",
            )
            if not goodreads_id:
                summary.skipped_no_id += 1
                continue

            status = _determine_status(row, header_map)
            if not status:
                summary.skipped_no_status += 1
                continue

            title = _get_value(row, header_map, "title")
            author = _get_value(row, header_map, "author", "author l-f", "author l f")
            isbn = _normalize_isbn(_get_value(row, header_map, "isbn"))
            isbn13 = _normalize_isbn(_get_value(row, header_map, "isbn13", "isbn 13"))

            record = {
                "status": status,
                "title": title,
                "author": author,
                "isbn": isbn,
                "isbn13": isbn13,
                "title_key": _normalize_text(title),
                "author_key": _normalize_text(author),
            }

            existing = records.get(goodreads_id)
            if existing:
                summary.duplicate_rows += 1
                if existing["status"] == "read":
                    continue
                if status == "read":
                    existing["status"] = "read"
                _merge_record(existing, record)
                continue

            records[goodreads_id] = record
    finally:
        if should_detach:
            try:
                handle.detach()
            except Exception:
                pass
        file_obj.seek(0)

    return records, summary


def match_goodreads_records(
    records: Dict[str, Dict[str, str]],
    summary: Optional[GoodreadsImportSummary] = None,
    allow_backfill: bool = True,
):
    """Resolve Goodreads IDs to Book matches with fallback logic."""
    if summary is None:
        summary = GoodreadsImportSummary()

    if not records:
        return {}, summary

    goodreads_ids = list(records.keys())

    book_map = {
        str(book.goodreads_id): book
        for book in Book.objects.filter(goodreads_id__in=goodreads_ids)
    }

    candidate_isbns = set()
    for record in records.values():
        if record.get("isbn"):
            candidate_isbns.add(record["isbn"])
        if record.get("isbn13"):
            candidate_isbns.add(record["isbn13"])

    isbn_map, ambiguous_isbns = _build_isbn_map(
        candidate_isbns,
        Book.objects.exclude(isbn__isnull=True, isbn13__isnull=True).only(
            "id", "isbn", "isbn13", "goodreads_id", "name"
        ),
    )

    title_author_cache: Dict[Tuple[str, str], Optional[Book]] = {}
    resolved = {}

    for goodreads_id, record in records.items():
        book = book_map.get(goodreads_id)
        match_source = "goodreads" if book else None

        if not book:
            isbn13_candidate = record.get("isbn13")
            isbn10_candidate = record.get("isbn")

            if isbn13_candidate:
                if isbn13_candidate in ambiguous_isbns:
                    summary.isbn_ambiguous += 1
                else:
                    book = isbn_map.get(isbn13_candidate)
                    if book:
                        match_source = "isbn"

            if not book and isbn10_candidate:
                if isbn10_candidate in ambiguous_isbns:
                    summary.isbn_ambiguous += 1
                else:
                    book = isbn_map.get(isbn10_candidate)
                    if book:
                        match_source = "isbn"

        if not book:
            title_key = record.get("title_key")
            author_key = record.get("author_key")
            if title_key and author_key:
                cache_key = (title_key, author_key)
                if cache_key not in title_author_cache:
                    qs = (
                        Book.objects.filter(
                            name__iexact=record.get("title") or "",
                            authors__name__iexact=record.get("author") or "",
                        )
                        .distinct()
                        .values_list("id", flat=True)[:2]
                    )
                    matches = list(qs)
                    if len(matches) == 1:
                        title_author_cache[cache_key] = Book.objects.get(id=matches[0])
                    elif len(matches) > 1:
                        title_author_cache[cache_key] = False
                    else:
                        title_author_cache[cache_key] = None

                cached = title_author_cache.get(cache_key)
                if cached is False:
                    summary.title_author_ambiguous += 1
                elif cached:
                    book = cached
                    match_source = "title_author"

        if book and match_source in {"isbn", "title_author"} and allow_backfill:
            if book.goodreads_id and str(book.goodreads_id) != goodreads_id:
                summary.goodreads_id_conflicts += 1
                book = None
                match_source = None
            elif not book.goodreads_id:
                book.goodreads_id = goodreads_id
                book.save(update_fields=["goodreads_id"])
                summary.goodreads_id_backfilled += 1

        if book:
            if match_source == "goodreads":
                summary.matched_by_goodreads += 1
            elif match_source == "isbn":
                summary.matched_by_isbn += 1
            elif match_source == "title_author":
                summary.matched_by_title_author += 1

        resolved[goodreads_id] = book

    return resolved, summary


@transaction.atomic
def import_goodreads_csv(file_obj, user) -> GoodreadsImportSummary:
    """
    Import Goodreads export CSV for a user.

    Creates ReadBook/WantToReadBook entries keyed by Goodreads ID. If a matching
    Book exists, it is linked; otherwise entries are stored as orphaned records
    for later matching.
    """
    summary = GoodreadsImportSummary()

    records, summary = parse_goodreads_records(file_obj, summary)
    summary.processed_books = len(records)

    book_matches, summary = match_goodreads_records(records, summary)

    for goodreads_id, record in records.items():
        status = record["status"]
        book = book_matches.get(goodreads_id)

        if book:
            summary.linked_books += 1
        else:
            summary.unmatched_books += 1

        if status == "read":
            removed = WantToReadBook.objects.filter(
                user=user, goodreads_id=goodreads_id
            ).delete()
            if removed[0]:
                summary.removed_from_want += removed[0]

            defaults = {"book": book} if book else {}
            _, created = ReadBook.objects.update_or_create(
                user=user,
                goodreads_id=goodreads_id,
                defaults=defaults,
            )
            if created:
                summary.read_added += 1
            else:
                summary.read_existing += 1
        else:
            if ReadBook.objects.filter(user=user, goodreads_id=goodreads_id).exists():
                summary.read_overrides_want += 1
                continue
            defaults = {"book": book} if book else {}
            _, created = WantToReadBook.objects.update_or_create(
                user=user,
                goodreads_id=goodreads_id,
                defaults=defaults,
            )
            if created:
                summary.want_added += 1
            else:
                summary.want_existing += 1

    cache.delete(f"read_books_{user.id}")
    cache.delete(f"want_to_read_books_{user.id}")

    return summary

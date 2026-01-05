"""
Books API URL patterns.

These URL patterns follow the same structure as games/api/urls.py.
"""

from django.urls import path

from . import views

app_name = "books-api"

urlpatterns = [
    # Book endpoints
    path("books/", views.BookListView.as_view(), name="book-list"),
    path("books/all/", views.BookAllDataView.as_view(), name="book-all-data"),
    path("books/version/", views.BookDataVersionView.as_view(), name="book-data-version"),
    path("books/<slug:slug>/", views.BookDetailView.as_view(), name="book-detail"),
    # Author endpoints
    path("authors/", views.AuthorListView.as_view(), name="author-list"),
    path("authors/<slug:slug>/", views.AuthorDetailView.as_view(), name="author-detail"),
    path(
        "authors/by-id/<int:goodreads_id>/",
        views.AuthorDetailByIdView.as_view(),
        name="author-detail-by-id",
    ),
    # Book list endpoints
    path("lists/", views.BookListListView.as_view(), name="booklist-list"),
    # Metadata
    path("meta/", views.BookMetaView.as_view(), name="meta"),
    # Genre endpoints
    path("genres/", views.BookGenreListView.as_view(), name="genre-list"),
    path("genres/tree/", views.BookGenreTreeView.as_view(), name="genre-tree"),
    # User tracking endpoints
    path("read-books/", views.ReadBookListCreateView.as_view(), name="read-book-list"),
    path(
        "read-books/<int:goodreads_id>/",
        views.ReadBookDeleteView.as_view(),
        name="read-book-delete",
    ),
    path(
        "want-to-read/",
        views.WantToReadBookListCreateView.as_view(),
        name="want-to-read-list",
    ),
    path(
        "want-to-read/<int:goodreads_id>/",
        views.WantToReadBookDeleteView.as_view(),
        name="want-to-read-delete",
    ),
]

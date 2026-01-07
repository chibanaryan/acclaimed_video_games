from django.urls import path

from books import views

app_name = "books"

urlpatterns = [
    # Main book listing
    path("", views.BookHomePageView.as_view(), name="home"),
    # Book search (HTMX endpoint)
    path("search/", views.BookSearchView.as_view(), name="search"),
    # Toggle read status (HTMX endpoint)
    path(
        "toggle-read/<str:goodreads_id>/",
        views.ToggleReadBookView.as_view(),
        name="toggle-read",
    ),
    # Goodreads import
    path(
        "import/",
        views.GoodreadsImportView.as_view(),
        name="goodreads-import",
    ),
    # Author routes (must be before <slug:slug>/ to avoid matching "authors" as a slug)
    path("authors/", views.AuthorListView.as_view(), name="author-list"),
    path("authors/<slug:slug>/", views.AuthorDetailView.as_view(), name="author-detail"),
    # Book detail (catch-all slug pattern, must be last)
    path("<slug:slug>/", views.BookDetailView.as_view(), name="book-detail"),
]

from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import Form
from django.http import HttpResponse, StreamingHttpResponse
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, View

from games.forms import ImportForm

from . import models, utils


class SPAWithPrerenderedView(View):
    """
    Serves pre-rendered HTML files from the dist folder if they exist,
    otherwise falls back to the SPA (index.html) for client-side routing.
    This enables vite-ssg pre-rendered pages to be served correctly
    while maintaining SPA fallback for client-side routing.
    """

    def get(self, request, *args, **kwargs):
        # Get the requested path and normalize it
        path = request.path.lstrip("/")

        # Determine the file to serve
        dist_path = Path(settings.BASE_DIR) / "frontend" / "dist"

        # For root path, serve index.html
        if path == "" or path == "/":
            file_path = dist_path / "index.html"
        else:
            # For other paths, try /path/index.html first (vite-ssg creates these)
            # e.g., /games/ -> frontend/dist/games/index.html
            file_path = dist_path / path / "index.html"

            # If that doesn't exist, try /path.html
            if not file_path.exists():
                file_path = dist_path / f"{path}.html"

        # If the pre-rendered file exists, serve it
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return HttpResponse(f.read(), content_type="text/html")
            except IOError:
                pass

        # Otherwise fall back to index.html (SPA for client-side routing)
        fallback_path = dist_path / "index.html"
        if fallback_path.exists():
            try:
                with open(fallback_path, "r", encoding="utf-8") as f:
                    return HttpResponse(f.read(), content_type="text/html")
            except IOError:
                pass

        return HttpResponse("Not found", status=404)


class ImportView(LoginRequiredMixin, FormView):
    """
    Handles batch importing of game data files with validation and transaction safety.

    Supports:
    - Batch upload of multiple TSV files (platforms, lists, games, memberships)
    - Single-file uploads (legacy support)
    - Delete existing data
    - IGDB data fetching

    Files are imported in dependency order:
    1. Platforms (no dependencies)
    2. Source Lists (Publications auto-created)
    3. Games (requires Platforms)
    4. Game Positions (requires Lists and Games)
    """

    template_name = "games/import.html"
    form_class = ImportForm
    success_url = reverse_lazy("import")

    def get_context_data(self, **kwargs) -> dict:
        """Add database object counts and persistent errors to context."""
        context = super().get_context_data(**kwargs)

        # Get game counts
        total_games = models.Game.objects.count()
        games_with_igdb = models.Game.objects.exclude(
            igdb_artwork_id__isnull=True
        ).count()
        games_without_igdb = models.Game.objects.filter(
            igdb_artwork_id__isnull=True
        ).count()

        context["counts"] = {
            "platforms": models.Platform.objects.count(),
            "publications": models.Publication.objects.count(),
            "lists": models.List.objects.count(),
            "games": total_games,
            "memberships": models.ListMembership.objects.count(),
            "developers": models.Developer.objects.count(),
        }
        context["igdb_counts"] = {
            "total": total_games,
            "with_igdb": games_with_igdb,
            "without_igdb": games_without_igdb,
            "percentage": int(
                (games_with_igdb / total_games * 100) if total_games > 0 else 0
            ),
        }

        # Get persistent errors from session
        import_errors = self.request.session.pop("import_errors", None)
        import_success_message = self.request.session.pop("import_success", None)
        trigger_igdb = self.request.session.pop("trigger_igdb", False)
        context["import_errors"] = import_errors
        context["import_success_message"] = import_success_message
        context["trigger_igdb"] = trigger_igdb

        return context

    def form_valid(self, form: Form) -> HttpResponse:
        """Process the import form and handle file uploads."""
        import_data = form.cleaned_data

        # Check if this is a batch file import (not delete/igdb operations)
        has_batch_files = any(
            [
                import_data.get("platforms_file"),
                import_data.get("lists_file"),
                import_data.get("games_file"),
                import_data.get("memberships_file"),
            ]
        )

        # If batch files are provided, process them directly
        if has_batch_files and not import_data.get("delete"):
            # Process batch import immediately (handles IGDB flag internally)
            res, message, trigger_igdb = utils.import_batch(import_data)
            if res:
                # Store success message in session (persist across redirect)
                self.request.session["import_success"] = message
                # Store IGDB trigger flag if import succeeded and checkbox was checked
                if trigger_igdb:
                    self.request.session["trigger_igdb"] = True
            else:
                # Store error message in session as a list for persistent display
                self.request.session["import_errors"] = [message]
            # Explicitly save session before redirect
            self.request.session.modified = True
            return super().form_valid(form)

        # For delete/igdb operations, use the standard import flow
        res, message = utils.import_data(import_data)
        if res:
            # Store success message in session (persist across redirect)
            self.request.session["import_success"] = message
        else:
            # Store error message in session as a list for persistent display
            self.request.session["import_errors"] = [message]

        # Explicitly save session before redirect
        self.request.session.modified = True
        return super().form_valid(form)


class IGDBProgressView(LoginRequiredMixin, View):
    """
    Streams IGDB data fetching progress via Server-Sent Events (SSE).
    Allows real-time progress bar updates in the browser.
    """

    def get(self, request, *args, **kwargs):
        """Stream IGDB fetch progress as SSE events."""
        return StreamingHttpResponse(
            utils.import_igdb_with_progress(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )


class PostListView(ListView):
    """
    Post list page
    """

    model = models.Post
    paginate_by = 5

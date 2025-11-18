from typing import Any, Dict
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import Form
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView, View

from games.forms import ImportForm

from . import constants, models, utils


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
    template_name = "games/import.html"
    form_class = ImportForm
    success_url = reverse_lazy("import")

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["import_types"] = constants.TYPES
        return context

    def form_valid(self, form: Form) -> HttpResponse:
        import_data = form.cleaned_data

        res, message = utils.import_data(import_data)
        if res:
            messages.info(self.request, message)
        else:
            messages.error(self.request, message)

        return super().form_valid(form)


class PostListView(ListView):
    """
    Post list page
    """

    model = models.Post
    paginate_by = 5

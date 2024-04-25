from typing import Any, Dict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import Form
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import (FormView, ListView)

from games.forms import ImportForm

from . import constants, models, utils


class ImportView(LoginRequiredMixin, FormView):
    template_name = 'games/import.html'
    form_class = ImportForm
    success_url = reverse_lazy('import')

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['import_types'] = constants.TYPES
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

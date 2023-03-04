from dataclasses import dataclass
from datetime import datetime

from django.db.models import Min
from django.views.generic import DetailView, ListView

from . import models


@dataclass
class Filter:
    param: str
    field: str
    coerce: type = str


class GameListView(ListView):
    paginate_by = 25

    filters = [
        Filter(param='year', field='year_of_release', coerce=int),
        Filter(param='developer', field='developer_id', coerce=int),
        Filter(param='decade', field='year_of_release__gte', coerce=int),
    ]

    def get_queryset(self):
        qs = models.Game.objects.all()

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                qs = qs.filter(**{filter.field: param_val})

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        min_year = models.Game.objects.aggregate(
            min_year=Min('year_of_release'),
        )['min_year']
        max_year = datetime.today().year
        all_years = range(min_year, max_year)
        decades = sorted(list(set(int(x / 10) * 10 for x in all_years)))

        context['developers'] = models.Developer.objects.values_list(
            'id', 'name')
        context['years'] = all_years
        context['is_filtered'] = self.request.GET
        context['decades'] = decades

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)

        return context


class GameDetailView(DetailView):
    model = models.Game


class DeveloperDetailView(DetailView):
    model = models.Developer

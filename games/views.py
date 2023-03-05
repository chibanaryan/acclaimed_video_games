import string
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from django.db.models import Count, Min, Value, Avg, CharField
from django.db.models.functions import Concat, Left, Cast
from django.views.generic import DetailView, ListView
from . import models


@dataclass
class Filter:
    param: str
    field: str
    coerce: type = str
    label: Callable[[str], str] = lambda x: x


class GameListView(ListView):
    """
    Game list page
    """
    paginate_by = 50

    filters = [
        Filter(param='year', field='year_of_release', coerce=int),
        Filter(param='decade', field='decade',
               coerce=str, label=lambda x: f'{x}s'),
        Filter(param='letter', field='first_letter__iexact',
               coerce=str, label=lambda x: f'Letter {x}')
    ]

    def get_queryset(self):
        qs = models.Game.objects.select_related(
            'developer',
        ).annotate(
            decade=Concat(
                Left(Cast('year_of_release', output_field=CharField()), 3), Value('0')),
            first_letter=Left('name', 1),
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                param_val = filter.coerce(param_val)
                qs = qs.filter(**{filter.field: param_val})

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        min_year = models.Game.objects.aggregate(
            min_year=Min('year_of_release'),
        )['min_year']
        max_year = datetime.today().year
        all_years = range(min_year, max_year)
        decades = sorted(list(set(str(int(x / 10) * 10) for x in all_years)))

        context['developers'] = models.Developer.objects.values_list(
            'id', 'name')
        context['years'] = all_years
        context['decades'] = decades
        context['letters'] = list(string.ascii_uppercase)

        page_obj = context['page_obj']
        offset = (page_obj.number - 1) * page_obj.paginator.per_page + 1
        limit = page_obj.paginator.per_page - 1
        total = page_obj.paginator.count

        context['total'] = total
        context['offset'] = offset
        context['limit'] = min((total, limit + offset))

        filter_labels = []
        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)
                filter_labels.append(filter.label(param_val))

        context['filter_label'] = ','.join(filter_labels)

        args = self.request.GET.copy()
        args.pop('page', None)
        context['is_filtered'] = args

        return context


class GameDetailView(DetailView):
    """
    Game detail page
    """
    model = models.Game


class DeveloperDetailView(DetailView):
    """
    Developer detail page
    """
    model = models.Developer


class DeveloperListView(ListView):
    """
    Developer list page
    """
    def get_queryset(self):
        qs = models.Developer.objects.annotate(
            games_count=Count('games'),
            games_rank_avg=Avg('games__rank'),
        ).order_by(
            'games_rank_avg',
        )

        return qs

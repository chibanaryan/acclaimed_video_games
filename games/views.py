from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from django.db.models.functions import Lower

from django.db.models import Avg, CharField, Count, Min, Value
from django.db.models.functions import Cast, Concat, Left
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView

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
        Filter(param='q', field='name__icontains', coerce=str),
        Filter(param='platform', field='platforms__code', coerce=str),
    ]

    def get_queryset(self):
        qs = models.Game.objects.prefetch_related(
            'developers',
            'platforms',
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

        context['platforms'] = models.Platform.objects.all()

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['games'] = models.Game.objects.filter(
            developers__developers=self.object,
        ).order_by(
            'year_of_release',
            'developers',
            'name',
        ).distinct()

        return context


class DeveloperListView(ListView):
    """
    Developer list page
    """
    template_name = 'games/developer_list.html'

    def get_queryset(self):
        qs = models.DeveloperAlias.objects.annotate(
            games_count=Count('games'),
        ).filter(
            games_count__gt=0
        ).order_by(
            Lower('name'),
        )

        return qs


class DeveloperAliasDetailView(DetailView):
    """
    Developer alias detail page
    """
    model = models.DeveloperAlias

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['games'] = self.object.games.order_by(
            'year_of_release',
            'developers',
            'name',
        ).distinct()

        return context


# class DeveloperAliasRedirectView(RedirectView):
#     """
#     Developer alias view that redirects to the canonical developer
#     """

#     def get_redirect_url(self, *args, **kwargs):

#         alias = get_object_or_404(models.DeveloperAlias, **kwargs)
#         url = reverse('developer-detail', args=[alias.developer.pk])

#         return url


class PlatformDetailView(DetailView):
    model = models.Platform

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['games'] = self.object.games.prefetch_related(
            'developers',
        ).distinct()

        return context


class ListListView(ListView):
    """
    List list page
    """
    paginate_by = 50
    filters = [
        Filter(param='publisher', field='publisher_id', coerce=int),
        Filter(param='year', field='year', coerce=int),
        Filter(param='type', field='type', coerce=str),
    ]

    def get_queryset(self):
        qs = models.List.objects.select_related(
            'publisher',
        ).order_by(
            'publisher',
            'year',
            'name',
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                param_val = filter.coerce(param_val)
                qs = qs.filter(**{filter.field: param_val})

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['publishers'] = models.Publication.objects.all()
        context['years'] = sorted(
            list(set(models.List.objects.values_list('year', flat=True).distinct())))

        args = self.request.GET.copy()
        args.pop('page', None)
        context['is_filtered'] = args

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)

        return context


class PublicationListView(ListView):
    """
    Publication list page
    """
    
    def get_queryset(self) :
        return models.Publication.objects.prefetch_related(
            'lists',
        )


class PublicationDetailView(DetailView):
    """
    Publication detail page
    """
    model = models.Publication

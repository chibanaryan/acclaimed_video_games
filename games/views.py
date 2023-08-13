from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import CharField, Count, Min, QuerySet, Value
from django.db.models.functions import Cast, Concat, Left, Lower
from django.forms import Form
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (DetailView, FormView, ListView, RedirectView,
                                  TemplateView)

from games.forms import ImportForm

from . import models, utils, constants


@dataclass
class Filter:
    param: str
    field: str
    coerce: type = str
    label: Callable[[str], str] = lambda x: x


def round_down(num, base=10) -> int:
    return num // base * base


class IndexView(TemplateView):
    template_name = 'games/index.html'

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['games'] = models.Game.objects.all()[:10]
        context['last_update'] = models.Game.objects.latest(
            'modified').modified
        context['list_count'] = round_down(models.List.objects.count(), 50)
        context['publication_count'] = round_down(
            models.Publication.objects.count())
        return context


class GameListView(ListView):
    """
    Game list page
    """
    paginate_by = 100

    filters = [
        Filter(param='year', field='year_of_release', coerce=int),
        Filter(param='decade', field='decade',
               coerce=str, label=lambda x: f'{x}s'),
        Filter(param='q', field='name__icontains', coerce=str),
        Filter(param='platform', field='platforms__code', coerce=str),
    ]

    def get_queryset(self) -> QuerySet:
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

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        min_year = models.Game.objects.aggregate(
            min_year=Min('year_of_release'),
        )['min_year'] or 1970
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
        context['args'] = urlencode(args)
        context['show_search_rank'] = args.get(
            'year') or args.get('decade') or args.get('platform')

        if args.get('highlight'):
            context['highlight'] = int(args.get('highlight'))

        # Build extra_title
        if args:
            extras = []
            for k, v in args.items():
                if k == 'decade':
                    extras.append(f'{v}s')
                elif k == 'q':
                    extras.append(f'"{v}"')
                elif k == 'platform':
                    platform = models.Platform.objects.get(code=v)
                    extras.append(platform.name)
                else:
                    extras.append(v)

            context['title'] = ','.join(extras)
        else:
            context['title'] = 'Top 500'

        return context


class GameDetailView(DetailView):
    """
    Game detail page
    """
    model = models.Game

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        game = self.object

        base_year = int(game.year_of_release / 10) * 10
        context['decade'] = base_year

        year_games = list(models.Game.objects.filter(
            year_of_release=game.year_of_release))
        context['rank_for_year'] = year_games.index(game) + 1

        top_year = base_year + 9
        decade_games = list(models.Game.objects.filter(
            year_of_release__gte=base_year, year_of_release__lte=top_year))
        context['rank_for_decade'] = decade_games.index(game) + 1

        context['list_groups'] = [
            ('All Time Lists', game.lists.filter(
                list__type=constants.LIST_ALLTIME)),
            ('Other Lists', game.lists.filter(list__type=constants.LIST_OTHER)),
            ('End of Year Lists', game.lists.filter(list__type=constants.LIST_EOY)),
        ]

        return context


class DeveloperDetailView(DetailView):
    """
    Developer detail page
    """
    model = models.Developer

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        games = models.Game.objects.filter(
            developers__developer=self.object,
        ).order_by(
            'year_of_release',
            'developers',
            'name',
        ).distinct()

        # Remove duplicates
        games = {x.id: x for x in games}.values()

        context['games'] = games

        return context


class DeveloperListView(ListView):
    """
    Developer list page
    """
    template_name = 'games/developer_list.html'

    def get_queryset(self) -> QuerySet:
        qs = models.DeveloperAlias.objects.annotate(
            games_count=Count('games'),
        ).filter(
            games_count__gt=0
        ).order_by(
            Lower('name'),
        )

        return qs


class DeveloperAliasRedirectView(RedirectView):
    """
    Developer alias view that redirects to the canonical developer
    """

    def get_redirect_url(self, *args, **kwargs) -> HttpResponse:

        alias = get_object_or_404(models.DeveloperAlias, **kwargs)
        url = reverse('developer-detail', args=[alias.developer.pk])

        return url


class ListListView(ListView):
    """
    List list page
    """
    paginate_by = 100
    filters = [
        Filter(param='publisher', field='publisher_id', coerce=int),
        Filter(param='year', field='year', coerce=int),
        Filter(param='type', field='type', coerce=str),
    ]

    def get_queryset(self) -> QuerySet:
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

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        context['publishers'] = models.Publication.objects.all()
        context['list_types'] = constants.LIST_TYPES
        context['years'] = sorted(
            list(set(models.List.objects.values_list('year', flat=True).distinct())))

        args = self.request.GET.copy()
        args.pop('page', None)
        context['is_filtered'] = args
        context['args'] = urlencode(args)

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)

        return context


class PublicationListView(ListView):
    """
    Publication list page
    """

    def get_queryset(self) -> QuerySet:
        return models.Publication.objects.prefetch_related(
            'lists',
        )


class PublicationDetailView(DetailView):
    """
    Publication detail page
    """
    model = models.Publication

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        context['list_groups'] = [
            ('All Time Lists', self.object.lists.filter(
                type=constants.LIST_ALLTIME)),
            ('Other Lists', self.object.lists.filter(type=constants.LIST_OTHER)),
            ('End of Year Lists', self.object.lists.filter(type=constants.LIST_EOY)),
        ]

        return context


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

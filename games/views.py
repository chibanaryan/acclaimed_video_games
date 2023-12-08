from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import CharField, Count, Min, QuerySet, Value, Q
from django.db.models.functions import Cast, Concat, Left, Lower
from django.forms import Form
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (DetailView, FormView, ListView, RedirectView,
                                  TemplateView)

from games.forms import ImportForm

from . import constants, models, utils


@dataclass
class Filter:
    param: str
    fields: List[str]
    coerce: type = str
    label: Callable[[str], str] = lambda x: x

    def filter_queryset(self, qs, param_val):
        if not param_val:
            return qs

        param_val = self.coerce(param_val.strip())
        if self.fields:
            query = Q()
            for field in self.fields:
                query |= Q(**{field: param_val})
        qs = qs.filter(query)

        return qs


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
        context['posts'] = models.Post.objects.filter(active=True)

        return context


class GameListView(ListView):
    """
    Game list page
    """
    paginate_by = 100

    filters = [
        Filter(param='year', fields=['year_of_release'], coerce=int),
        Filter(param='decade', fields=['decade'],
               coerce=str, label=lambda x: f'{x}s'),
        Filter(
            param='q',
            fields=[
                'name__search',
                'name__icontains',
                'name_normalized__search',
                'name_normalized__icontains',
            ],
            coerce=str),
        Filter(param='platform', fields=['platforms__code'], coerce=str),
        Filter(param='genre', fields=['genres'], coerce=int),
    ]

    def get_normalized_args(self):
        args = self.request.GET.copy()

        if args.get('alltime'):
            args.pop('year')
            args.pop('decade')
            args.pop('alltime')

        args = {k: v for (k, v) in args.items() if v}

        return args

    def get_title(self, args):
        prefix = ''
        base_title = ''
        is_all_time = not args.get('decade') and not args.get('year')

        if is_all_time:
            base_title = f'All Time'
            prefix = 'Most Acclaimed Games of'
        elif args.get('decade'):
            base_title = f"{args['decade']}s"
            prefix = 'Most Acclaimed Games of the'
        elif args.get('year'):
            base_title = f"{args['year']}"
            prefix = 'Most Acclaimed Games of'
        else:
            prefix = ''

        extra_bits = []
        if args.get('platform'):
            platform = models.Platform.objects.get(code=args['platform'])
            extra_bits.append(platform.name)
        if args.get('genre'):
            genre = models.Genre.objects.get(id=args['genre'])
            extra_bits.append(genre.name)
        if args.get('q'):
            extra_bits.append('"' + args["q"] + '"')

        extra_title = ', '.join(extra_bits)

        if extra_title:
            if is_all_time:
                prefix = ''
                base_title = extra_title
            else:
                base_title = f'{base_title} - {extra_title}'

        return prefix, base_title

    def get_queryset(self) -> QuerySet:
        qs = models.Game.objects.prefetch_related(
            'genres',
            'developers',
            'platforms',
        ).annotate(
            decade=Concat(
                Left(Cast('year_of_release', output_field=CharField()), 3), Value('0')),
            first_letter=Left('name', 1),
        )

        args = self.get_normalized_args()

        # If q is present then remove all other args
        if args.get('q'):
            args = {'q': args['q']}

        for filter in self.filters:
            param_val = args.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        args = self.get_normalized_args()

        # Get list of decades and years
        min_year = models.Game.objects.aggregate(
            min_year=Min('year_of_release'),
        )['min_year'] or 1970
        max_year = datetime.today().year
        all_years = range(min_year, max_year)
        decades = sorted(list(set(str(int(x / 10) * 10) for x in all_years)))

        context['years'] = all_years
        context['decades'] = decades

        # Get list of platforms and genres
        platforms = models.Platform.objects.all()
        genres = models.Genre.objects.all()
        rank_heading = 'All time rank'

        if args.get('year'):
            platforms = platforms.filter(
                games__year_of_release=args['year']).distinct()
            genres = genres.filter(
                game__year_of_release=args['year']).distinct()
            rank_heading = f"{args['year']} rank"

        if args.get('decade'):
            start = int(args['decade'])
            end = start + 9
            platforms = platforms.filter(
                games__year_of_release__gte=start,
                games__year_of_release__lte=end,
            ).distinct()
            genres = genres.filter(
                game__year_of_release__gte=start,
                game__year_of_release__lte=end,
            ).distinct()
            rank_heading = f"{args['decade']}s rank"

        context['platforms'] = platforms
        context['genres'] = genres

        if args.get('highlight'):
            context['highlight'] = int(args.get('highlight'))

        # Handle pagination
        page_obj = context['page_obj']
        offset = (page_obj.number - 1) * page_obj.paginator.per_page
        limit = page_obj.paginator.per_page + offset
        total = page_obj.paginator.count

        if limit > total:
            limit = total

        context['offset'] = offset
        context['show_pagination'] = len(page_obj.paginator.page_range) > 1

        # Build titles
        if total:
            context['subtitle'] = f'{offset + 1} to {limit} of {total} results'
        else:
            context['subtitle'] = '0 results'

        prefix, base_title = self.get_title(args)
        context['title'] = f'{prefix} {base_title}'
        context['short_title'] = base_title

        # Build list of selected filters
        for filter in self.filters:
            param_val = args.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)

        # Is the list filtered?
        context['is_filtered'] = args.get('platform') or \
            args.get('genre') or \
            args.get('q')

        context['show_year_rank'] = args.get('year')
        context['show_decade_rank'] = args.get('decade')
        context['rank_heading'] = rank_heading

        context['args'] = urlencode(args)

        return context


class GameDetailView(DetailView):
    """
    Game detail page
    """
    model = models.Game

    def get_object(self, *args, **kwargs):
        """
        Lookup object by its igdb_id 
        """
        queryset = self.get_queryset()

        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk is not None:
            queryset = queryset.filter(igdb_id=pk)

        return queryset.get()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)

        game = self.object

        if game.year_of_release:
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
            ('Decade Lists', game.lists.filter(
                list__type=constants.LIST_DECADE)),
            ('Miscellaneous Lists', game.lists.filter(
                list__type=constants.LIST_MISC)),
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
    paginate_by = 100

    filters = [
        Filter(
            param='q',
            fields=['name__search', 'name__icontains'],
            coerce=str),
    ]

    def get_queryset(self) -> QuerySet:
        qs = models.DeveloperAlias.objects.annotate(
            games_count=Count('games'),
        ).filter(
            games_count__gt=0
        ).order_by(
            Lower('name'),
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['is_filtered'] = self.request.GET.get('q')

        page_obj = context['page_obj']
        offset = (page_obj.number - 1) * page_obj.paginator.per_page
        limit = page_obj.paginator.per_page + offset
        total = page_obj.paginator.count

        if limit > total:
            limit = total

        context['show_pagination'] = len(page_obj.paginator.page_range) > 1

        if total:
            context['subtitle'] = f'{offset + 1} to {limit} of {total} results'
        else:
            context['subtitle'] = '0 results'

        filter_labels = []
        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            if param_val:
                context['selected_' + filter.param] = filter.coerce(param_val)
                filter_labels.append(filter.label(param_val))

        return context


class DeveloperAliasRedirectView(RedirectView):
    """
    Developer alias view that redirects to the canonical developer
    """

    def get_redirect_url(self, *args, **kwargs) -> HttpResponse:
        alias = get_object_or_404(models.DeveloperAlias, igdb_id=kwargs['pk'])
        url = reverse('developer-detail', args=[alias.developer.pk])

        return url


class ListListView(ListView):
    """
    List list page
    """
    paginate_by = 100
    filters = [
        Filter(param='publisher', fields=['publisher_id'], coerce=int),
        Filter(param='year', fields=['year'], coerce=int),
        Filter(param='type', fields=['type'], coerce=str),
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
            qs = filter.filter_queryset(qs, param_val)

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
            ('Miscellaneous Lists', self.object.lists.filter(
                type=constants.LIST_MISC)),
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

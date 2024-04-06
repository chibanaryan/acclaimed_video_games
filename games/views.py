import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Min, Q, QuerySet
from django.db.models.functions import Lower
from django.forms import Form
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (DetailView, FormView, ListView, RedirectView,
                                  TemplateView)
from games.forms import ImportForm, SearchForm

from . import constants, models, utils

decade_pattern = re.compile(r'^\d{2}(\d{2})-(\d{2})$')
year_pattern = re.compile(r'^(\d{4})$')


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
        context['posts'] = models.Post.objects.filter(active=True)[:5]

        return context


class GameYearListView(ListView):
    paginate_by = 100
    template_name = 'games/game_year_list.html'

    @lru_cache
    def get_data(self):
        slug = self.kwargs['slug']

        alltime_match = slug == 'alltime'
        decade_match = decade_pattern.match(slug)
        year_match = year_pattern.match(slug)
        start = None
        end = None
        title = None
        title_prefix = 'Most Acclaimed Games of'
        decade_slug = None
        year_slug = None

        if decade_match:
            start, end = [int(x) for x in decade_match.groups()]
            if start > 50:
                start += 1900
            else:
                start += 2000

            if end > 50:
                end += 1900
            else:
                end += 2000

            title = f'{title_prefix} {start} to {end}'
            decade_slug = slug

        elif year_match:
            start = int(year_match.groups()[0])
            end = start
            title = f'{title_prefix} {start}'
            year_slug = slug

        elif alltime_match:
            title = f'{title_prefix} All Time'

        return {
            'start': start,
            'end': end,
            'title': title,
            'decade_slug': decade_slug,
            'year_slug': year_slug,
        }

    def get_queryset(self) -> QuerySet:
        qs = models.Game.objects.prefetch_related(
            'genres',
            'developers',
            'platforms',
        )

        data = self.get_data()

        if data.get('start') and data.get('end'):
            qs = qs.filter(
                year_of_release__gte=data['start'],
                year_of_release__lte=data['end'],
            ).distinct()

        return qs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        data = self.get_data()

        # Get list of decades and years
        min_year = models.Game.objects.aggregate(
            min_year=Min('year_of_release'),
        )['min_year'] or 1970
        max_year = datetime.today().year
        all_years = range(min_year, max_year)

        year_count_map = dict(
            models.Game.objects.values_list(
                'year_of_release'
            ).annotate(
                count=Count('id')
            ).order_by(
                'year_of_release'
            ))

        all_years_with_counts = [(str(x), year_count_map.get(x, 0))
                                 for x in all_years]
        decades = sorted(list(set(int(x / 10) * 10 for x in all_years)))
        decades = [f'{x}-{str(x + 9)[2:4]}' for x in decades]

        context['years'] = all_years_with_counts
        context['decades'] = decades
        context['form'] = SearchForm()
        context.update(data)

        return context


class GameSearchView(ListView):
    paginate_by = 100
    template_name = 'games/search.html'

    def get_queryset(self) -> QuerySet:
        qs = models.Game.objects.prefetch_related(
            'genres',
            'platforms',
            'developers',
        ).annotate(
            genre_count=Count('genres')
        ).order_by(
            'rank'
        )

        form = SearchForm(self.request.GET)
        if form.is_valid():
            args = form.cleaned_data
            if args.get('genres'):
                genres = args.get('genres')
                genre_option = args.get('genre_option')
                if genre_option == constants.SEARCH_ANY:
                    q = Q()
                    for genre in genres:
                        q |= Q(genres=genre)
                    qs = qs.filter(q)
                elif genre_option == constants.SEARCH_ALL:
                    for genre in genres:
                        qs = qs.filter(genres=genre)
                elif genre_option == constants.SEARCH_EXACTLY:
                    for genre in genres:
                        qs = qs.filter(genres=genre)
                    qs = qs.filter(genre_count=len(genres))
                elif genre_option == constants.SEARCH_NONE:
                    qs = qs.exclude(genres__in=genres)
                else:
                    qs = qs.filter(genres__in=genres)
            if args.get('platforms'):
                qs = qs.filter(platforms__in=args['platforms'])
            if args.get('start'):
                qs = qs.filter(year_of_release__gte=args['start'])
            if args.get('end'):
                qs = qs.filter(year_of_release__lte=args['end'])

        return qs.distinct()

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['form'] = SearchForm(self.request.GET)
        paginator = context['paginator']
        context['title'] = f'{paginator.count} search results'

        return context


class GameDetailView(DetailView):
    """
    Game detail page
    """
    model = models.Game

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
        utils.Filter(
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
        url = reverse('developer-detail', args=[alias.developer.slug])

        return url


class ListListView(ListView):
    """
    List list page
    """
    paginate_by = 100
    filters = [
        utils.Filter(param='publisher', fields=['publisher_id'], coerce=int),
        utils.Filter(param='year', fields=['year'], coerce=int),
        utils.Filter(param='type', fields=['type'], coerce=str),
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


class PostListView(ListView):
    """
    Post list page
    """
    model = models.Post
    paginate_by = 5

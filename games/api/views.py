from datetime import datetime

from django.contrib.flatpages.models import FlatPage
from django.db.models import Count, Min, Q
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.views import APIView, Response

from .. import models, utils
from . import serializers


class GameListView(ListAPIView):

    serializer_class = serializers.GameSummarySerializer
    filters = [
        utils.Filter(
            param='q',
            fields=[
                'name_normalized__search',
                'name_normalized__icontains',
                'name__search',
                'name__icontains',
            ],
        ),
        utils.Filter(
            param='developer',
            fields=['developers__developer__igdb_id'],
            coerce=int),
        utils.Filter(
            param='start',
            fields=['year_of_release__gte'],
            coerce=int),
        utils.Filter(
            param='end',
            fields=['year_of_release__lte'],
            coerce=int),
    ]

    def get_queryset(self):
        qs = models.Game.objects.prefetch_related(
            'developers',
            'platforms',
            'genres',
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        genre_option = self.request.GET.get('genre_option')

        genres = self.request.GET.get('genres')
        if genres:
            genres = [int(x) for x in genres.split(',')]
            if genre_option == 'A':     # Any
                q = Q()
                for genre in genres:
                    q |= Q(genres=genre)
                qs = qs.filter(q)
            else:                       # All
                for genre in genres:
                    qs = qs.filter(genres=genre)

        platforms = self.request.GET.get('platforms')
        if platforms:
            platforms = [int(x) for x in platforms.split(',')]
            qs = qs.filter(platforms__in=platforms)

        order_by = self.request.GET.get('order_by')
        if order_by:
            qs = qs.order_by(order_by)

        return qs.distinct()


class GameDetailView(RetrieveAPIView):
    lookup_field = 'slug'
    serializer_class = serializers.GameDetailSerializer
    queryset = models.Game.objects.prefetch_related('lists')


class DeveloperDetailView(RetrieveAPIView):
    lookup_field = 'slug'
    serializer_class = serializers.DeveloperSerializer
    queryset = models.Developer.objects.all()


class DeveloperAliasListView(ListAPIView):

    serializer_class = serializers.DeveloperAliasSerializer
    filters = [
        utils.Filter(
            param='q',
            fields=['name__search', 'name__icontains'],
        )
    ]

    def get_queryset(self):
        qs = models.DeveloperAlias.objects.annotate(
            games_count=Count('games'),
        ).order_by(
            Lower('name')
        )

        for filter in self.filters:
            param_val = self.request.GET.get(filter.param)
            qs = filter.filter_queryset(qs, param_val)

        return qs


class DeveloperAliasDetailView(RetrieveAPIView):
    lookup_field = 'igdb_id'
    serializer_class = serializers.DeveloperAliasSerializer
    queryset = models.DeveloperAlias.objects.annotate(
        games_count=Count('games'),
    ).order_by(
        Lower('name')
    )


class ListListView(ListAPIView):

    serializer_class = serializers.ListSerializer

    filters = [
        utils.Filter(param='publisher', fields=['publisher_id'], coerce=int),
        utils.Filter(param='year', fields=['year'], coerce=int),
        utils.Filter(param='type', fields=['type'], coerce=str),
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
            qs = filter.filter_queryset(qs, param_val)

        return qs


class PublicationListView(ListAPIView):
    serializer_class = serializers.PublicationSerializer
    queryset = models.Publication.objects.all()


class PublicationDetailView(RetrieveAPIView):
    serializer_class = serializers.PublicationSerializer
    queryset = models.Publication.objects.all()


class PostListView(ListAPIView):
    serializer_class = serializers.PostSerializer
    queryset = models.Post.objects.all()


class MetaView(APIView):

    def get(self, *args, **kwargs):
        data = {}

        # Lists
        list_year_counts = models.List.objects.order_by(
            'year',
        ).values(
            'year',
        ).annotate(
            count=Count('id')
        ).values(
            'year',
            'count',
        )

        data['lists'] = {
            'years': list_year_counts,
        }

        # Games
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

        all_years_with_counts = [
            {'year': x, 'count': year_count_map.get(x, 0)} for x in all_years]
        decades = sorted(list(set(int(x / 10) * 10 for x in all_years)))
        decades = [f'{x}-{str(x + 9)[2:4]}' for x in decades]

        data['games'] = {
            'years': all_years_with_counts,
            'decades': decades,
            'last_update': models.Game.objects.latest('modified').modified
        }

        return Response(data)


class SnippetDetailView(APIView):
    serializer_class = serializers.PublicationSerializer

    def get(self, *args, **kwargs):
        snippet = get_object_or_404(models.Snippet, **kwargs)
        return Response({'snippet': snippet.text})


class PageDetailView(RetrieveAPIView):

    serializer_class = serializers.PageSerializer

    def get_object(self):
        url = self.kwargs.get('url')
        page = get_object_or_404(FlatPage, url=f'/{url}/')
        return page


class GenreListView(ListAPIView):
    serializer_class = serializers.GenreSerializer
    queryset = models.Genre.objects.all()


class PlatformListView(ListAPIView):
    serializer_class = serializers.PlatformSerializer
    queryset = models.Platform.objects.all()

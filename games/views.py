from django.shortcuts import render

from django.views.generic import ListView
from . import models


class GameListView(ListView):

    def get_queryset(self):
        qs = models.Game.objects.all()

        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(year_of_release=year)

        return qs
    
    def get_context_data(self, **kwargs) :
        context = super().get_context_data(**kwargs)

        context['is_filtered'] = self.request.GET
        context['years'] = sorted(models.Game.objects.values_list('year_of_release', flat=True).distinct())

        return context

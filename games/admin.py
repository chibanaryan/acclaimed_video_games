from typing import Any
from django.contrib import admin
from . import models


class DeveloperAliasInlineAdmin(admin.TabularInline):
    model = models.DeveloperAlias
    extra = 0


@admin.register(models.Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']


@admin.register(models.Developer)
class DeveloperAdmin(admin.ModelAdmin):
    search_fields = ['name']
    inlines = [DeveloperAliasInlineAdmin]


@admin.register(models.DeveloperAlias)
class DeveloperAliasAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'igdb_id']
    search_fields = ['name']


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'rank',
        'year_rank',
        'decade_rank',
        'year_of_release',
        'igdb_id',
        'igdb_artwork_id',
        'igdb_url',
    ]
    list_filter = ['year_of_release']
    search_fields = ['name']
    filter_horizontal = ['developers', 'platforms', 'genres']

    # def save_model(self, request, obj: models.Game, form, change):
    #     obj.get_igdb_data(cache_results=False)
    #     obj.save()


@admin.register(models.List)
class ListAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'order', 'publisher', 'type']
    list_filter = ['type', 'publisher']
    search_fields = ['name']


@admin.register(models.ListMembership)
class ListMembershipAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'slug']


@admin.register(models.Snippet)
class SnippetAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'date', 'active']

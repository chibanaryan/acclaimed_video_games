from django.contrib import admin
from . import models


class DeveloperAliasInlineAdmin(admin.TabularInline):
    model = models.DeveloperAlias
    extra = 0

@admin.register(models.Platform)
class PlatformAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Developer)
class DeveloperAdmin(admin.ModelAdmin):
    search_fields = ['name']
    inlines = [DeveloperAliasInlineAdmin]


@admin.register(models.DeveloperAlias)
class DeveloperAliasAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'rank', 'year_of_release']
    list_filter = ['year_of_release']
    search_fields = ['name']
    filter_horizontal = ['developers', 'platforms']


@admin.register(models.List)
class ListAdmin(admin.ModelAdmin):
    list_filter = ['publisher']


@admin.register(models.ListMembership)
class ListMembershipAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Publication)
class PublicationAdmin(admin.ModelAdmin):
    pass

from django.contrib import admin
from . import models


@admin.register(models.Developer)
class DeveloperAdmin(admin.ModelAdmin):
    pass


@admin.register(models.Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'rank', 'developer', 'year_of_release']
    list_filter = ['year_of_release']
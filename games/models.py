from django.db import models
from django.utils.text import slugify
from . import constants, igdb

class Snippet(models.Model):
    """A reusable piece of text"""
    slug = models.SlugField(unique=True)
    text = models.TextField()

    def __str__(self):
        return self.slug

    def save(self, *args, **kwargs):
        slugified_slug = slugify(self.slug)
        if self.slug != slugified_slug:
            self.slug = slugified_slug
        super().save(*args, **kwargs)


class Platform(models.Model):
    """
    The platform a game available for
    """
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Developer(models.Model):
    """
    A company or organization that produces video games
    """
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class DeveloperAlias(models.Model):
    """
    A different name that a developer may use
    """
    developer = models.ForeignKey(
        'Developer',
        on_delete=models.CASCADE,
        related_name='aliases')
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Developer aliases'

    def __str__(self) -> str:
        if self.name != self.developer.name:
            return f'{self.name} ({self.developer})'
        else:
            return self.name


class Game(models.Model):
    """
    A video game
    """
    name = models.CharField(max_length=100)
    rank = models.IntegerField(unique=True)
    year_of_release = models.PositiveSmallIntegerField()
    developers = models.ManyToManyField(
        'DeveloperAlias',
        blank=True,
        related_name='games')
    platforms = models.ManyToManyField(
        'Platform',
        blank=True,
        related_name='games')
    modified = models.DateTimeField(auto_now=True)
    igdb_id = models.IntegerField(null=True, blank=True, unique=True)
    igdb_artwork_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True)

    class Meta:
        ordering = ['rank']

    def __str__(self) -> str:
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.igdb_id or not self.igdb_artwork_id:
            data = igdb.api.get_game_info(self)
            if data:
                self.igdb_id = data['game_id']
                self.igdb_artwork_id = data['artwork_id']

        return super().save(*args, **kwargs)

    @property
    def thumbnail(self):
        if self.igdb_artwork_id:
            return f'https://images.igdb.com/igdb/image/upload/t_cover_small/{self.igdb_artwork_id}'

    @property
    def image(self):
        if self.igdb_artwork_id:
            return f'https://images.igdb.com/igdb/image/upload/t_cover_big/{self.igdb_artwork_id}'


class Publication(models.Model):
    """
    A magazine, website etc that publishes lists
    """
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class List(models.Model):
    """
    A list published by a critic or publication
    """
    publisher = models.ForeignKey(
        'Publication',
        null=True,
        blank=True,
        related_name='lists',
        on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    year = models.PositiveSmallIntegerField()
    type = models.CharField(
        max_length=1,
        choices=constants.LIST_TYPES,
        default=constants.LIST_EOY)
    order = models.PositiveIntegerField(unique=True, null=True)

    class Meta:
        ordering = ['order', 'type', 'name']
        unique_together = ['publisher', 'name', 'year']

    def __str__(self) -> str:
        return self.name


class ListMembership(models.Model):
    """
    A game's appearance in a list
    """
    list = models.ForeignKey('List', on_delete=models.CASCADE)
    game = models.ForeignKey(
        'Game', on_delete=models.CASCADE, related_name='lists')
    rank = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return f'{self.list} - {self.game} - {self.rank}'

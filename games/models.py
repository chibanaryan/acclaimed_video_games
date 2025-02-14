import logging

import markdown
from django.db import IntegrityError, models
from django.utils.text import Truncator, slugify
from unidecode import unidecode

from . import constants, igdb

logger = logging.getLogger(__name__)

api = igdb.get_api()


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
    slug = models.SlugField(max_length=100, null=True, blank=True)
    igdb_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

    @property
    def other_aliases(self) -> models.QuerySet:
        return self.aliases.exclude(name=self.name)


class DeveloperAlias(models.Model):
    """
    A different name that a developer may use
    """
    developer = models.ForeignKey(
        'Developer',
        on_delete=models.CASCADE,
        related_name='aliases')
    name = models.CharField(max_length=100, unique=True)
    igdb_id = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Developer aliases'

    def __str__(self) -> str:
        if self.name != self.developer.name:
            return f'{self.name} ({self.developer})'
        else:
            return self.name


class Genre(models.Model):
    """A video game genre"""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Game(models.Model):
    """
    A video game
    """
    name = models.CharField(max_length=100)
    name_normalized = models.CharField(max_length=100, null=True, blank=True)
    slug = models.SlugField(max_length=100, null=True, blank=True)
    genres = models.ManyToManyField('Genre', blank=True)
    description = models.TextField(null=True, blank=True)
    rank = models.IntegerField()
    year_of_release = models.PositiveSmallIntegerField(null=True, blank=True)
    developers = models.ManyToManyField(
        'DeveloperAlias',
        blank=True,
        related_name='games')
    platforms = models.ManyToManyField(
        'Platform',
        blank=True,
        related_name='games')
    modified = models.DateTimeField(auto_now=True)
    igdb_id = models.IntegerField(null=True, blank=True)
    igdb_artwork_id = models.CharField(
        max_length=100,
        null=True,
        blank=True)
    igdb_url = models.URLField(null=True, blank=True)
    year_rank = models.IntegerField(null=True, blank=True)
    decade_rank = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['rank']

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Save the normalized version of the name
        normalized = unidecode(self.name)
        if self.name != normalized:
            self.name_normalized = normalized

        from . import utils
        try:
            self.year_rank = utils.get_ranking_for_year(self)
            self.decade_rank = utils.get_ranking_for_decade(self)
        except Exception as e:
            logger.error(str(e))

        super().save(*args, **kwargs)

    def get_igdb_data(self, cache_results=True):
        if not self.igdb_id:
            return

        data = api.get_game_info_by_id(self.igdb_id, cache_results)
        self.slug = slugify(data.get('slug'))
        self.igdb_url = data.get('url')
        self.igdb_artwork_id = data.get('cover')
        self.description = '\n\n'.join(
            [x for x in [data.get('storyline'), data.get('summary')] if x])

        developer_aliases = []
        for d in data['developers']:

            # This developer is a parent
            if not d.get('parent'):
                developer, created = Developer.objects.update_or_create(
                    name=d['name'],
                    defaults={
                        'slug': d['slug'],
                        'igdb_id': d['id'],
                    }
                )

            # This developer has a parent
            else:
                parent_obj = d.get('parent')
                if parent_obj:
                    developer, created = Developer.objects.update_or_create(
                        name=parent_obj['name'],
                        defaults={
                            'slug': parent_obj['slug'],
                            'igdb_id': parent_obj['id'],
                        }
                    )

            try:
                developer_alias, created = DeveloperAlias.objects.update_or_create(
                    developer=developer,
                    name=d['name'],
                    defaults={
                        'igdb_id': d['id'],
                    }
                )
            except IntegrityError:
                developer_alias = DeveloperAlias.objects.get(name=d['name'])

            developer_aliases.append(developer_alias)

        self.developers.set(developer_aliases)

        genres = []
        for genre_name in data.get('genres'):
            genre, created = Genre.objects.get_or_create(name=genre_name)
            genres.append(genre)
        self.genres.set(genres)

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
    slug = models.SlugField(max_length=100)

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)


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
        ordering = ['order', 'type', 'publisher', 'year', 'name']
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


class Post(models.Model):
    """
    A blog-style news post
    """
    title = models.CharField(max_length=100, null=True, blank=True)
    text = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-date']

    def __str__(self) -> str:
        return self.title or Truncator(self.text).words(10)

    @property
    def text_rendered(self):
        return markdown.markdown(self.text)

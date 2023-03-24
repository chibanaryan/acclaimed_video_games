from django.db import models


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
    #developers = models.ManyToManyField('Developer', related_name='aliases')
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Developer aliases'

    def __str__(self) -> str:
        # if self.name != self.developer.name:
        #     return f'{self.name} ({self.developer})'
        # else:
        return self.name


class Game(models.Model):
    """
    A video game
    """
    name = models.CharField(max_length=100)
    rank = models.IntegerField()
    year_of_release = models.PositiveSmallIntegerField()
    developers = models.ManyToManyField(
        'DeveloperAlias',
        blank=True,
        related_name='games')
    platforms = models.ManyToManyField(
        'Platform',
        blank=True,
        related_name='games')

    class Meta:
        ordering = ['rank']

    def __str__(self) -> str:
        return self.name


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
    TYPES = [
        ('M', 'Main'),
        ('E', 'End of year'),
    ]
    publisher = models.ForeignKey(
        'Publication',
        null=True,
        blank=True,
        related_name='lists',
        on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    year = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=1, choices=TYPES, default='M')

    class Meta:
        ordering = ['type', 'name']
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

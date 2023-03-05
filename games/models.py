from django.db import models


class Developer(models.Model):
    """
    A company or organization that produces video games
    """
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Game(models.Model):
    """
    A video game
    """
    name = models.CharField(max_length=100)
    rank = models.IntegerField()
    year_of_release = models.PositiveSmallIntegerField()
    developer = models.ForeignKey(
        'Developer',
        null=True,
        on_delete=models.SET_NULL,
        related_name='games')

    class Meta:
        ordering = ['rank']

    def __str__(self) -> str:
        return self.name


class List(models.Model):
    """
    A list published by a video game critic
    """
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)

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

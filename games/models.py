from django.db import models


class Developer(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.name


class Game(models.Model):
    name = models.CharField(max_length=100)
    rank = models.IntegerField()
    year_of_release = models.PositiveSmallIntegerField()
    developer = models.ForeignKey(
        'Developer',
        null=True,
        on_delete=models.SET_NULL)
    
    class Meta:
        ordering = ['rank']

    def __str__(self) -> str:
        return self.name

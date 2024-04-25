from django.contrib.flatpages.models import FlatPage
from rest_framework import serializers
from django.db.models import F
from .. import models, constants


class IdNameSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    name = serializers.CharField()

    def get_id(self, obj):
        if hasattr(obj, 'igdb_id'):
            return obj.igdb_id
        else:
            return obj.id


class IdSlugNameSerializer(IdNameSerializer):
    slug = serializers.CharField()


# class GameListMembershipSerializer(serializers.ModelSerializer):
#     list = serializers.CharField(source='list.name')
#     publication = serializers.CharField(source='list.publisher.name')
#     type = serializers.CharField(source='list.type')
#     url = serializers.CharField(source='list.url')
#     year = serializers.IntegerField(source='list.year')

#     class Meta:
#         model = models.ListMembership
#         fields = [
#             'list',
#             'publication',
#             'rank',
#             'type',
#             'url',
#             'year',
#         ]


game_fields = [
    'id',
    'decade_rank',
    'description',
    'developers',
    'genres',
    'igdb_artwork_id',
    'igdb_url',
    'name',
    'name_normalized',
    'platforms',
    'rank',
    'slug',
    'year_of_release',
    'year_rank',
]


class GameSummarySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='igdb_id')
    developers = IdNameSerializer(many=True)
    genres = IdNameSerializer(many=True)
    platforms = IdNameSerializer(many=True)

    class Meta:
        model = models.Game
        fields = game_fields


class GameDetailSerializer(GameSummarySerializer):
    lists = serializers.SerializerMethodField()

    class Meta:
        model = models.Game
        fields = game_fields + ['lists']

    def get_lists(self, obj):
        return obj.lists.values(
            'rank',
            name=F('list__name'),
            publication=F('list__publisher__name'),
            type=F('list__type'),
            url=F('list__url'),
            year=F('list__year'),
        )


class DeveloperSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='igdb_id')
    aliases = IdNameSerializer(many=True)

    class Meta:
        model = models.Developer
        fields = [
            'id',
            'name',
            'slug',
            'aliases',
        ]


class DeveloperAliasSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='igdb_id')
    games_count = serializers.IntegerField()
    developer = IdSlugNameSerializer()

    class Meta:
        model = models.DeveloperAlias
        fields = [
            'id',
            'name',
            'developer',
            'games_count',
        ]


class ListSerializer(serializers.ModelSerializer):

    publisher = serializers.CharField(source='publisher.name')

    class Meta:
        model = models.List
        fields = [
            'id',
            'name',
            'publisher',
            'year',
            'type',
            'url',
        ]


class PublicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Publication
        fields = [
            'id',
            'name',
        ]


class PostSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Post
        fields = [
            'id',
            'title',
            'text',
            'date',
            'active',
        ]


class PageSerializer(serializers.ModelSerializer):

    class Meta:
        model = FlatPage
        fields = [
            'id',
            'url',
            'title',
            'content',
        ]


class GenreSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Genre
        fields = [
            'id',
            'name',
        ]


class PlatformSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Platform
        fields = [
            'id',
            'name',
        ]

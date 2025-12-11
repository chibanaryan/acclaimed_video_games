import markdown
from django.contrib.flatpages.models import FlatPage
from django.db.models import F
from rest_framework import serializers

from .. import models


class IdNameSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    name = serializers.CharField()

    def get_id(self, obj):
        if hasattr(obj, "igdb_id"):
            return obj.igdb_id
        else:
            return obj.id


class IdSlugNameSerializer(IdNameSerializer):
    slug = serializers.CharField()


class IdCodeNameSerializer(IdNameSerializer):
    code = serializers.CharField()


game_fields = [
    "id",
    "decade_rank",
    "description",
    "studios",
    "genres",
    "igdb_artwork_id",
    "igdb_url",
    "name",
    "name_normalized",
    "platforms",
    "rank",
    "slug",
    "year_of_release",
    "year_rank",
]


class GameSummarySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="igdb_id")
    studios = IdNameSerializer(many=True)
    genres = IdNameSerializer(many=True)  # IGDB genres (not Wikipedia genres)
    platforms = IdCodeNameSerializer(many=True)
    # Delegate to primary_igdb_game_data
    igdb_artwork_id = serializers.SerializerMethodField()
    igdb_url = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = models.Game
        fields = game_fields

    def get_igdb_artwork_id(self, obj):
        """Get artwork_id from primary IGDBGameData record."""
        if obj.primary_igdb_game_data:
            return obj.primary_igdb_game_data.artwork_id
        return None

    def get_igdb_url(self, obj):
        """Get URL from primary IGDBGameData record."""
        if obj.primary_igdb_game_data:
            return obj.primary_igdb_game_data.url
        return None

    def get_description(self, obj):
        """Get description from primary IGDBGameData record."""
        if obj.primary_igdb_game_data:
            return obj.primary_igdb_game_data.description
        return None


class GameDetailSerializer(GameSummarySerializer):
    lists = serializers.SerializerMethodField()

    class Meta:
        model = models.Game
        fields = game_fields + ["lists"]

    def get_lists(self, obj):
        return obj.lists.order_by(
            "list__publisher__name",
            "list__year",
        ).values(
            "rank",
            name=F("list__name"),
            publication=F("list__publisher__name"),
            type=F("list__type"),
            url=F("list__url"),
            year=F("list__year"),
        )


class CompanySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="igdb_id")
    studios = IdNameSerializer(many=True)

    class Meta:
        model = models.Company
        fields = [
            "id",
            "name",
            "slug",
            "studios",
        ]


class StudioSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="igdb_id")
    games_count = serializers.IntegerField()
    company = IdSlugNameSerializer()

    class Meta:
        model = models.Studio
        fields = [
            "id",
            "name",
            "company",
            "games_count",
        ]


class ListSerializer(serializers.ModelSerializer):

    publication = serializers.CharField(source="publisher.name")

    class Meta:
        model = models.List
        fields = [
            "id",
            "name",
            "publication",
            "year",
            "type",
            "url",
        ]


class PublicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Publication
        fields = [
            "id",
            "name",
        ]


class PostSerializer(serializers.ModelSerializer):

    text = serializers.CharField(source="text_rendered")
    author = serializers.SerializerMethodField()

    class Meta:
        model = models.Post
        fields = [
            "id",
            "title",
            "text",
            "date",
            "active",
            "author",
        ]

    def get_author(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return None


class PageSerializer(serializers.ModelSerializer):

    content = serializers.SerializerMethodField()

    class Meta:
        model = FlatPage
        fields = [
            "id",
            "url",
            "title",
            "content",
        ]

    def get_content(self, obj: FlatPage):
        return markdown.markdown(obj.content)


class IGDBGenreSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.IGDBGenre
        fields = [
            "id",
            "name",
        ]


# Backward compatibility alias
GenreSerializer = IGDBGenreSerializer


class WikipediaGenreSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.WikipediaGenre
        fields = [
            "id",
            "name",
        ]


class PlatformSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Platform
        fields = [
            "id",
            "code",
            "name",
        ]

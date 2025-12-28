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
    """Basic Wikipedia genre serializer with hierarchy fields."""

    parent_id = serializers.IntegerField(source="parent.id", allow_null=True)

    class Meta:
        model = models.WikipediaGenre
        fields = [
            "id",
            "name",
            "slug",
            "level",
            "display_order",
            "path",
            "parent_id",
            "icon_name",
        ]


class WikipediaGenreTreeSerializer(serializers.ModelSerializer):
    """
    Wikipedia genre serializer with nested children for tree structure.

    Returns genres in a hierarchical format suitable for tree-based UI:
    {
        "id": 1,
        "name": "Action",
        "slug": "action",
        "level": 0,
        "children": [
            {"id": 2, "name": "Shooter", "slug": "shooter", "level": 1, "children": []},
            ...
        ]
    }
    """

    children = serializers.SerializerMethodField()
    game_count = serializers.SerializerMethodField()

    class Meta:
        model = models.WikipediaGenre
        fields = [
            "id",
            "name",
            "slug",
            "level",
            "display_order",
            "path",
            "icon_name",
            "children",
            "game_count",
        ]

    def get_children(self, obj):
        """Recursively serialize child genres."""
        children = obj.children.all().order_by("display_order", "name")
        return WikipediaGenreTreeSerializer(children, many=True).data

    def get_game_count(self, obj):
        """
        Get count of games with this genre.

        Note: For root categories, this includes games tagged with any
        descendant genre.
        """
        # Check if count was annotated on the queryset
        if hasattr(obj, "game_count_annotated"):
            return obj.game_count_annotated

        # Fallback to actual count
        return obj.games_with_wikipedia_genre.count()


class PlatformSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.Platform
        fields = [
            "id",
            "code",
            "name",
        ]


class DeveloperSearchSerializer(serializers.ModelSerializer):
    """Lightweight serializer for developer search results in nav dropdown."""

    company_slug = serializers.CharField(source="company.slug", allow_null=True)
    games_count = serializers.IntegerField()

    class Meta:
        model = models.Studio
        fields = [
            "id",
            "name",
            "company_slug",
            "games_count",
        ]

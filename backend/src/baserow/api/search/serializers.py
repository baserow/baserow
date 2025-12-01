from rest_framework import serializers

from baserow.api.search.constants import DEFAULT_SEARCH_LIMIT
from baserow.contrib.database.search.handler import ALL_SEARCH_MODES


class SearchQueryParamSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, default=None)
    search_mode = serializers.ChoiceField(
        required=False,
        default=None,
        choices=ALL_SEARCH_MODES,
    )


class WorkspaceSearchSerializer(serializers.Serializer):
    """Serializer for workspace search requests."""

    query = serializers.CharField(min_length=1, max_length=100)
    limit = serializers.IntegerField(
        default=DEFAULT_SEARCH_LIMIT,
        min_value=1,
        max_value=100,
        help_text="Maximum number of results per type",
    )
    offset = serializers.IntegerField(
        default=0, min_value=0, help_text="Number of results to skip"
    )


class SearchResultSerializer(serializers.Serializer):
    """Serializer for individual search results."""

    type = serializers.CharField()
    id = serializers.IntegerField()
    title = serializers.CharField()
    subtitle = serializers.CharField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_null=True)
    metadata = serializers.DictField(required=False, allow_null=True)
    created_on = serializers.CharField(required=False, allow_null=True)
    updated_on = serializers.CharField(required=False, allow_null=True)


class WorkspaceSearchResponseSerializer(serializers.Serializer):
    """Serializer for workspace search responses."""

    results = serializers.ListField(
        child=SearchResultSerializer(),
        help_text="Priority-ordered search results",
    )
    has_more = serializers.BooleanField(
        help_text="Whether there are more results available for pagination"
    )

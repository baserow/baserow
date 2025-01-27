from rest_framework import serializers

from baserow.contrib.builder.pages.constants import PAGE_PARAM_TYPE_CHOICES
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.validators import (
    path_param_name_validation,
    query_param_name_validation,
)


class PathParamSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=True,
        validators=[path_param_name_validation],
        help_text="The name of the parameter.",
        max_length=255,
    )
    type = serializers.ChoiceField(
        choices=PAGE_PARAM_TYPE_CHOICES, help_text="The type of the parameter."
    )


class QueryParamSerializer(serializers.Serializer):
    name = serializers.CharField(
        required=True,
        validators=[query_param_name_validation],
        help_text="The name of the parameter.",
        max_length=255,
    )
    type = serializers.ChoiceField(
        choices=PAGE_PARAM_TYPE_CHOICES, help_text="The type of the parameter."
    )


class PageSerializer(serializers.ModelSerializer):
    """
    👉 Mind to update the
    baserow.contrib.builder.api.domains.serializer.PublicPageSerializer
    when you update this one.
    """

    path_params = PathParamSerializer(many=True, required=False)
    query_params = QueryParamSerializer(many=True, required=False)

    class Meta:
        model = Page
        fields = (
            "id",
            "name",
            "path",
            "path_params",
            "order",
            "builder_id",
            "shared",
            "visibility",
            "role_type",
            "roles",
            "query_params",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "builder_id": {"read_only": True},
            "shared": {"read_only": True},
            "visibility": {"read_only": True},
            "role_type": {"read_only": True},
            "roles": {"read_only": True},
            "order": {"help_text": "Lowest first."},
        }


class CreatePageSerializer(serializers.ModelSerializer):
    path_params = PathParamSerializer(many=True, required=False)
    query_params = PathParamSerializer(many=True, required=False)

    class Meta:
        model = Page
        fields = ("name", "path", "path_params", "query_params")


class UpdatePageSerializer(serializers.ModelSerializer):
    path_params = PathParamSerializer(many=True, required=False)
    query_params = QueryParamSerializer(many=True, required=False)

    class Meta:
        model = Page
        fields = (
            "name",
            "path",
            "path_params",
            "visibility",
            "role_type",
            "roles",
            "query_params",
        )
        extra_kwargs = {
            "name": {"required": False},
            "path": {"required": False},
            "visibility": {"required": False},
            "role_type": {"required": False},
            "roles": {"required": False},
        }


class OrderPagesSerializer(serializers.Serializer):
    page_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="The ids of the pages in the order they are supposed to be set in",
    )

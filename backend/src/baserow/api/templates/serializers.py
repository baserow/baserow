from django.conf import settings

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.models import Template, TemplateCategory


class ListRequestQueryParamSerializer(serializers.Serializer):
    search = serializers.CharField(required=False)


class TemplateSerializer(serializers.ModelSerializer):
    is_default = serializers.SerializerMethodField(
        help_text="Indicates if the template must be selected by default. The "
        "web-frontend automatically selects the first `is_default` template "
        "that it can find."
    )

    class Meta:
        model = Template
        fields = (
            "id",
            "name",
            "slug",
            "icon",
            "keywords",
            "workspace_id",
            "is_default",
            "open_application",
        )

    @extend_schema_field(OpenApiTypes.STR)
    def get_is_default(self, instance):
        return instance.slug == settings.DEFAULT_APPLICATION_TEMPLATES[0]


class TemplateCategoriesSerializer(serializers.ModelSerializer):
    templates = TemplateSerializer(read_only=True, many=True)

    class Meta:
        model = TemplateCategory
        fields = ("id", "name", "templates")

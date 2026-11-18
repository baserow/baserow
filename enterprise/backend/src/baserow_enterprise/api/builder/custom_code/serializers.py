from typing import List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.builder.models import Builder
from baserow_enterprise.builder.custom_code.models import (
    BuilderCustomCode,
    BuilderCustomScript,
)


class CustomHtmlField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class CustomCodeSerializer(serializers.ModelSerializer):
    html = CustomHtmlField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        help_text="Custom HTML for the document head.",
    )

    class Meta:
        model = BuilderCustomCode
        fields = ["css", "js", "html"]


class PublicCustomCodeSerializer(serializers.ModelSerializer):
    has_html = serializers.SerializerMethodField(
        help_text="Whether the builder has custom HTML for the document head."
    )

    class Meta:
        model = BuilderCustomCode
        fields = ["css", "js", "has_html"]

    def get_has_html(self, instance: BuilderCustomCode) -> bool:
        return bool(instance.html)


class CustomHtmlSerializer(serializers.Serializer):
    html = serializers.CharField()


class CustomScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuilderCustomScript
        fields = ["id", "type", "url", "load_type", "crossorigin"]


class EnterpriseBuilderCustomCodeSerializer(serializers.Serializer):
    """
    This serializer adds the scripts
    """

    scripts = serializers.SerializerMethodField(
        help_text="Scripts to embed for this application"
    )

    class Meta:
        ref_name = "EnterpriseBuilderCustomCodeApplication"

    @extend_schema_field(CustomScriptSerializer(many=True))
    def get_scripts(self, instance: Builder) -> List:
        """
        Serializes the builder's scripts.

        :param instance: The builder instance.
        :return: A list of serialized scripts.
        """

        return CustomScriptSerializer(instance.scripts.all(), many=True).data

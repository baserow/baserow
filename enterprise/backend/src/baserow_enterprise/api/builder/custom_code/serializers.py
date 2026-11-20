from typing import List

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.contrib.builder.models import Builder
from baserow_enterprise.builder.custom_code.models import (
    BuilderCustomCode,
    BuilderCustomScript,
)


class CustomCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuilderCustomCode
        fields = ["css", "js"]


class CustomHtmlSerializer(serializers.Serializer):
    html = serializers.CharField(read_only=True)


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
    head_html = serializers.CharField(source="custom_code.html", read_only=True)
    has_head_html = serializers.SerializerMethodField()

    def get_has_head_html(self, instance: Builder) -> bool:
        return bool(instance.custom_code.html)

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

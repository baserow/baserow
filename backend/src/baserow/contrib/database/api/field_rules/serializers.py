from django.utils.functional import lazy

from rest_framework import serializers

from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.field_rules.registries import field_rules_type_registry


class RequestFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = (
            "is_active",
            "type",
        )

    type = serializers.ChoiceField(
        choices=lazy(field_rules_type_registry.get_types, list)(),
        help_text="The type of the field rule that must be created.",
        required=True,
    )


class RequestUpdateFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = (
            "is_active",
            "type",
        )

    type = serializers.ChoiceField(
        choices=lazy(field_rules_type_registry.get_types, list)(),
        help_text="The type of the field rule that must be created.",
        required=True,
    )


class ResponseFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = (
            "id",
            "table_id",
            "is_valid",
            "error_text",
            "is_active",
            "type",
        )
        read_only_fields = (
            "id",
            "table_id",
            "is_valid",
            "error_text",
            "is_active",
            "type",
        )

    type = serializers.ChoiceField(
        choices=lazy(field_rules_type_registry.get_types, list)(),
        help_text="The type of the field rule that must be created.",
        required=True,
    )


class InvalidRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = ("id",)
        read_only_fields = ("id",)

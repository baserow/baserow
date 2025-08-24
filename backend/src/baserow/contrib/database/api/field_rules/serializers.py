from rest_framework import serializers

from baserow.contrib.database.field_rules.models import FieldRule


class RequestFieldRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = ("is_active",)

    type = serializers.CharField(required=False, help_text="The type of the rule.")


class RequestUpdateFieldRuleSerializer(RequestFieldRuleSerializer):
    type = serializers.CharField(write_only=True, required=False)


class ResponseFieldRuleSerializer(RequestFieldRuleSerializer):
    class Meta:
        model = FieldRule
        fields = (
            "id",
            "table_id",
            "is_valid",
            "error_text",
            "is_active",
        )
        read_only_fields = (
            "id",
            "table_id",
            "is_valid",
            "error_text",
        )

    type = serializers.CharField(required=False, help_text="The type of the rule.")


class InvalidRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = ("id",)
        read_only_fields = ("id",)

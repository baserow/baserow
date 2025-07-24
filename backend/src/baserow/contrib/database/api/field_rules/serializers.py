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

    # id = serializers.IntegerField(read_only=True)
    # table_id = serializers.IntegerField(read_only=True)
    # is_valid = serializers.BooleanField(read_only=True)
    # error_text = serializers.CharField(read_only=True)

    type = serializers.CharField(required=False, help_text="The type of the rule.")


class InvalidRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldRule
        fields = ("id",)
        read_only_fields = ("id",)

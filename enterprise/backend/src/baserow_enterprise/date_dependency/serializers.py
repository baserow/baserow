from collections import defaultdict
from datetime import timedelta
from typing import Callable

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.api.field_rules.serializers import (
    RequestFieldRuleSerializer,
    ResponseFieldRuleSerializer,
)
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    DateField,
    DurationField,
    LinkRowField,
)
from baserow_enterprise.date_dependency.models import (
    DateDependency,
    DependencyBufferType,
    DependencyConnectionType,
    DependencyLinkrowType,
)


def _valid_duration_format(field: DurationField):
    if field.duration_format != "d h":
        raise ValidationError("Duration format must be 'd h'")
    return field


def _valid_date_field(field: DateField):
    if field.date_include_time:
        raise ValidationError("Date field must not include time")
    return field


def _check_self_reference(field: LinkRowField):
    if not field.is_self_referencing:
        raise ValidationError("Field should reference self")
    return


class RequestDateDependencySerializer(serializers.ModelSerializer):
    class Meta:
        model = DateDependency
        fields = RequestFieldRuleSerializer.Meta.fields + (
            "dependency_linkrow_role",
            "dependency_connection_type",
            "dependency_buffer",
            "dependency_buffer_type",
            "include_weekends",
        )

    start_date_field_id = serializers.IntegerField(
        required=True, help_text="Start date field id"
    )
    end_date_field_id = serializers.IntegerField(
        required=True, help_text="End date field id"
    )
    duration_field_id = serializers.IntegerField(
        required=True, help_text="Duration field id"
    )
    dependency_linkrow_field_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Linkrow field id to be used for dependent rows. This should point to the same table.",
    )
    dependency_linkrow_role = serializers.ChoiceField(
        required=False,
        choices=DependencyLinkrowType,
        help_text="Tells if linked rows are predecessors or successors of a row.",
    )
    dependency_connection_type = serializers.ChoiceField(
        required=False,
        choices=DependencyConnectionType,
        help_text="Describes which field from one row should affect which field in linked rows.",
    )
    dependency_buffer_type = serializers.ChoiceField(
        required=False,
        choices=DependencyBufferType,
        help_text="Describes how the buffer should behave: whether it should be flexible, keep its length, or be ignored.",
    )
    dependency_buffer = serializers.DurationField(
        required=False,
        allow_null=True,
        min_value=timedelta(seconds=0),
        help_text="Time buffer to be injected between dependent rows.",
    )
    include_weekends = serializers.BooleanField(
        required=False,
        allow_null=False,
        default=False,
        help_text="Indicates that if the end date is on weekend, it should be moved to the closest business day.",
    )

    def _validate_field(
        self, value: int, expected_type: str, *extra_checks: Callable
    ) -> int:
        table = self.context["table"]
        # This is a hack to avoid field validation if the whole rule is
        # disabled
        if self.initial_data.get("is_active") is False:
            return value
        try:
            field = FieldHandler().get_field(value).specific
        except FieldDoesNotExist:
            raise ValidationError("Field doesn't exist")

        if field.table_id != table.id:
            raise ValidationError("Field doesn't exist")
        if field.get_type().type != expected_type:
            raise ValidationError(f"Invalid field type")
        if field.read_only:
            raise ValidationError("Field cannot be read-only")
        for check in extra_checks:
            check(field)
        return value

    def validate_start_date_field_id(self, value):
        return self._validate_field(value, "date", _valid_date_field)

    def validate_end_date_field_id(self, value):
        return self._validate_field(value, "date", _valid_date_field)

    def validate_duration_field_id(self, value):
        return self._validate_field(value, "duration", _valid_duration_format)

    def validate_dependency_linkrow_field_id(self, value):
        if value is None:
            return

        val = self._validate_field(value, "link_row", _check_self_reference)
        return val

    def validate(self, attrs):
        error_dict = defaultdict(list)
        if attrs.get("is_active") is False:
            return attrs

        if (
            attrs.get("start_date_field_id") is not None
            and attrs.get("end_date_field_id") is not None
            and attrs.get("start_date_field_id") == attrs.get("end_date_field_id")
        ):
            error_dict["start_date_field_id"].append(
                "start date field should be different from end date field"
            )
            error_dict["end_date_field_id"].append(
                "end date field should be different from start date field"
            )

        if error_dict:
            raise ValidationError(error_dict)
        return attrs


class ResponseDateDependencySerializer(serializers.ModelSerializer):
    """
    Serializes inbound date dependency configuration. Requires `table` in the context.
    """

    class Meta:
        model = DateDependency
        fields = ResponseFieldRuleSerializer.Meta.fields + (
            "dependency_linkrow_role",
            "dependency_connection_type",
            "dependency_buffer",
            "dependency_buffer_type",
            "include_weekends",
        )

    start_date_field_id = serializers.IntegerField(
        required=True, help_text="Start date field id"
    )
    end_date_field_id = serializers.IntegerField(
        required=True, help_text="End date field id"
    )
    duration_field_id = serializers.IntegerField(
        required=True, help_text="Duration field id"
    )
    dependency_linkrow_field_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Linkrow field id to be used for dependent rows. This should point to the same table.",
    )
    dependency_linkrow_role = serializers.ChoiceField(
        required=False,
        choices=DependencyLinkrowType,
        help_text="Tells if linked rows are predecessors or successors of a row.",
    )
    dependency_connection_type = serializers.ChoiceField(
        required=False,
        choices=DependencyConnectionType,
        help_text="Describes which field from one row should affect which field in linked rows.",
    )
    dependency_buffer_type = serializers.ChoiceField(
        required=False,
        choices=DependencyBufferType,
        help_text="Describes how the buffer should behave: whether it should be flexible, keep its length, or be ignored.",
    )
    dependency_buffer = serializers.DurationField(
        required=False,
        allow_null=True,
        min_value=timedelta(seconds=0),
        help_text="Time buffer to be injected between dependent rows.",
    )
    include_weekends = serializers.BooleanField(
        required=False,
        allow_null=False,
        default=False,
        help_text="Indicates that if the end date is on weekend, it should be moved to the closest business day.",
    )

from collections import defaultdict
from typing import Callable

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    DateField,
    DurationField,
    LinkRowField,
)
from baserow.contrib.database.fields.registries import field_type_registry


def _valid_duration_format(field: DurationField):
    if field.duration_format != "d h":
        raise ValidationError("Duration format must be 'd h'")
    return field


def _valid_date_field(field: DateField):
    if field.date_include_time:
        raise ValidationError("Date field must not include time")
    return field


def _valid_linkrow_field(field: LinkRowField):
    if not field.is_self_referencing:
        raise ValidationError("Link row field should be self referencing")
    return field


class RequestDateDependencySerializer:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.initial_data and self.initial_data.get("is_active"):
            self.fields["start_date_field_id"].required = True
            self.fields["end_date_field_id"].required = True
            self.fields["duration_field_id"].required = True

    def _validate_field(
        self, value: int | None, expected_type: str, *extra_checks: Callable
    ) -> int:
        if value is None:
            return value
        table = self.context["table"]
        try:
            field_cls = field_type_registry.get(expected_type).model_class
            field = (
                FieldHandler()
                .get_field(
                    value,
                    field_cls,
                    base_queryset=field_cls.objects.select_related(
                        "table__database__workspace",
                        "content_type",
                    ),
                )
                .specific
            )
        except FieldDoesNotExist:
            raise ValidationError(code="missing", detail="Field doesn't exist")

        if field.table_id != table.id:
            raise ValidationError(
                code="invalid", detail="Field belongs to another table"
            )
        if field.get_type().type != expected_type:
            raise ValidationError(code="invalid", detail="Invalid field type")
        if field.read_only:
            raise ValidationError(code="invalid", detail="Field cannot be read-only")
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
        return self._validate_field(value, "link_row", _valid_linkrow_field)

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


class ResponseDateDependencySerializer:
    """
    Serializes inbound date dependency configuration. Requires `table` in the context.
    """

    start_date_field_id = serializers.IntegerField(
        required=True, help_text="Start date field id"
    )
    end_date_field_id = serializers.IntegerField(
        required=True, help_text="End date field id"
    )
    duration_field_id = serializers.IntegerField(
        required=True, help_text="Duration field id"
    )

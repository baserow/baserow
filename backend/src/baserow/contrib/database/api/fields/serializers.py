from datetime import timedelta
from typing import Optional

from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db.models.manager import BaseManager
from django.utils.functional import lazy

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from loguru import logger
from rest_framework import serializers
from rest_framework.serializers import SkipField, empty

from baserow.api.polymorphic import PolymorphicSerializer
from baserow.api.user_files.serializers import UserFileURLAndThumbnailsSerializerMixin
from baserow.api.user_files.validators import user_file_name_validator
from baserow.contrib.database.fields.constants import (
    BASEROW_BOOLEAN_FIELD_FALSE_VALUES,
    BASEROW_BOOLEAN_FIELD_TRUE_VALUES,
)
from baserow.contrib.database.fields.models import Field, FieldConstraint
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.fields.utils.duration import (
    postgres_interval_to_seconds,
    prepare_duration_value_for_db,
)
from baserow.core.utils import split_comma_separated_string


class FieldConstraintSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldConstraint
        fields = ("type_name",)


class FieldSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(help_text="The type of the related field.")
    read_only = serializers.SerializerMethodField(
        help_text="Indicates whether the field is a read only field. If true, "
        "it's not possible to update the cell value."
    )
    database_id = serializers.IntegerField(
        source="table.database_id",
        help_text="The ID of the database this field belongs to.",
        read_only=True,
    )
    workspace_id = serializers.IntegerField(
        source="table.database.workspace_id",
        help_text="The ID of the workspace this field belongs to.",
        read_only=True,
    )
    field_constraints = serializers.SerializerMethodField(
        help_text="The constraints applied to this field."
    )

    class Meta:
        model = Field
        fields = (
            "id",
            "table_id",
            "name",
            "order",
            "type",
            "primary",
            "read_only",
            "immutable_type",
            "immutable_properties",
            "description",
            "database_id",
            "workspace_id",
            "db_index",
            "field_constraints",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "table_id": {"read_only": True},
            "immutable_type": {"read_only": True},
            "immutable_properties": {"read_only": True},
            "description": {
                "required": False,
                "default": None,
                "allow_null": True,
                "allow_blank": True,
            },
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return field_type_registry.get_by_model(instance.specific_class).type

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_read_only(self, instance):
        return (
            field_type_registry.get_by_model(instance.specific_class).read_only
            or instance.read_only
        )

    def get_field_constraints(self, instance):
        """
        Returns the field constraints for the field.
        Handles cases where field_constraints is being accessed before the field is
        saved to the database.
        """

        try:
            constraints = instance.field_constraints.all()
            return FieldConstraintSerializer(constraints, many=True).data
        except (ValueError, TypeError):
            return []


class PolymorphicFieldSerializer(PolymorphicSerializer):
    """
    Polymorphic field serializer.
    """

    base_class = FieldSerializer
    registry = field_type_registry
    request = False


class RelatedFieldsSerializer(serializers.Serializer):
    related_fields = serializers.SerializerMethodField(
        help_text="A list of related fields which also changed.",
    )

    def __init__(self, *args, **kwargs):
        self.related_fields_list = kwargs.pop("related_fields", [])
        super().__init__(*args, **kwargs)

    @extend_schema_field(FieldSerializer(many=True))
    def get_related_fields(self, instance):
        return [
            field_type_registry.get_serializer(f, FieldSerializer).data
            for f in self.related_fields_list
        ]


class FieldSerializerWithRelatedFields(FieldSerializer, RelatedFieldsSerializer):
    class Meta(FieldSerializer.Meta):
        fields = FieldSerializer.Meta.fields + ("related_fields",)


class SelectOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    value = serializers.CharField(max_length=255, required=True)
    color = serializers.CharField(max_length=255, required=True)


class CreateFieldSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(field_type_registry.get_types, list)(), required=True
    )
    field_constraints = FieldConstraintSerializer(
        many=True, required=False, default=list
    )

    class Meta:
        model = Field
        fields = ("name", "type", "description", "db_index", "field_constraints")
        extra_kwargs = {
            "description": {
                "required": False,
                "default": None,
                "allow_null": True,
                "allow_blank": True,
            },
            "db_index": {"required": False},
        }


class UpdateFieldSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=lazy(field_type_registry.get_types, list)(), required=False
    )
    field_constraints = FieldConstraintSerializer(many=True, required=False)

    class Meta:
        model = Field
        fields = ("name", "type", "description", "db_index", "field_constraints")
        extra_kwargs = {
            "name": {"required": False},
            "description": {
                "required": False,
                "default": None,
                "allow_null": True,
                "allow_blank": True,
            },
            "db_index": {"required": False},
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Only include fields that were provided in the input data. This allows 'None'
        # if 'None' was explicitly set, but removes fields that weren't in input.
        # This is needed so that values are not accidentally overwritten if they're
        # not provided when updating the field.
        return {
            key: representation[key]
            for key in representation.keys()
            if key in self.initial_data
        }


class ArrayValueSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        read_only=True,
        required=False,
        help_text="The id of the row this value was looked up from.",
    )
    ids = serializers.DictField(
        child=serializers.IntegerField(
            read_only=True,
            required=False,
            help_text="The id of the row the value ultimately came from or the link "
            "row ids which led to the value.",
        ),
        read_only=True,
        required=False,
        help_text="If this value is a lookup crossing multiple link fields each link "
        "row id involved will be set in here.",
    )

    def __init__(self, child, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["value"] = child

    def to_representation(self, instance):
        # Note this is workaround for https://github.com/baserow/baserow/issues/4424
        # Once we have a proper way to handle this, we can remove this
        # and return the super().to_representation(instance) directly.
        try:
            return super().to_representation(instance)
        except Exception:
            logger.exception("Mismatch between field type and value type")
        return []


class LinkRowValueSerializer(serializers.Serializer):
    id = serializers.IntegerField(
        read_only=True,
        help_text="The unique identifier of the row in the related table.",
    )
    value = serializers.CharField(
        help_text="The primary field's value as a string of the row in the "
        "related table.",
        required=False,
        source="*",
    )
    order = serializers.DecimalField(
        max_digits=40,
        decimal_places=20,
        required=False,
    )


@extend_schema_field(OpenApiTypes.INT)
class IntegerOrStringField(serializers.Field):
    """
    A serializer field that accept an int or a string.
    """

    def __init__(self, **kwargs):
        required = kwargs.pop("required", False)
        allow_null = kwargs.pop("allow_null", True)
        allow_blank = kwargs.pop("allow_blank", allow_null)
        min_value = kwargs.pop("min_value", None)
        max_value = kwargs.pop("max_value", None)
        max_length = kwargs.pop("max_length", None)

        super().__init__(required=required, allow_null=allow_null, **kwargs)
        self._integer_field = serializers.IntegerField(
            **{
                "required": required,
                "allow_null": allow_null,
                "min_value": min_value,
                "max_value": max_value,
                **kwargs,
            }
        )
        self._char_field = serializers.CharField(
            **{
                "required": required,
                "allow_blank": allow_blank,
                "max_length": max_length,
                **kwargs,
            }
        )

    def to_internal_value(self, data):
        if isinstance(data, int) or data is None:
            return self._integer_field.to_internal_value(data)
        elif isinstance(data, str):
            return self._char_field.to_internal_value(data)
        else:
            raise serializers.ValidationError(
                "The provided value should be a valid integer or string",
                code="invalid",
            )

    def to_representation(self, value):
        return value


class LimitListSerializer(serializers.ListSerializer):
    def __init__(self, *args, **kwargs):
        self.limit = kwargs.pop("limit", None)
        super().__init__(*args, **kwargs)

    def to_representation(self, data):
        data = data.all() if isinstance(data, BaseManager) else data
        if self.limit is not None:
            data = data[: self.limit]
        return super().to_representation(data)


class FileFieldRequestSerializer(serializers.ListField):
    """
    A serializer field that accept a List or a CSV string that will be converted to
    an Array.
    """

    def to_internal_value(self, data):
        if not isinstance(data, (str, list)):
            raise serializers.ValidationError(
                "This value must be a list or a string.",
                code="not_a_list",
            )

        if not data:
            return []

        if isinstance(data, str):
            data = split_comma_separated_string(data)

        if any([not isinstance(i, type(data[0])) for i in data]):
            raise serializers.ValidationError(
                "All list values must be same type.", code="not_same_type"
            )

        if isinstance(data[0], str):
            [user_file_name_validator(name) for name in data]  # noqa W0106
            data = [{"name": name} for name in data]

        elif isinstance(data[0], dict):
            for val in data:
                name = val.get("name")
                if name is None:
                    raise serializers.ValidationError(
                        "A name property is required for all values of the list.",
                        code="required",
                    )
                user_file_name_validator(name)
        else:
            raise serializers.ValidationError(
                "The provided value should be a list of valid string or objects "
                "containing a value property.",
                code="invalid",
            )

        return super().to_internal_value(data)


class FileFieldResponseSerializer(
    UserFileURLAndThumbnailsSerializerMixin, serializers.Serializer
):
    visible_name = serializers.CharField()
    name = serializers.CharField()
    size = serializers.IntegerField()
    mime_type = serializers.CharField()
    is_image = serializers.BooleanField()
    image_width = serializers.IntegerField()
    image_height = serializers.IntegerField()
    uploaded_at = serializers.DateTimeField()

    def get_instance_attr(self, instance, name):
        return instance[name]


class LinkRowRequestSerializer(serializers.ListField):
    """
    A serializer field that accept a List or a CSV string that will be converted to
    an Array.
    """

    child = IntegerOrStringField()

    def to_internal_value(self, data):
        if not data:
            return []

        if isinstance(data, list):
            if any([not isinstance(i, type(data[0])) for i in data]):
                raise serializers.ValidationError(
                    "All list values must be same type.", code="not_same_type"
                )
            if not isinstance(data[0], (str, int)):
                raise serializers.ValidationError(
                    "The provided value must be a list of valid integer or string",
                    code="invalid",
                )

        elif isinstance(data, str):
            data = split_comma_separated_string(data)

        elif isinstance(data, int):
            data = [data]
        else:
            raise serializers.ValidationError(
                "This provided value must be a list, an integer or a string.",
                code="invalid",
            )

        return super().to_internal_value(data)


@extend_schema_field(OpenApiTypes.NONE)
class MustBeEmptyField(serializers.Field):
    def __init__(self, error_message, *args, **kwargs):
        def validator(value):
            raise ValidationError(error_message, code="invalid")

        kwargs["write_only"] = True
        kwargs["required"] = False
        kwargs["validators"] = [validator]
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        return None


class UniqueRowValueParamsSerializer(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False, help_text="Defines how many values should be returned."
    )
    split_comma_separated = serializers.BooleanField(
        required=False,
        help_text="Indicates whether the original column values must be splitted by "
        "comma.",
        default=False,
    )


class UniqueRowValuesSerializer(serializers.Serializer):
    values = serializers.ListSerializer(child=serializers.CharField())


class CollaboratorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="first_name", read_only=True)


class AvailableCollaboratorsSerializer(serializers.ListField):
    def __init__(self, **kwargs):
        kwargs["child"] = CollaboratorSerializer()
        kwargs["read_only"] = True
        kwargs["source"] = "*"
        kwargs["help_text"] = "A list of all the available collaborators."

        super().__init__(**kwargs)

    def get_attribute(self, instance):
        return super().get_attribute(instance)

    def to_representation(self, instance):
        field_type = instance.get_type()
        if not field_type.can_represent_collaborators(instance):
            return []

        workspace = instance.table.database.workspace
        if not hasattr(workspace, "available_collaborators"):
            setattr(
                workspace,
                "available_collaborators",
                workspace.users.order_by("first_name"),
            )

        return [
            CollaboratorSerializer(user).data
            for user in workspace.available_collaborators
        ]


class DuplicateFieldParamsSerializer(serializers.Serializer):
    duplicate_data = serializers.BooleanField(
        default=False, help_text="Indicates whether the data should be duplicated."
    )


class ChangePrimaryFieldParamsSerializer(serializers.Serializer):
    new_primary_field_id = serializers.IntegerField(
        help_text="The ID of the new primary field."
    )


class ListOrStringField(serializers.ListField):
    """
    A serializer field that accept a List or a CSV string that will be converted to
    an Array.
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            data = split_comma_separated_string(data)

        return super().to_internal_value(data)


class BaserowBooleanField(serializers.BooleanField):
    """
    A Baserow specific `BooleanField` that extends the `TRUE_VALUES` and
    `FALSE_VALUES` in DRF so that we support "checked" and "unchecked".
    """

    TRUE_VALUES = BASEROW_BOOLEAN_FIELD_TRUE_VALUES
    FALSE_VALUES = BASEROW_BOOLEAN_FIELD_FALSE_VALUES


@extend_schema_field(OpenApiTypes.FLOAT)
class DurationFieldSerializer(serializers.Field):
    """
    A serializer field that accept a float or a string and return a timedelta.
    """

    def __init__(self, duration_format, **kwargs):
        self.duration_format = duration_format
        super().__init__(**kwargs)

    def to_internal_value(self, data) -> Optional[timedelta]:
        return prepare_duration_value_for_db(
            data, self.duration_format, serializers.ValidationError
        )

    def to_representation(self, value):
        if isinstance(value, timedelta):
            return value.total_seconds()
        elif isinstance(value, str):
            # Durations are stored as strings in the postgres format for lookups/arrays
            # in formula land, so parse the string accordingly and return the value in
            # seconds.
            return postgres_interval_to_seconds(value)
        elif isinstance(value, (int, float)):
            # DEPRECATED: durations were stored as the number of seconds in formula
            # land, so just return the value in that case.
            return value
        else:
            raise ValueError("Invalid duration value.")


class PasswordSerializer(serializers.CharField):
    def run_validation(self, data=empty):
        if isinstance(data, bool) and data:
            raise SkipField()
        return super().run_validation(data=data)

    def to_internal_value(self, data) -> Optional[str]:
        if data is None or data == "":
            return None

        return make_password(data)


class LinkRowFieldSerializerMixin(serializers.ModelSerializer):
    link_row_table_primary_field = serializers.SerializerMethodField(
        help_text="The primary field of the table that is linked to."
    )

    def get_link_row_table_primary_field(self, instance):
        related_field = instance.link_row_table_primary_field
        if related_field is None:
            return None
        return field_type_registry.get_serializer(
            related_field.specific, FieldSerializer
        ).data


class PasswordFieldAuthenticationSerializer(serializers.Serializer):
    field_id = serializers.IntegerField(
        help_text="The field where to check the password for.",
        required=True,
    )
    row_id = serializers.IntegerField(
        help_text="The row where to check the password for.",
        required=True,
    )
    password = serializers.CharField(
        help_text="The password to check.",
        required=True,
    )


class PasswordFieldAuthenticationResponseSerializer(serializers.Serializer):
    is_correct = serializers.BooleanField(
        help_text="Indicates whether the provided password is correct.",
    )

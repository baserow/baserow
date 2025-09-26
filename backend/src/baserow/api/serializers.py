from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.relations import PrimaryKeyRelatedField

from baserow.core.context import clear_current_workspace_id, set_current_workspace_id
from baserow.core.storage import get_default_storage
from baserow.core.utils import split_comma_separated_string


def get_example_pagination_serializer_class(
    results_serializer_class,
    additional_fields=None,
    serializer_name=None,
):
    """
    Generates a pagination like response serializer that has the provided serializer
    class as results. It is only used for example purposes in combination with the
    openapi documentation.

    :param results_serializer_class: The serializer class that needs to be added as
        results.
    :type results_serializer_class: Serializer
    :param additional_fields: A dict containing additional fields that must be added
        to the serializer. The fields are going to be placed at the root of the
        serializer.
    :type additional_fields: dict
    :param serializer_name: The class name of the serializer. Generated serializer
        should be unique because serializer with the same class name are reused.
    :type serializer_name: str
    :return: The generated pagination serializer.
    :rtype: Serializer
    """

    fields = {
        "count": serializers.IntegerField(help_text="The total amount of results."),
        "next": serializers.URLField(
            allow_blank=True, allow_null=True, help_text="URL to the next page."
        ),
        "previous": serializers.URLField(
            allow_blank=True, allow_null=True, help_text="URL to the previous page."
        ),
        "results": results_serializer_class(many=True),
    }

    if additional_fields:
        fields.update(**additional_fields)

    if not serializer_name:
        serializer_name = "PaginationSerializer"

    return type(
        serializer_name + results_serializer_class.__name__,
        (serializers.Serializer,),
        fields,
    )


class NaturalKeyRelatedField(serializers.ListField):
    """
    A related field that use the natural key instead of the Id to reference the object.
    """

    def __init__(
        self, model=None, custom_does_not_exist_exception_class=None, **kwargs
    ):
        self._model = model
        self._custom_does_not_exist_exception_class = (
            custom_does_not_exist_exception_class
        )
        super().__init__(**kwargs)

    def to_representation(self, value):
        representation = super().to_representation(value.natural_key())

        if len(representation) == 1:
            return representation[0]
        else:
            return representation

    def to_internal_value(self, data):
        if not isinstance(data, list):
            data = [data]

        natural_key = super().to_internal_value(data)
        try:
            return self.get_queryset().get_by_natural_key(*natural_key)
        except self._model.DoesNotExist as e:
            if self._custom_does_not_exist_exception_class:
                raise self._custom_does_not_exist_exception_class(
                    f"Object with natural key {natural_key} for model {self._model} does not exist."
                )
            else:
                raise e

    def get_queryset(self):
        return self._model.objects


class CommaSeparatedIntegerValuesField(serializers.Field):
    """A serializer field that accepts a CSV string containing a list of integers."""

    def to_representation(self, value):
        return ",".join(value)

    def to_internal_value(self, data):
        record_ids = split_comma_separated_string(data)
        if not all([record.isdigit() for record in record_ids]):
            raise serializers.ValidationError("The provided record ids are not valid.")

        return record_ids


class FileURLSerializerMixin(serializers.Serializer):
    url = serializers.SerializerMethodField()

    def get_handler(self):
        """Define handler used for url generation.
        That handler needs to to implement method `export_file_path`.
        """

        raise NotImplementedError("Subclasses must implement this method.")

    def get_instance_attr(self, instance, name):
        return getattr(instance, name)

    @extend_schema_field(OpenApiTypes.URI)
    def get_url(self, instance):
        if hasattr(instance, "workspace_id"):
            # FIXME: Temporarily setting the current workspace ID for URL generation in
            # storage backends, enabling permission checks at download time.
            try:
                set_current_workspace_id(instance.workspace_id)
                return self._get_url(instance)
            finally:
                clear_current_workspace_id()
        else:
            return self._get_url(instance)

    def _get_exported_file_name(self, instance):
        return self.get_instance_attr(instance, "exported_file_name")

    def _get_url(self, instance):
        handler = self.get_handler()
        name = self._get_exported_file_name(instance)

        if not name:
            return None

        path = handler.export_file_path(name)
        storage = get_default_storage()
        return storage.url(path)


class NonValidatingPrimaryKeyRelatedField(PrimaryKeyRelatedField):
    def get_queryset(self):
        return None

    def to_representation(self, value):
        if isinstance(value, int):
            return value
        else:
            return value.pk

    def to_internal_value(self, data):
        try:
            return int(data)
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid ID: {data}")

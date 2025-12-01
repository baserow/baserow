from django.utils.functional import lazy

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.core.jobs.constants import (
    JOB_CANCELLED,
    JOB_FAILED,
    JOB_FINISHED,
    JOB_PENDING,
)
from baserow.core.jobs.models import Job
from baserow.core.jobs.registries import job_type_registry

VALID_JOB_STATES = [
    JOB_PENDING,
    JOB_FINISHED,
    JOB_FAILED,
    JOB_CANCELLED,
]


class JobSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField(help_text="The type of the job.")

    progress_percentage = serializers.IntegerField(
        source="get_cached_progress_percentage",
        help_text="A percentage indicating how far along the job is. 100 means "
        "that it's finished.",
    )
    state = serializers.CharField(
        source="get_cached_state",
        help_text="Indicates the state of the import job.",
    )

    class Meta:
        model = Job
        fields = (
            "id",
            "type",
            "progress_percentage",
            "state",
            "human_readable_error",
            "created_on",
            "updated_on",
        )
        extra_kwargs = {
            "id": {"read_only": True},
        }

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return job_type_registry.get_by_model(instance.specific_class).type


class CreateJobSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=lazy(job_type_registry.get_types, list)(),
        help_text="The type of the job.",
    )

    class Meta:
        model = Job
        fields = ("user_id", "type")


class JobTypeFiltersSerializer(serializers.Serializer):
    """
    Base serializer for job type-specific filters. This serves as the base class
    for all job type filter serializers and uses 'type' as a discriminator field.
    """

    type = serializers.ChoiceField(
        choices=lazy(job_type_registry.get_types, list)(),
        required=True,
        help_text="The type of job to filter for. Determines which additional filter fields are available.",
    )


class ListJobQuerySerializer(serializers.Serializer):
    states = serializers.CharField(required=False)
    job_ids = serializers.CharField(required=False)
    type = serializers.ChoiceField(
        choices=lazy(job_type_registry.get_types, list)(),
        required=False,
        help_text="The type of job to filter for. Determines which additional filter fields are available.",
    )
    offset = serializers.IntegerField(required=False, min_value=0)
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=100, default=20
    )

    def validate_states(self, value):
        if not value:
            return None

        states = value.split(",")
        for state in states:
            state = state[1:] if state.startswith("!") else state
            if state not in VALID_JOB_STATES:
                raise serializers.ValidationError(
                    f"State {state} is not a valid state."
                    f" Valid states are: {', '.join(VALID_JOB_STATES)}.",
                )
        return states

    def validate_job_ids(self, value):
        if not value:
            return None

        req_job_ids = value.split(",")
        validated_job_ids = []
        for job_id in req_job_ids:
            try:
                validated_job_ids.append(int(job_id))
            except ValueError:
                raise serializers.ValidationError(
                    f"Job id {job_id} is not a valid integer."
                )
        return validated_job_ids

    def validate(self, attrs):
        job_type_name = attrs.get("type")

        # Collect type-specific filters in a separate dict
        type_filters = {}

        if job_type_name:
            job_type = job_type_registry.get(job_type_name)
            filters_serializer_class = job_type.get_filters_serializer()

            if filters_serializer_class:
                filters_data = {}

                # Add any type-specific fields from initial_data
                filters_serializer = filters_serializer_class()

                for field_name in filters_serializer.fields.keys():
                    if field_name in self.initial_data:
                        filters_data[field_name] = self.initial_data[field_name]

                # Validate using the type-specific serializer
                filters_serializer = filters_serializer_class(data=filters_data)
                if filters_serializer.is_valid():
                    for field_name, value in filters_serializer.validated_data.items():
                        # if the field starts with the job_type name to disambiguate
                        # the query parameter, remove it
                        field_key = field_name
                        if field_name.startswith(f"{job_type.type}_"):
                            field_key = field_name[len(job_type.type) + 1 :]
                        type_filters[field_key] = value
                else:
                    raise serializers.ValidationError(filters_serializer.errors)

        # Add type_filters dict to attrs for easy access in the view
        attrs["type_filters"] = type_filters
        attrs["job_type_name"] = job_type_name

        return attrs


class ListJobQuerySerializerExtension(OpenApiSerializerExtension):
    """
    Custom OpenAPI serializer extension that dynamically adds type-specific filter
    fields to the ListJobQuerySerializer based on the job registry. This creates a flat
    parameter list where type-specific fields appear when the corresponding type is
    selected, since it's not possible to use a discriminator in query parameters.
    """

    target_class = "baserow.api.jobs.serializers.ListJobQuerySerializer"

    def map_serializer(self, auto_schema, direction):
        """
        Generate the schema by adding all type-specific fields from job filters
        serializers to the base ListJobQuerySerializer properties.
        """

        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True
        )

        properties = schema.get("properties", {})
        base_field_names = set(ListJobQuerySerializer().fields.keys())

        # Collect all type-specific fields from job registry
        for job_type in job_type_registry.get_all():
            filters_serializer_class = job_type.get_filters_serializer()
            if (
                not filters_serializer_class
                or filters_serializer_class == JobTypeFiltersSerializer
            ):
                continue

            serializer = force_instance(filters_serializer_class)

            for field_name, field in serializer.fields.items():
                # Skip base fields and the type field
                if field_name in base_field_names or field_name == "type":
                    continue

                field_schema = auto_schema._map_serializer_field(field, direction)

                help_text = field_schema.get("description", "")
                field_schema[
                    "description"
                ] = f"**[Only for type='{job_type.type}']** {help_text}"

                if field_name not in properties:
                    properties[field_name] = field_schema

        schema["properties"] = properties
        return schema

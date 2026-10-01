from rest_framework import serializers

from baserow.core.registries import subject_type_registry


class SubjectOptionsQueryParamsSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, required=False, default=1)
    size = serializers.IntegerField(min_value=1, max_value=100, required=False)
    search = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )
    workspace_id = serializers.IntegerField(min_value=1, required=False, default=None)
    subject_types = serializers.CharField(required=False, allow_blank=False)

    def validate_subject_types(self, value):
        """Parse and validate a comma-separated list of registered subject types."""

        requested_types = set(value.split(","))
        unknown_types = requested_types - set(subject_type_registry.get_types())
        if unknown_types:
            raise serializers.ValidationError(
                f"Unknown subject types: {', '.join(sorted(unknown_types))}."
            )
        return requested_types


class SubjectOptionSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    subject_id = serializers.IntegerField(read_only=True)
    subject_type = serializers.CharField(read_only=True)
    name = serializers.CharField(source="subject_name", read_only=True)
    label = serializers.CharField(source="subject_label", read_only=True)
    email = serializers.EmailField(
        source="subject_email", read_only=True, allow_null=True
    )
    subject_count = serializers.IntegerField(read_only=True, allow_null=True)

    def get_id(self, instance):
        return f"{instance['subject_type']}:{instance['subject_id']}"

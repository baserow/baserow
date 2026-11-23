from typing import Any

from django.utils.functional import lazy

from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from baserow.api.polymorphic import PolymorphicRequestSerializer, PolymorphicSerializer
from baserow.api.workspaces.serializers import WorkspaceSerializer
from baserow.core.db import specific_iterator
from baserow.core.models import Application
from baserow.core.registries import application_type_registry


class LastViewedField(serializers.DateTimeField):
    """
    Read from the per user context instead of the instance. Not a
    `SerializerMethodField` because read only fields are always documented as
    required, while responses that are not for a specific user leave the key out.
    """

    def __init__(self, **kwargs):
        super().__init__(required=False, allow_null=True, source="*", **kwargs)

    def to_representation(self, value):
        last_viewed = self.context.get("last_viewed_per_application", {}).get(value.id)
        return super().to_representation(last_viewed) if last_viewed else None


class PendingCountField(serializers.IntegerField):
    """
    Read from the per user context instead of the instance, for the same reason as
    `LastViewedField`.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        :param kwargs: The remaining field arguments, such as the help text.
        """

        super().__init__(required=False, source="*", **kwargs)

    def to_representation(self, value: Application) -> int:
        """
        :param value: The application being serialized.
        :return: How many things wait for the requesting user in it, 0 if unknown.
        """

        return self.context.get("pending_count_per_application", {}).get(value.id, 0)


class ApplicationSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    workspace = WorkspaceSerializer(
        help_text="The workspace that the application belongs to."
    )
    last_viewed = LastViewedField(
        help_text="When the requesting user last opened something in this "
        "application, or null if never. Only present in responses to a user."
    )
    pending_count = PendingCountField(
        help_text="How many things in this application wait for the requesting "
        "user to act, such as tool calls to approve. Only present in responses to "
        "a user."
    )

    class Meta:
        model = Application
        fields = (
            "id",
            "name",
            "order",
            "type",
            "workspace",
            "created_on",
            "last_viewed",
            "pending_count",
        )
        extra_kwargs = {"id": {"read_only": True}}

    @extend_schema_field(OpenApiTypes.STR)
    def get_type(self, instance):
        return application_type_registry.get_by_model(instance.specific_class).type

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Only the views that know the requesting user provide the values. Anything
        # else (realtime payloads, jobs) leaves the key out rather than sending a
        # `null` that would overwrite what the client already knows.
        if "last_viewed_per_application" not in self.context:
            data.pop("last_viewed", None)
        if "pending_count_per_application" not in self.context:
            data.pop("pending_count", None)
        return data


class PolymorphicApplicationResponseSerializer(PolymorphicSerializer):
    base_class = ApplicationSerializer
    registry = application_type_registry
    request = False


class PublicPolymorphicApplicationResponseSerializer(
    PolymorphicApplicationResponseSerializer
):
    name_prefix = "public_"
    extra_params = {"public": True}


def get_user_managed_application_types():
    """
    Returns the application types that people create and change through the API:
    every type but those Baserow keeps for a workspace, like the shared application
    that owns the workspace integrations.

    :return: The application types.
    """

    return [
        application_type
        for application_type in application_type_registry.get_all()
        if application_type.is_user_managed
    ]


class BaseApplicationCreatePolymorphicSerializer(serializers.ModelSerializer):
    # Lazy, so the types registered after this module is imported are included.
    type = serializers.ChoiceField(
        choices=lazy(
            lambda: [
                application_type.type
                for application_type in get_user_managed_application_types()
            ],
            list,
        )()
    )
    init_with_data = serializers.BooleanField(default=False)

    class Meta:
        model = Application
        fields = ("name", "type", "init_with_data")


class PolymorphicApplicationCreateSerializer(PolymorphicRequestSerializer):
    base_class = BaseApplicationCreatePolymorphicSerializer
    registry = application_type_registry

    @classmethod
    def get_request_types(cls):
        return get_user_managed_application_types()


class BaseApplicationUpdatePolymorphicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ("name",)


class PolymorphicApplicationUpdateSerializer(PolymorphicRequestSerializer):
    base_class = BaseApplicationUpdatePolymorphicSerializer
    registry = application_type_registry

    # Changing an application Baserow keeps for a workspace is refused, see
    # `ApplicationType.is_user_managed`.
    @classmethod
    def get_request_types(cls):
        return get_user_managed_application_types()


class OrderApplicationsSerializer(serializers.Serializer):
    application_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Application ids in the desired order.",
    )


class InstallTemplateJobApplicationsSerializer(serializers.JSONField):
    def to_representation(self, value):
        application_ids = super().to_representation(value)

        if not application_ids:
            return None

        applications = specific_iterator(
            Application.objects.select_related("content_type", "workspace").filter(
                pk__in=application_ids, workspace__trashed=False
            )
        )
        return PolymorphicApplicationResponseSerializer(applications, many=True).data

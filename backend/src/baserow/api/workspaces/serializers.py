from rest_framework import serializers

from baserow.api.mixins import UnknownFieldRaisesExceptionSerializerMixin
from baserow.api.validators import no_url_validation
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.models import Workspace

from .users.serializers import WorkspaceUserSerializer, WorkspaceUserWorkspaceSerializer

__all__ = [
    "WorkspaceUserWorkspaceSerializer",
    "WorkspaceSerializer",
    "OrderWorkspacesSerializer",
    "WorkspaceUserSerializer",
]


class WorkspaceSerializer(serializers.ModelSerializer):
    generative_ai_models_enabled = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = (
            "id",
            "name",
            "generative_ai_models_enabled",
        )
        extra_kwargs = {
            "id": {"read_only": True},
            "generative_ai_models_enabled": {"read_only": True},
            "name": {"validators": [no_url_validation]},
        }

    def get_generative_ai_models_enabled(self, object):
        """Serialize enabled generative AI models for a workspace.

        :param object: The workspace being serialized.
        :return: Enabled model identifiers grouped by provider type.
        """

        # Views serializing many workspaces load every scope up front, so this
        # does not resolve each of them separately.
        states = self.context.get("ai_provider_states") or {}
        return generative_ai_model_type_registry.get_enabled_models_per_type(
            object, state=states.get(getattr(object, "id", None))
        )


def get_generative_ai_settings_serializer(
    include_database_only_providers: bool = False,
):
    """Build a serializer for explicit generative AI provider settings.

    :param include_database_only_providers: Whether to include providers which cannot
        persist settings in the legacy workspace JSON field.
    :return: A serializer containing the providers allowed by the requested scope.
    """

    ai_model_types = {}
    for ai_model_type in generative_ai_model_type_registry.get_all():
        if (
            not include_database_only_providers
            and not ai_model_type.supports_legacy_workspace_settings
        ):
            continue
        settings_serializer = ai_model_type.get_settings_serializer()
        ai_model_types[ai_model_type.type] = settings_serializer(required=False)
    return type(
        "GenerativeAISettingsSerializer",
        (UnknownFieldRaisesExceptionSerializerMixin, serializers.Serializer),
        ai_model_types,
    )


class PermissionObjectSerializer(serializers.Serializer):
    name = serializers.CharField(help_text="The permission manager name.")
    permissions = serializers.JSONField(
        help_text="The content of the permission object for this permission manager."
    )


class OrderWorkspacesSerializer(serializers.Serializer):
    workspaces = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="Workspace ids in the desired order.",
    )

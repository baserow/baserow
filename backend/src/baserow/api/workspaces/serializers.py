from rest_framework import serializers

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
        }

    def get_generative_ai_models_enabled(self, object):
        return generative_ai_model_type_registry.get_enabled_models_per_type(object)


def get_generative_ai_settings_serializer():
    ai_model_types = {}
    for ai_model_type in generative_ai_model_type_registry.get_all():
        settings_serializer = ai_model_type.get_settings_serializer()
        ai_model_types[ai_model_type.type] = settings_serializer(required=False)
    return type(
        "GenerativeAISettingsSerializer",
        (serializers.Serializer,),
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

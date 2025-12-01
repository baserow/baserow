from baserow_premium.plugins import PremiumPlugin
from rest_framework import serializers

from baserow.api.workspaces.serializers import WorkspaceSerializer
from baserow.contrib.builder.api.serializers import BuilderSerializer
from baserow.core.registries import plugin_registry


class PublicWorkspaceSerializer(WorkspaceSerializer):
    licenses = serializers.SerializerMethodField()

    class Meta(WorkspaceSerializer.Meta):
        fields = WorkspaceSerializer.Meta.fields + ("licenses",)

    def get_licenses(self, object):
        all_licenses = set()
        license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin(
            cache_queries=True
        )
        license_types = list(
            license_plugin.get_active_instance_wide_license_types(None)
        ) + list(license_plugin.get_active_workspace_licenses(object))

        for license_type in license_types:
            all_licenses.add(license_type.type)

        return list(all_licenses)


class PremiumPublicBuilderSerializer(BuilderSerializer):
    """
    Change the workspace to add licences.
    """

    workspace = serializers.SerializerMethodField()

    class Meta:
        ref_name = "PremiumPublicBuilderApplication"

    def get_workspace(self, obj):
        return PublicWorkspaceSerializer(obj.get_workspace()).data

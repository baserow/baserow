from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from baserow_enterprise.assistant.plan_context import get_workspace_plan_tier


class TestWorkspacePlanTier:
    def test_get_workspace_plan_tier_returns_free_without_active_licenses(self):
        user = object()
        workspace = object()
        license_plugin = MagicMock()
        license_plugin.get_active_instance_wide_license_types.return_value = []
        license_plugin.get_active_workspace_licenses.return_value = []
        license_plugin.get_active_specific_licenses_only_for_workspace.return_value = []

        with patch(
            "baserow_enterprise.assistant.plan_context._get_license_plugin",
            return_value=license_plugin,
        ):
            assert get_workspace_plan_tier(user, workspace) == "free"

    def test_get_workspace_plan_tier_returns_highest_active_license(self):
        user = object()
        workspace = object()
        license_plugin = MagicMock()
        license_plugin.get_active_instance_wide_license_types.return_value = [
            SimpleNamespace(type="premium", order=10)
        ]
        license_plugin.get_active_workspace_licenses.return_value = []
        license_plugin.get_active_specific_licenses_only_for_workspace.return_value = [
            SimpleNamespace(type="advanced", order=75)
        ]

        with patch(
            "baserow_enterprise.assistant.plan_context._get_license_plugin",
            return_value=license_plugin,
        ):
            assert get_workspace_plan_tier(user, workspace) == "advanced"

    def test_get_workspace_plan_tier_normalizes_enterprise_without_support(self):
        user = object()
        workspace = object()
        license_plugin = MagicMock()
        license_plugin.get_active_instance_wide_license_types.return_value = []
        license_plugin.get_active_workspace_licenses.return_value = [
            SimpleNamespace(type="enterprise_without_support", order=100)
        ]
        license_plugin.get_active_specific_licenses_only_for_workspace.return_value = []

        with patch(
            "baserow_enterprise.assistant.plan_context._get_license_plugin",
            return_value=license_plugin,
        ):
            assert get_workspace_plan_tier(user, workspace) == "enterprise"

    def test_get_workspace_plan_tier_falls_back_to_free_on_errors(self):
        with patch(
            "baserow_enterprise.assistant.plan_context._get_license_plugin",
            side_effect=RuntimeError("license lookup failed"),
        ):
            assert get_workspace_plan_tier(object(), object()) == "free"

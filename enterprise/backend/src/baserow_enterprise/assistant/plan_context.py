from itertools import chain

from baserow.core.registries import plugin_registry
from baserow_premium.plugins import PremiumPlugin

FREE_PLAN_TIER = "free"
VALID_PLAN_TIERS = (FREE_PLAN_TIER, "premium", "advanced", "enterprise")


def _normalize_plan_tier(plan_tier: str) -> str:
    if plan_tier == "enterprise_without_support":
        return "enterprise"
    return plan_tier


def _get_license_plugin():
    return plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()


def get_workspace_plan_tier(user, workspace) -> str:
    """
    Return the active plan tier for the current user in the current workspace.

    The assistant only needs the highest-level tier that is relevant for the current
    chat context. Feature details remain in the knowledge base and should be resolved
    via docs search when needed.
    """

    try:
        license_plugin = _get_license_plugin()
        active_license_types = chain(
            license_plugin.get_active_instance_wide_license_types(user),
            license_plugin.get_active_workspace_licenses(workspace),
            license_plugin.get_active_specific_licenses_only_for_workspace(
                user, workspace
            ),
        )
        highest_plan = max(
            active_license_types,
            key=lambda license_type: license_type.order,
        )
    except Exception:
        return FREE_PLAN_TIER

    return _normalize_plan_tier(highest_plan.type)

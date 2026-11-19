from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import FeatureDisabledException
from baserow.core.registries import plugin_registry

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

FF_DASHBOARD_FILTERS = "dashboard-filters"
FF_ENABLE_ALL = "*"
FF_IDENTITIES = "identities"
FF_AGENT_BUILDER = "agent-builder"
FF_USER_TEMPLATES = "user_templates"
FF_RBAC_IMPROVEMENTS = "rbac_improvements"


def get_user_feature_flags(user: "AbstractUser | AnonymousUser | None") -> set[str]:
    """
    The feature flags the registered plugins grant to the user, lowercased. Empty
    for a signed out or unknown user.

    :param user: The user to get the granted feature flags for.
    :return: The lowercased names of the feature flags granted to the user.
    """

    if not isinstance(user, AbstractUser):
        return set()

    flags = {
        flag.lower()
        for plugin in plugin_registry.registry.values()
        for flag in plugin.get_user_feature_flags(user)
    }
    # Agents run as identities, so granting the agent builder must grant both.
    if FF_AGENT_BUILDER in flags:
        flags.add(FF_IDENTITIES)
    return flags


def feature_flag_is_enabled(
    feature_flag: str,
    user: "AbstractUser | AnonymousUser | None" = None,
    raise_if_disabled=False,
) -> bool:
    """
    Check if a specific feature flag is enabled for the instance or, when the user
    is given, granted to that user by a plugin.

    :param feature_flag: The name of the feature flag to check.
    :param user: The user the check is for. Without it only the instance is
        checked.
    :param raise_if_disabled: Whether to raise instead of returning False.
    :raises FeatureDisabledException: If the feature flag is disabled and
        `raise_if_disabled` is True.
    :return: True if the feature flag is enabled.
    """

    if FF_ENABLE_ALL in settings.FEATURE_FLAGS:
        return True
    flag = feature_flag.lower()
    is_enabled = flag in settings.FEATURE_FLAGS or flag in get_user_feature_flags(user)

    if not is_enabled and raise_if_disabled:
        raise FeatureDisabledException(
            f"The feature flag {feature_flag} is not enabled."
        )

    return is_enabled

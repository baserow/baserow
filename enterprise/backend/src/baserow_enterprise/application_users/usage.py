from typing import Optional, Tuple

from django.conf import settings

from baserow.core.models import Workspace
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.notification_types import (
    clear_application_user_threshold,
    notify_application_user_threshold,
)
from baserow_premium.application_user_usage.registries import (
    application_user_usage_provider_registry,
)


def _sorted_providers():
    return sorted(
        application_user_usage_provider_registry.get_all(),
        key=lambda provider: provider.order,
        reverse=True,
    )


def get_application_user_usage_and_limit(
    workspace: Workspace,
) -> Tuple[int, Optional[int]]:
    """
    Resolves the current application user usage and limit for the given workspace by
    asking the registered providers, highest order first. A limit of `None` means
    there is no enforced application user limit. This is used to drive the threshold
    notifications.

    :param workspace: The workspace to resolve the usage and limit for.
    :return: A `(usage, limit)` tuple.
    """

    for provider in _sorted_providers():
        result = provider.get_usage_and_limit(workspace)
        if result is not None:
            return result
    return 0, None


def get_application_user_login_limit(workspace: Workspace) -> Optional[int]:
    """
    Resolves the application user limit to enforce at login time for the given
    workspace by asking the registered providers, highest order first. Returns the
    first limit that a provider returns, or `None` when no provider enforces a hard
    login limit for the current deployment.

    :param workspace: The workspace the authenticating user belongs to.
    :return: The login limit, or `None`.
    """

    for provider in _sorted_providers():
        limit = provider.get_login_limit(workspace)
        if limit is not None:
            return limit
    return None


def check_application_user_limit(workspace: Workspace) -> None:
    """
    Sends an in-app notification to the workspace members when the application user
    usage reaches one of the configured warning thresholds or the limit itself
    (100%). Notifications are deduped per `(workspace, threshold)`, and cleared again
    when usage drops back below a threshold so that re-crossing it (e.g. after an
    upgrade then growth) notifies anew.

    :param workspace: The workspace to check.
    """

    usage, limit = get_application_user_usage_and_limit(workspace)
    if not limit:
        return

    # The limit itself is the 100% threshold, on top of the configured warnings.
    thresholds = [
        *settings.BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS,
        100,
    ]
    for threshold in thresholds:
        if usage >= limit * threshold / 100:
            notify_application_user_threshold(workspace, usage, limit, threshold)
        else:
            clear_application_user_threshold(workspace, threshold)


def notify_workspaces_approaching_application_user_limit() -> None:
    """
    Loops over every workspace that has at least one user source and notifies its
    members when it reaches a warning threshold or its application user limit. This is
    meant to be called after the application user counts have been refreshed so that
    application users added directly (e.g. as table rows) are also taken into account.
    """

    workspace_ids = (
        UserSource.objects.values_list("application__workspace_id", flat=True)
        .order_by("application__workspace_id")
        .distinct()
    )
    for workspace in Workspace.objects.filter(id__in=workspace_ids):
        check_application_user_limit(workspace)


def raise_if_over_application_user_login_limit(user_source: UserSource, user) -> None:
    """
    Raises `ApplicationUserLimitReached` when the given user isn't allowed to
    authenticate because the workspace enforces an application user login limit and
    the user is past it, i.e. not amongst the first `limit` users (ordered by
    creation) of the user source.

    :param user_source: The user source the user is authenticating against.
    :param user: The authenticated `UserSourceUser`.
    :raises ApplicationUserLimitReached: When the user is past the limit.
    """

    # Soft limit (the default): the limit is only used to notify workspace members,
    # nobody is blocked from signing in. The hard limit is opt-in via an env var.
    if not settings.BASEROW_APPLICATION_USER_LIMIT_ENFORCED:
        return

    workspace = user_source.application.workspace
    if workspace is None:
        return

    limit = get_application_user_login_limit(workspace)
    if limit is None:
        return

    position = user_source.get_type().get_user_position(user_source, user)
    if position is not None and position > limit:
        raise ApplicationUserLimitReached(
            "The application user limit has been reached."
        )

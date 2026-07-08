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


def raise_if_over_application_user_login_limit(user_source: UserSource) -> None:
    """
    Raises ApplicationUserLimitReached when logins to the given user source's
    workspace aren't allowed because a provider that enforces a hard application user
    login limit considers the workspace over it.

    When a workspace is over its limit, all of its logins are refused (not just the
    users past the limit).

    The over-limit decision is delegated to the registered providers (highest order
    first): the first provider that returns a non-None verdict decides. A provider
    returning None doesn't enforce a hard login limit for the current deployment, so
    the next provider is consulted; when none do, the login is allowed.

    :param user_source: The user source the user is authenticating against.
    :raises ApplicationUserLimitReached: When a provider considers the workspace over
        the limit.
    """

    # Soft limit: the limit is only used to notify workspace members and nobody
    # is blocked from signing in.
    if not settings.BASEROW_APPLICATION_USER_LIMIT_ENFORCED:
        return

    workspace = user_source.application.workspace
    for provider in _sorted_providers():
        over_limit = provider.is_over_login_limit(workspace)
        if over_limit is None:
            continue
        if over_limit:
            raise ApplicationUserLimitReached(
                "The application user limit has been reached."
            )
        return

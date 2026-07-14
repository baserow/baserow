from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.utils.timezone import now

from baserow.core.models import Workspace
from baserow.core.registries import plugin_registry
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.models import ApplicationUserOverLimit
from baserow_enterprise.application_users.notification_types import (
    clear_application_user_threshold,
    notify_application_user_threshold,
)
from baserow_premium.plugins import PremiumPlugin


def get_application_user_usage_and_limit(
    workspace: Workspace,
) -> Tuple[int, Optional[int]]:
    """
    Resolves the current application user usage and limit for the given workspace by
    asking the license plugin of the current deployment (a per-workspace quota for
    SaaS, an instance-wide license value for self-hosted). A limit of `None` means
    there is no enforced application user limit. This is used to drive the threshold
    notifications.

    :param workspace: The workspace to resolve the usage and limit for.
    :return: A `(usage, limit)` tuple.
    """

    license_plugin = plugin_registry.get_by_type(PremiumPlugin).get_license_plugin()
    result = license_plugin.get_application_user_usage_and_limit_for_workspace(
        workspace
    )
    if result is None:
        return 0, None
    return result


def check_application_user_limit(workspace: Workspace) -> None:
    """
    Sends an in-app notification to the workspace members when the application user
    usage reaches one of the configured warning thresholds or the limit itself
    (100%). Notifications are deduped per `(workspace, threshold)`, and cleared again
    when usage drops back below a threshold so that re-crossing it (e.g. after an
    upgrade then growth) notifies anew. Also stamps or clears the moment the
    workspace went over its limit, which drives the login enforcement grace period.

    :param workspace: The workspace to check.
    """

    usage, limit = get_application_user_usage_and_limit(workspace)
    update_application_user_over_limit_state(workspace, usage, limit)
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


def update_application_user_over_limit_state(
    workspace: Workspace, usage: int, limit: Optional[int]
) -> None:
    """
    Stamps the moment the workspace went over its application user limit, or clears
    it again once usage is back within the limit (or no limit resolves anymore, e.g.
    after a license upgrade). Repeated calls while the workspace stays over its limit
    keep the original timestamp, so the grace period isn't restarted. The timestamp
    drives the grace period before logins are refused when the limit is enforced.

    :param workspace: The workspace to update the over limit state for.
    :param usage: The current application user usage.
    :param limit: The current application user limit, or `None` when there is none.
    """

    if limit is not None and usage > limit:
        ApplicationUserOverLimit.objects.get_or_create(
            workspace=workspace, defaults={"since": now()}
        )
    else:
        ApplicationUserOverLimit.objects.filter(workspace=workspace).delete()


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
    workspace aren't allowed because the workspace has been over its application
    user limit for longer than the configured grace period.

    When a workspace is over its limit, all of its logins are refused (not just the
    users past the limit). When no limit resolves for the workspace (e.g. an
    unlicensed install, or a pre v1.32 license without an `application_users`
    field), the login is allowed.

    :param user_source: The user source the user is authenticating against.
    :raises ApplicationUserLimitReached: When the workspace has been over the limit
        for longer than the grace period.
    """

    # Soft limit: the limit is only used to notify workspace members and nobody
    # is blocked from signing in.
    if not settings.BASEROW_APPLICATION_USER_LIMIT_ENFORCED:
        return

    workspace = user_source.application.workspace

    # The periodic user source count stamps the moment a workspace goes over its
    # limit. Only refuse logins when that happened longer than the grace period
    # ago, so the workspace has time to upgrade or reduce its usage first. This is
    # a single cheap query on the login path.
    grace_period_cutoff = now() - timedelta(
        hours=settings.BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS
    )
    over_limit_past_grace_period = ApplicationUserOverLimit.objects.filter(
        workspace=workspace, since__lt=grace_period_cutoff
    ).exists()
    if not over_limit_past_grace_period:
        return

    # The workspace might have upgraded or reduced its usage since the periodic
    # count last ran, so double check the actual usage on the spot before refusing
    # the login.
    usage, limit = get_application_user_usage_and_limit(workspace)
    if limit is not None and usage > limit:
        raise ApplicationUserLimitReached(
            "The application user limit has been reached."
        )

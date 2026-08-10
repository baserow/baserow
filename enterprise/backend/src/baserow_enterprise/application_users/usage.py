import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now

from baserow.core.cache import global_cache
from baserow.core.models import Workspace
from baserow.core.registries import plugin_registry
from baserow.core.user_sources.models import UserSource
from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.notification_types import (
    clear_application_user_threshold,
    notify_application_user_threshold,
)
from baserow_premium.plugins import PremiumPlugin

logger = logging.getLogger(__name__)

OVER_LIMIT_CACHE_KEY_PREFIX = "application_user_over_limit"

# The over limit moment is re-stamped by the hourly `check_application_user_limits`
# task, so this only has to outlive a couple of missed runs. It also makes sure the
# key of a workspace that no longer exists eventually disappears by itself.
OVER_LIMIT_CACHE_TIMEOUT = 60 * 60 * 24  # 1 day


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
    return license_plugin.get_application_user_usage_and_limit_for_workspace(workspace)


def check_application_user_limit(workspace: Workspace) -> None:
    """
    Sends an in-app notification to the workspace admins when the application user
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


def get_over_limit_cache_key(workspace_id: int) -> str:
    return f"{OVER_LIMIT_CACHE_KEY_PREFIX}_{workspace_id}"


def get_application_user_over_limit_since(
    workspace: Workspace,
) -> Optional[datetime]:
    """
    Returns the moment the workspace was first detected to be over its application
    user limit, or `None` when it isn't over its limit as far as we know.

    See `update_application_user_over_limit_state` for why this is best effort.

    :param workspace: The workspace to get the over limit moment of.
    :return: The over limit moment, or `None`.
    """

    since = global_cache.get(
        get_over_limit_cache_key(workspace.id),
        default=None,
        timeout=OVER_LIMIT_CACHE_TIMEOUT,
    )
    return parse_datetime(since) if since else None


def update_application_user_over_limit_state(
    workspace: Workspace, usage: int, limit: Optional[int]
) -> None:
    """
    Stamps the moment the workspace went over its application user limit, or clears
    it again once usage is back within the limit (or no limit resolves anymore, e.g.
    after a license upgrade). Repeated calls while the workspace stays over its limit
    keep the original timestamp, so the grace period isn't restarted. The timestamp
    drives the grace period before logins are refused when the limit is enforced.

    This is deliberately kept in the cache rather than the database, so it is best
    effort: losing it (a flush, an eviction, the version bump that comes with a new
    release) restarts the grace period of a workspace that is still over its limit.
    That only ever grants a workspace more time, never less, and the login check
    re-resolves the real usage before refusing anything, so the stamp is a timer and
    not the authority on whether the limit is exceeded.

    :param workspace: The workspace to update the over limit state for.
    :param usage: The current application user usage.
    :param limit: The current application user limit, or `None` when there is none.
    """

    cache_key = get_over_limit_cache_key(workspace.id)

    if limit is None or usage <= limit:
        global_cache.invalidate(cache_key)
        return

    def stamp_over_limit_moment(since: Optional[str]) -> str:
        # Keep the original moment on repeated calls, so a workspace that stays over
        # its limit doesn't get its grace period restarted every run.
        if since is not None:
            return since
        # Logged because the stamp is otherwise invisible, and it's what a support
        # request about a refused login needs to be answered.
        logger.info(
            "Workspace %s went over its application user limit (%s/%s).",
            workspace.id,
            usage,
            limit,
        )
        return now().isoformat()

    # `update` does the read-modify-write under a lock, so overlapping runs can't each
    # stamp a different moment.
    global_cache.update(
        cache_key,
        stamp_over_limit_moment,
        default_value=None,
        timeout=OVER_LIMIT_CACHE_TIMEOUT,
    )


def notify_workspaces_approaching_application_user_limit() -> None:
    """
    Loops over every workspace that has at least one user source and notifies its
    admins when it reaches a warning threshold or its application user limit. This is
    driven by the `check_application_user_limits` periodic task, which runs
    independently of the licenses because unlicensed installs have a limit too. It
    reads the user source counts that are periodically refreshed by
    `count_all_user_source_users`, so that application users added directly (e.g.
    as table rows) are also taken into account.
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
    users past the limit). Every workspace resolves a limit, so being unlicensed is
    not a way around this: it resolves the default application user limit instead.

    :param user_source: The user source the user is authenticating against.
    :raises ApplicationUserLimitReached: When the workspace has been over the limit
        for longer than the grace period.
    """

    # Soft limit: the limit is only used to notify workspace admins and nobody
    # is blocked from signing in.
    if not settings.BASEROW_APPLICATION_USER_LIMIT_ENFORCED:
        return

    # A published app's application has no workspace of its own, so resolve the
    # workspace it was published from. That's where the limit is enforced and where
    # the periodic check stamps the over limit moment.
    workspace = user_source.application.specific.get_workspace()

    # The periodic application user limit check stamps the moment a workspace goes
    # over its limit. Only refuse logins when that happened longer than the grace period
    # ago, so the workspace has time to upgrade or reduce its usage first. This is
    # a cheap cache read on the login path.
    over_limit_since = get_application_user_over_limit_since(workspace)
    if over_limit_since is None:
        return

    grace_period_cutoff = now() - timedelta(
        hours=settings.BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS
    )
    if over_limit_since >= grace_period_cutoff:
        return

    # The workspace might have upgraded or reduced its usage since the periodic
    # count last ran, so double check the actual usage on the spot before refusing
    # the login.
    usage, limit = get_application_user_usage_and_limit(workspace)
    if limit is not None and usage > limit:
        raise ApplicationUserLimitReached()

from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils.timezone import now

import pytest
from baserow_premium_tests.fixtures import VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE
from celery.exceptions import SoftTimeLimitExceeded

from baserow.core.cache import global_cache, local_cache
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.registries import plugin_registry
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.notification_types import (
    ApplicationUserLimitNotificationType,
)
from baserow_enterprise.application_users.tasks import check_application_user_limits
from baserow_enterprise.application_users.usage import (
    get_application_user_over_limit_since,
    get_over_limit_cache_key,
    raise_if_over_application_user_login_limit,
    update_application_user_over_limit_state,
)
from baserow_premium.application_user_usage.constants import (
    DEFAULT_APPLICATION_USERS_LIMIT,
)
from baserow_premium.application_user_usage.utils import (
    INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY,
)
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.plugins import PremiumPlugin

OVER_THE_LICENSE_LIMIT = 11
OVER_THE_DEFAULT_LIMIT = DEFAULT_APPLICATION_USERS_LIMIT + 1


@pytest.fixture(autouse=True)
def self_hosted_license_plugin():
    """
    These tests cover the self-hosted resolution where the application user limit
    comes from the registered licenses. Under the SaaS settings the premium plugin
    resolves a per-workspace subscription quota instead, so force the self-hosted
    license plugin to keep the tests deterministic in both environments.
    """

    premium_plugin = plugin_registry.get_by_type(PremiumPlugin)
    with patch.object(
        premium_plugin,
        "get_license_plugin",
        lambda cache_queries=False: LicensePlugin(cache_queries),
    ):
        yield


class PerWorkspaceLicensePlugin(LicensePlugin):
    """
    A license plugin whose application user limit is per workspace, like the SaaS
    one, as far as the periodic check is concerned: only the workspaces with
    application users of their own (a published user source) are checked, and the
    notification talks about the workspace rather than the instance.
    """

    def is_application_user_limit_instance_wide(self):
        return False


@contextmanager
def per_workspace_license_plugin():
    premium_plugin = plugin_registry.get_by_type(PremiumPlugin)
    with patch.object(
        premium_plugin,
        "get_license_plugin",
        lambda cache_queries=False: PerWorkspaceLicensePlugin(cache_queries),
    ):
        yield


def publish(data_fixture, builder):
    """
    Publishes the builder by pointing a domain of it to a published copy. Only the
    user sources of published applications count towards the application user usage,
    so the periodic check only checks the workspaces that have one.
    """

    return data_fixture.create_builder_custom_domain(
        builder=builder,
        published_to=data_fixture.create_builder_application(workspace=None),
    )


def mark_over_limit_since(user_source, since):
    workspace = user_source.application.specific.get_workspace()
    global_cache.update(
        get_over_limit_cache_key(workspace.id), lambda _: since.isoformat()
    )


def is_marked_over_limit(workspace):
    return get_application_user_over_limit_since(workspace) is not None


def expire_instance_wide_count_cache():
    """
    The instance wide application user count is cached for less than the interval of
    the periodic check, so every run of it resolves the count anew. Tests that run the
    check more than once with a changed usage have to expire that cache themselves,
    because they don't wait for the timeout.
    """

    global_cache.invalidate(INSTANCE_WIDE_APPLICATION_USER_COUNT_CACHE_KEY)


@pytest.fixture
def user_source(data_fixture):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(workspace=workspace)
    return data_fixture.create_local_baserow_table_user_source(application=builder)


@pytest.mark.django_db
@override_settings(
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_unlicensed_within_the_default_limit(
    mock_aggregate_user_source_counts, user_source
):
    mock_aggregate_user_source_counts.return_value = DEFAULT_APPLICATION_USERS_LIMIT
    mark_over_limit_since(user_source, now() - timedelta(hours=2))

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_refused_when_unlicensed_over_the_default_limit(
    mock_aggregate_user_source_counts, user_source
):
    # Being unlicensed is not a way around the limit: the default one applies.
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    mark_over_limit_since(user_source, now() - timedelta(hours=2))

    with pytest.raises(ApplicationUserLimitReached):
        raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_refused_over_the_default_limit_when_no_license_carries_one(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    # The default fixture license predates v1.32, so it carries no
    # `application_users` even though it is active. That grants no application user
    # capacity of its own, so the default limit applies.
    premium_data_fixture.create_premium_license()
    mark_over_limit_since(user_source, now() - timedelta(hours=2))

    with pytest.raises(ApplicationUserLimitReached):
        raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_the_usage_is_within_the_license_limit(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 10
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_refused_when_over_the_license_limit_past_the_grace_period(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    mark_over_limit_since(user_source, now() - timedelta(hours=2))

    with pytest.raises(ApplicationUserLimitReached):
        raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_over_the_license_limit_within_the_grace_period(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    mark_over_limit_since(user_source, now() - timedelta(minutes=30))

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_the_periodic_count_has_not_detected_the_overrun_yet(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    # The workspace is over its limit, but no over limit moment has been stamped
    # yet, so the grace period hasn't started.
    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_past_the_grace_period_when_the_usage_dropped_meanwhile(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 10
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    # The stale over limit moment hasn't been cleared by the periodic count yet,
    # but the live usage check sees the workspace is back within its limit.
    mark_over_limit_since(user_source, now() - timedelta(hours=2))

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_refused_over_the_limit_when_logging_into_a_published_app(
    mock_aggregate_user_source_counts, data_fixture, premium_data_fixture
):
    # A published app's application has no workspace of its own, so the login limit
    # check has to resolve the workspace it was published from instead of reading a
    # `None` workspace off the published application.
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(workspace=workspace)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    published_user_source = data_fixture.create_local_baserow_table_user_source(
        application=published_builder
    )
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    mark_over_limit_since(published_user_source, now() - timedelta(hours=2))

    with pytest.raises(ApplicationUserLimitReached):
        raise_if_over_application_user_login_limit(published_user_source)


@pytest.mark.django_db
def test_update_application_user_over_limit_state(data_fixture):
    workspace = data_fixture.create_workspace()

    # Within the limit: nothing is stamped.
    update_application_user_over_limit_state(workspace, usage=10, limit=10)
    assert not is_marked_over_limit(workspace)

    # Over the limit: the moment is stamped.
    update_application_user_over_limit_state(workspace, usage=11, limit=10)
    since = get_application_user_over_limit_since(workspace)
    assert since is not None

    # Still over the limit: the original moment is kept so the grace period
    # isn't restarted.
    update_application_user_over_limit_state(workspace, usage=12, limit=10)
    assert get_application_user_over_limit_since(workspace) == since

    # Back within the limit: the moment is cleared again.
    update_application_user_over_limit_state(workspace, usage=10, limit=10)
    assert not is_marked_over_limit(workspace)

    # No limit resolves anymore (e.g. a license upgrade): also cleared.
    update_application_user_over_limit_state(workspace, usage=11, limit=10)
    update_application_user_over_limit_state(workspace, usage=11, limit=None)
    assert not is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[80])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_notifies_workspace_admins_over_the_application_user_limit(
    mock_aggregate_user_source_counts,
    data_fixture,
    premium_data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    data_fixture.create_user_workspace(
        user=member, workspace=workspace, permissions="MEMBER"
    )
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    # The premium license carries the application user limit of 10.
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    with django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert sorted(n.data["threshold"] for n in notifications) == [80, 100]
    # Only the workspace admins are notified, because they are the ones who can
    # act on the limit. Regular members don't receive the notification.
    recipient_ids = set(
        NotificationRecipient.objects.filter(
            notification__in=notifications
        ).values_list("recipient_id", flat=True)
    )
    assert recipient_ids == {admin.id}
    assert is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[80])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_notifies_an_unlicensed_install_over_the_default_limit(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    # An unlicensed install runs no license check at all, so the notifications have
    # to come from the periodic application user check instead.
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    with django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert sorted(n.data["threshold"] for n in notifications) == [80, 100]
    assert notifications[0].data["limit"] == DEFAULT_APPLICATION_USERS_LIMIT
    assert is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[80])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_clears_notifications_when_the_usage_drops_again(
    mock_aggregate_user_source_counts,
    data_fixture,
    premium_data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    # Every task run gets its own local cache context, like celery gives it.
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    assert (
        Notification.objects.filter(
            type=ApplicationUserLimitNotificationType.type, workspace=workspace
        ).count()
        == 2
    )
    assert is_marked_over_limit(workspace)

    # The usage drops back under the limit, so the next check clears the
    # notifications and the over limit state again, and crossing the limit later
    # notifies anew.
    mock_aggregate_user_source_counts.return_value = 5
    expire_instance_wide_count_cache()
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    assert not Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    ).exists()
    assert not is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[80])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_does_not_duplicate_notifications_while_still_over_limit(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    since_after_first_run = get_application_user_over_limit_since(workspace)
    assert since_after_first_run is not None

    # A second run while the workspace is still over its limit must not create
    # duplicate notifications (they are deduped per workspace and threshold), nor
    # restart the grace period.
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert sorted(n.data["threshold"] for n in notifications) == [80, 100]
    assert get_application_user_over_limit_since(workspace) == since_after_first_run


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[80])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_only_clears_the_thresholds_the_usage_dropped_below(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert sorted(n.data["threshold"] for n in notifications) == [80, 100]
    first_100_notification_id = notifications.get(data__contains={"threshold": 100}).id

    # The usage drops below the limit but stays above the 80% warning threshold:
    # only the 100% notification is cleared, and the workspace is no longer marked
    # over its limit.
    mock_aggregate_user_source_counts.return_value = int(
        DEFAULT_APPLICATION_USERS_LIMIT * 0.9
    )
    expire_instance_wide_count_cache()
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert [n.data["threshold"] for n in notifications] == [80]
    assert not is_marked_over_limit(workspace)

    # Crossing the limit again notifies anew for the cleared threshold, because
    # clearing it re-armed the dedup.
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    expire_instance_wide_count_cache()
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notifications = Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert sorted(n.data["threshold"] for n in notifications) == [80, 100]
    new_100_notification_id = notifications.get(data__contains={"threshold": 100}).id
    assert new_100_notification_id != first_100_notification_id


@pytest.mark.parametrize(
    "threshold,instance_wide,expected_title",
    [
        (100, False, "Application user limit reached"),
        (80, False, "8 of 10 application users used"),
        (100, True, "Application user limit of the instance reached"),
        (80, True, "8 of 10 application users of the instance used"),
    ],
)
def test_application_user_limit_notification_title(
    threshold, instance_wide, expected_title
):
    notification = Notification(
        data={
            "threshold": threshold,
            "usage": 8,
            "limit": 10,
            "instance_wide": instance_wide,
        }
    )
    assert (
        ApplicationUserLimitNotificationType.get_notification_title(notification)
        == expected_title
    )


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_notification_data_contract(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    # The frontend renders the notification from this data, so its keys are part
    # of the contract.
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notification = Notification.objects.get(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )
    assert notification.data == {
        "workspace_id": workspace.id,
        "workspace_name": workspace.name,
        "threshold": 100,
        "usage": OVER_THE_DEFAULT_LIMIT,
        "limit": DEFAULT_APPLICATION_USERS_LIMIT,
        "instance_wide": True,
    }


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_skips_workspaces_without_user_sources(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin_a = data_fixture.create_user()
    workspace_with_user_source = data_fixture.create_workspace(user=admin_a)
    builder = data_fixture.create_builder_application(
        workspace=workspace_with_user_source
    )
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    # This workspace has no user source at all, so it has no application users and
    # is never checked, even though the instance wide usage is over the limit.
    admin_b = data_fixture.create_user()
    workspace_without_user_source = data_fixture.create_workspace(user=admin_b)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    assert Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type,
        workspace=workspace_with_user_source,
    ).exists()
    assert not Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type,
        workspace=workspace_without_user_source,
    ).exists()
    assert not is_marked_over_limit(workspace_without_user_source)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_notifies_every_workspace_with_a_user_source_instance_wide(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin_a = data_fixture.create_user()
    workspace_with_published_user_source = data_fixture.create_workspace(user=admin_a)
    builder = data_fixture.create_builder_application(
        workspace=workspace_with_published_user_source
    )
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    # The self-hosted limit is instance wide, so a workspace whose only user source
    # is in an unpublished application is told too, even though it contributed
    # nothing to the usage: once it publishes, its logins are affected like
    # everyone else's. The notification says it is the instance's limit, so the
    # workspace isn't blamed for the usage of another one.
    admin_b = data_fixture.create_user()
    workspace_with_unpublished_user_source = data_fixture.create_workspace(user=admin_b)
    unpublished_builder = data_fixture.create_builder_application(
        workspace=workspace_with_unpublished_user_source
    )
    data_fixture.create_local_baserow_table_user_source(application=unpublished_builder)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    for workspace in (
        workspace_with_published_user_source,
        workspace_with_unpublished_user_source,
    ):
        notification = Notification.objects.get(
            type=ApplicationUserLimitNotificationType.type, workspace=workspace
        )
        assert notification.data["instance_wide"] is True
        assert is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_skips_workspaces_without_a_published_user_source(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin_a = data_fixture.create_user()
    workspace_with_published_user_source = data_fixture.create_workspace(user=admin_a)
    builder = data_fixture.create_builder_application(
        workspace=workspace_with_published_user_source
    )
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    # With a per workspace limit only the user sources of published applications
    # count towards the usage, so a workspace whose only user source is in an
    # unpublished application has no application users and is never checked, even
    # though the usage resolved for the checked workspaces is over the limit.
    admin_b = data_fixture.create_user()
    workspace_with_unpublished_user_source = data_fixture.create_workspace(user=admin_b)
    unpublished_builder = data_fixture.create_builder_application(
        workspace=workspace_with_unpublished_user_source
    )
    data_fixture.create_local_baserow_table_user_source(application=unpublished_builder)

    with (
        per_workspace_license_plugin(),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    notification = Notification.objects.get(
        type=ApplicationUserLimitNotificationType.type,
        workspace=workspace_with_published_user_source,
    )
    assert notification.data["instance_wide"] is False
    assert not Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type,
        workspace=workspace_with_unpublished_user_source,
    ).exists()
    assert not is_marked_over_limit(workspace_with_unpublished_user_source)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_clears_the_notifications_of_a_workspace_that_unpublished(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    domain = publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)
    other_workspace = data_fixture.create_workspace(user=admin)
    other_builder = data_fixture.create_builder_application(workspace=other_workspace)
    publish(data_fixture, other_builder)
    data_fixture.create_local_baserow_table_user_source(application=other_builder)

    with (
        per_workspace_license_plugin(),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    assert Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    ).exists()

    # With a per workspace limit, the workspace has no application users anymore
    # once its application is unpublished, and isn't checked. The notification it
    # was sent is stale though, and cleared anyway so that publishing and crossing
    # the limit again notifies anew.
    domain.published_to = None
    domain.save()
    with (
        per_workspace_license_plugin(),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    assert not Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    ).exists()
    assert Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=other_workspace
    ).exists()


@pytest.mark.django_db
@override_settings(
    BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[],
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_over_limit_stamp_of_a_workspace_that_dropped_out_lingers_harmlessly(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    domain = publish(data_fixture, builder)
    user_source = data_fixture.create_local_baserow_table_user_source(
        application=builder
    )

    with (
        per_workspace_license_plugin(),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    assert is_marked_over_limit(workspace)

    # The application is unpublished, so with a per workspace limit the workspace
    # has no application users anymore and drops out of the check. Its stale
    # notification is cleared, but its over limit stamp is deliberately left to
    # expire by itself rather than cleared per dropped out workspace...
    domain.published_to = None
    domain.save()
    # ...which is the real usage of a workspace without a published user source.
    mock_aggregate_user_source_counts.return_value = 0
    expire_instance_wide_count_cache()
    with (
        per_workspace_license_plugin(),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    assert not Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    ).exists()
    assert is_marked_over_limit(workspace)

    # ...and that is harmless: even once the stamp is older than the grace period,
    # the login check re-resolves the real usage before refusing anything, and the
    # workspace is within its limit.
    mark_over_limit_since(user_source, now() - timedelta(hours=2))
    with per_workspace_license_plugin():
        raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_checks_every_workspace_across_batches(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspaces = []
    for _ in range(3):
        workspace = data_fixture.create_workspace(user=admin)
        builder = data_fixture.create_builder_application(workspace=workspace)
        publish(data_fixture, builder)
        data_fixture.create_local_baserow_table_user_source(application=builder)
        workspaces.append(workspace)

    with (
        patch(
            "baserow_enterprise.application_users.usage."
            "APPLICATION_USER_LIMIT_CHECK_BATCH_SIZE",
            2,
        ),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    for workspace in workspaces:
        assert Notification.objects.filter(
            type=ApplicationUserLimitNotificationType.type, workspace=workspace
        ).exists()
        assert is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_a_periodic_check_cut_short_has_still_dealt_with_the_earlier_batches(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspaces = []
    for _ in range(3):
        workspace = data_fixture.create_workspace(user=admin)
        builder = data_fixture.create_builder_application(workspace=workspace)
        publish(data_fixture, builder)
        data_fixture.create_local_baserow_table_user_source(application=builder)
        workspaces.append(workspace)

    # The usage and limit are resolved per batch, so the time limit firing while
    # resolving the second batch leaves the first one fully dealt with. The
    # workspaces are checked in id order, so it is the earliest that got dealt with.
    resolve = LicensePlugin.get_application_user_usage_and_limit_for_workspaces

    def resolve_then_time_out(self, batch):
        if resolve_then_time_out.calls:
            raise SoftTimeLimitExceeded()
        resolve_then_time_out.calls += 1
        return resolve(self, batch)

    resolve_then_time_out.calls = 0

    with (
        pytest.raises(SoftTimeLimitExceeded),
        patch(
            "baserow_enterprise.application_users.usage."
            "APPLICATION_USER_LIMIT_CHECK_BATCH_SIZE",
            1,
        ),
        patch.object(
            LicensePlugin,
            "get_application_user_usage_and_limit_for_workspaces",
            resolve_then_time_out,
        ),
        local_cache.context(),
        django_capture_on_commit_callbacks(execute=True),
    ):
        check_application_user_limits()

    first, *rest = sorted(workspaces, key=lambda workspace: workspace.id)
    assert Notification.objects.filter(
        type=ApplicationUserLimitNotificationType.type, workspace=first
    ).exists()
    assert is_marked_over_limit(first)
    for workspace in rest:
        assert not Notification.objects.filter(
            type=ApplicationUserLimitNotificationType.type, workspace=workspace
        ).exists()
        assert not is_marked_over_limit(workspace)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_keeps_the_notifications_of_a_trashed_workspace(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_DEFAULT_LIMIT
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    notification = Notification.objects.get(
        type=ApplicationUserLimitNotificationType.type, workspace=workspace
    )

    # A trashed workspace isn't checked, but its notification isn't cleared as
    # stale either, like it never was before...
    TrashHandler.trash(admin, workspace, None, workspace)
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    assert Notification.objects.filter(id=notification.id).exists()

    # ...so that restoring it doesn't notify the admins a second time about the
    # same ongoing condition.
    TrashHandler.restore_item(admin, "workspace", workspace.id)
    with local_cache.context(), django_capture_on_commit_callbacks(execute=True):
        check_application_user_limits()

    assert list(
        Notification.objects.filter(
            type=ApplicationUserLimitNotificationType.type, workspace=workspace
        ).values_list("id", flat=True)
    ) == [notification.id]


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_USAGE_WARNING_THRESHOLDS=[])
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_the_periodic_check_does_not_query_per_workspace_without_published_user_source(
    mock_aggregate_user_source_counts,
    data_fixture,
    django_capture_on_commit_callbacks,
):
    # Regression test for the hourly check exceeding its time limit on a large
    # instance with per workspace limits: it used to spend a handful of queries on
    # every workspace that ever got a user source, although most of them have no
    # published application and so no application users to check. Those
    # workspaces must cost nothing each.
    mock_aggregate_user_source_counts.return_value = 0
    expire_instance_wide_count_cache()
    admin = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin)
    builder = data_fixture.create_builder_application(workspace=workspace)
    publish(data_fixture, builder)
    data_fixture.create_local_baserow_table_user_source(application=builder)

    def create_workspace_with_unpublished_user_source():
        unpublished_workspace = data_fixture.create_workspace(user=admin)
        unpublished_builder = data_fixture.create_builder_application(
            workspace=unpublished_workspace
        )
        data_fixture.create_local_baserow_table_user_source(
            application=unpublished_builder
        )

    def count_queries_of_the_check():
        with (
            per_workspace_license_plugin(),
            CaptureQueriesContext(connection) as queries,
            local_cache.context(),
            django_capture_on_commit_callbacks(execute=True),
        ):
            check_application_user_limits()
        return len(queries)

    create_workspace_with_unpublished_user_source()
    queries_with_one_unpublished_workspace = count_queries_of_the_check()

    for _ in range(5):
        create_workspace_with_unpublished_user_source()

    assert count_queries_of_the_check() == queries_with_one_unpublished_workspace

from datetime import timedelta
from unittest.mock import patch

from django.test.utils import override_settings
from django.utils.timezone import now

import pytest
from baserow_premium_tests.fixtures import VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE

from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.models import ApplicationUserOverLimit
from baserow_enterprise.application_users.usage import (
    raise_if_over_application_user_login_limit,
    update_application_user_over_limit_state,
)

OVER_THE_LICENSE_LIMIT = 11


def mark_over_limit_since(user_source, since):
    ApplicationUserOverLimit.objects.create(
        workspace=user_source.application.workspace, since=since
    )


@pytest.fixture
def user_source(data_fixture):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(workspace=workspace)
    return data_fixture.create_local_baserow_table_user_source(application=builder)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_LIMIT_ENFORCED=False)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_over_the_limit_when_the_limit_is_a_soft_one(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_the_install_is_unlicensed(
    mock_aggregate_user_source_counts, user_source
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_allowed_when_no_license_carries_an_application_user_limit(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    # The default fixture license predates v1.32, so it carries no
    # `application_users` even though it is active.
    premium_data_fixture.create_premium_license()

    raise_if_over_application_user_login_limit(user_source)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True)
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
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
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
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
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
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
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
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
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
def test_update_application_user_over_limit_state(data_fixture):
    workspace = data_fixture.create_workspace()

    # Within the limit: nothing is stamped.
    update_application_user_over_limit_state(workspace, usage=10, limit=10)
    assert not ApplicationUserOverLimit.objects.filter(workspace=workspace).exists()

    # Over the limit: the moment is stamped.
    update_application_user_over_limit_state(workspace, usage=11, limit=10)
    over_limit = ApplicationUserOverLimit.objects.get(workspace=workspace)

    # Still over the limit: the original moment is kept so the grace period
    # isn't restarted.
    update_application_user_over_limit_state(workspace, usage=12, limit=10)
    assert (
        ApplicationUserOverLimit.objects.get(workspace=workspace).since
        == over_limit.since
    )

    # Back within the limit: the moment is cleared again.
    update_application_user_over_limit_state(workspace, usage=10, limit=10)
    assert not ApplicationUserOverLimit.objects.filter(workspace=workspace).exists()

    # No limit resolves anymore (e.g. a license upgrade): also cleared.
    update_application_user_over_limit_state(workspace, usage=11, limit=10)
    update_application_user_over_limit_state(workspace, usage=11, limit=None)
    assert not ApplicationUserOverLimit.objects.filter(workspace=workspace).exists()

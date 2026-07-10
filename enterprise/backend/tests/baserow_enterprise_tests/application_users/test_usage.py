from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium_tests.fixtures import VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE

from baserow_enterprise.application_users.exceptions import ApplicationUserLimitReached
from baserow_enterprise.application_users.usage import (
    raise_if_over_application_user_login_limit,
)

OVER_THE_LICENSE_LIMIT = 11


@pytest.fixture
def user_source(data_fixture):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(workspace=workspace)
    return data_fixture.create_local_baserow_table_user_source(application=builder)


@pytest.mark.django_db
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_LIMIT_ENFORCED=False)
@patch(
    "baserow_premium.application_user_usage.provider_types."
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
    "baserow_premium.application_user_usage.provider_types."
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
    "baserow_premium.application_user_usage.provider_types."
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
    "baserow_premium.application_user_usage.provider_types."
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
@override_settings(DEBUG=True, BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True)
@patch(
    "baserow_premium.application_user_usage.provider_types."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_login_is_refused_when_the_usage_exceeds_the_license_limit(
    mock_aggregate_user_source_counts, user_source, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = OVER_THE_LICENSE_LIMIT
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    with pytest.raises(ApplicationUserLimitReached):
        raise_if_over_application_user_login_limit(user_source)

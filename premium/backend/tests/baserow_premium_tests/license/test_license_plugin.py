from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium_tests.fixtures import (
    VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE,
    VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE,
)

from baserow_premium.application_user_usage.constants import (
    DEFAULT_APPLICATION_USERS_LIMIT,
)
from baserow_premium.license.plugin import LicensePlugin


@pytest.mark.django_db
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_application_user_usage_and_limit_defaults_when_unlicensed(
    mock_aggregate_user_source_counts, data_fixture
):
    mock_aggregate_user_source_counts.return_value = 7
    workspace = data_fixture.create_workspace()

    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
        7,
        DEFAULT_APPLICATION_USERS_LIMIT,
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_application_user_usage_and_limit_defaults_without_application_users(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 7
    workspace = premium_data_fixture.create_workspace()
    # The default fixture license predates v1.32, so it carries no
    # `application_users` even though it is active. That grants no application user
    # capacity of its own, so the default limit applies.
    license_object = premium_data_fixture.create_premium_license()
    assert license_object.is_active
    assert license_object.application_users is None

    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
        7,
        DEFAULT_APPLICATION_USERS_LIMIT,
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_application_user_usage_and_limit_sums_all_active_licenses(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 7
    workspace = premium_data_fixture.create_workspace()
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE.decode()
    )

    # The licensed value replaces the default, also when it is lower than it.
    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
        7,
        25,
    )

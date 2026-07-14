from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium_tests.fixtures import (
    VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE,
    VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE,
)

from baserow_premium.license.plugin import LicensePlugin


@pytest.mark.django_db
def test_get_application_user_usage_and_limit_is_none_when_unlicensed(data_fixture):
    workspace = data_fixture.create_workspace()

    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_application_user_usage_and_limit_is_none_without_application_users(
    premium_data_fixture,
):
    workspace = premium_data_fixture.create_workspace()
    # The default fixture license predates v1.32, so it carries no
    # `application_users` even though it is active.
    license_object = premium_data_fixture.create_premium_license()
    assert license_object.is_active
    assert license_object.application_users is None

    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) is None


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

    plugin = LicensePlugin()
    assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
        7,
        25,
    )

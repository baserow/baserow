from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from baserow_premium_tests.fixtures import (
    VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE,
    VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE,
)

from baserow_premium.application_user_usage.provider_types import (
    PremiumApplicationUserUsageProviderType,
)


@pytest.mark.django_db
def test_get_usage_and_limit_is_none_when_unlicensed(data_fixture):
    workspace = data_fixture.create_workspace()

    provider = PremiumApplicationUserUsageProviderType()
    assert provider.get_usage_and_limit(workspace) is None
    assert provider.is_over_login_limit(workspace) is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_usage_and_limit_is_none_for_a_license_without_application_users(
    premium_data_fixture,
):
    workspace = premium_data_fixture.create_workspace()
    # The default fixture license predates v1.32, so it carries no
    # `application_users` even though it is active.
    license_object = premium_data_fixture.create_premium_license()
    assert license_object.is_active
    assert license_object.application_users is None

    provider = PremiumApplicationUserUsageProviderType()
    assert provider.get_usage_and_limit(workspace) is None
    assert provider.is_over_login_limit(workspace) is None


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.provider_types."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_usage_and_limit_sums_the_limits_of_all_active_licenses(
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

    provider = PremiumApplicationUserUsageProviderType()
    assert provider.get_usage_and_limit(workspace) == (7, 25)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "usage,expected",
    [
        (9, False),
        # The limit itself is not over the limit, only exceeding it is.
        (10, False),
        (11, True),
    ],
)
@patch(
    "baserow_premium.application_user_usage.provider_types."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_is_over_login_limit_compares_usage_against_the_license_limit(
    mock_aggregate_user_source_counts, usage, expected, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = usage
    workspace = premium_data_fixture.create_workspace()
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )

    provider = PremiumApplicationUserUsageProviderType()
    assert provider.is_over_login_limit(workspace) is expected

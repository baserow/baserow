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
from baserow_premium.license.models import License
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.license.registries import license_type_registry


def _reset_license_table():
    """
    The tests below assert limits resolved from the License table, so they must
    only see the licenses they create themselves. When test files outside the
    pytest rootdir are passed as direct file arguments, their module node ID
    collapses to empty and their module level autouse fixtures apply session
    wide, which can register an active enterprise license (e.g. the
    `enable_enterprise` fixture) before these tests run. Called from the test
    bodies instead of a fixture so it always runs after such leaked fixtures.
    """

    License.objects.all().delete()


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
    _reset_license_table()

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
    _reset_license_table()
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
    _reset_license_table()
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


VALID_ENTERPRISE_15_SEAT_15_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImVhMDk4NTIxLTJiMTAtNGYxNC04MzJmLWFlMzI5N2I0OGM4ZiIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjYtMDEtMDhUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDUwLT"
    b"AxLTA4VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMTUsICJ"
    b"hcHBsaWNhdGlvbl91c2VycyI6IDE1LCAiaXNzdWVkX29uIjogIjIwMjYtMDEtMDhUMDk6Mjk6MTcuOTcx"
    b"NzUyIiwgImlzc3VlZF90b19lbWFpbCI6ICJwZXRlckBiYXNlcm93LmlvIiwgImlzc3VlZF90b19uYW1lI"
    b"jogIlBldGVyIiwgImluc3RhbmNlX2lkIjogIjEifQ==.ogM9TYtnWLM_fkdmMFZvaWGDFNGvTkzktIvgk"
    b"NCkmP1E9M_XWwYLdb4A-dMoG_5YTH1NixlxsGZN-EGRQ9o04NsouvXJ0S70aCVh2PZ35k0qyNw5tNN5nC"
    b"luJav7vBXkUB4z3c1qPsoArQLr1TMNBG3I8duB8Kjd7dKi2z1rtBSmJZP6BrqSR4EfHWdj3Pk5x9fqfFl"
    b"33Ubio1Xp_xHuApWXxEIp-eHjMmBe2eZ_dd-rvO7VA6wGpCaqaZKOkHxajS3SHKXjtB1rwnUs84up0r5k"
    b"MF5eJHgjOzN-9lIv5zIxH09BBnQPB70ZYlHurk0LiJu8rfWu3OtwRQG0otM2xA=="
)

# Expired (valid through 2021-12-31) and without `application_users`.
VALID_EXPIRED_ENTERPRISE_FIVE_SEAT_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjNmMDE2OGFmLWFmYWYtNDQyNi04OTZiLWIzODgzOTEwNzZlNyIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjEtMDEtMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDIxLT"
    b"EyLTMxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogNSwgIml"
    b"zc3VlZF9vbiI6ICIyMDIzLTAxLTExVDE0OjUzOjQ1LjM3Mjk1MCIsICJpc3N1ZWRfdG9fZW1haWwiOiAi"
    b"cGV0ckBleGFtcGxlLmNvbSIsICJpc3N1ZWRfdG9fbmFtZSI6ICJwZXRyQGV4YW1wbGUuY29tIiwgImluc"
    b"3RhbmNlX2lkIjogIjZkNjM2NmI4LTZmMzItNDU0OS04MWMyLWQ0YTBjMDdhMzM0YiJ9.B6os-CyNrp5wW"
    b"3gDTwjariLS6KhUBFYBwOlDlpVkTB8BPe1yjVIxw7nRH09TXovp9oTc2iJkGY5znBxuFMbCotmnIkBTnw"
    b"p6uOhBMlPQFydzUXt1GmaWpEEcTSV7hKNVykPasEBCTK3Z4CA-eTjJBKo7vGCT7qTu01I4ghgI4aBEM5J"
    b"qMe-ngEomRVnRMPAEgCNjFB44rVAB3zcJfPuBoukRB2FjOw1ddEkA3DjwcHlhkj1NcETlyUpFbFtCjhtL"
    b"oowm_5CZm8Ba6eL-YgI2vKTWfMsVZ9GkJxcaiK3d-AB_ipjub-VVyNXPiVWab7108w3EXmoZIvmhCc67g"
    b"bL3jA=="
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_application_user_usage_and_limit_asks_the_most_relevant_license_type(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 7
    workspace = premium_data_fixture.create_workspace()
    _reset_license_table()
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    License.objects.create(
        license=VALID_ENTERPRISE_15_SEAT_15_APP_USER_LICENSE.decode(),
        cached_untrusted_instance_wide=True,
    )

    # With both a premium and an enterprise license active, the license type with
    # the highest order (enterprise) is the one asked for the usage and limit.
    enterprise_license_type_class = type(license_type_registry.get("enterprise"))
    with patch.object(
        enterprise_license_type_class,
        "get_application_user_usage_and_limit",
        return_value=(3, 42),
    ):
        plugin = LicensePlugin()
        assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
            3,
            42,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
def test_get_application_user_usage_and_limit_ignores_inactive_licenses(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 7
    workspace = premium_data_fixture.create_workspace()
    _reset_license_table()
    premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    License.objects.create(
        license=VALID_EXPIRED_ENTERPRISE_FIVE_SEAT_LICENSE.decode(),
        cached_untrusted_instance_wide=True,
    )

    # The expired enterprise license must not win the most relevant license type
    # selection despite its higher order: if it were asked, the patched method
    # would return the sentinel instead of the premium license's limit.
    enterprise_license_type_class = type(license_type_registry.get("enterprise"))
    with patch.object(
        enterprise_license_type_class,
        "get_application_user_usage_and_limit",
        return_value=(3, 42),
    ):
        plugin = LicensePlugin()
        assert plugin.get_application_user_usage_and_limit_for_workspace(workspace) == (
            7,
            10,
        )

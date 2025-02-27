from unittest.mock import patch

from django.test.utils import override_settings

import pytest

VALID_FIRST_PREMIUM_5_SEAT_10_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjhiZmMwNzA1LWUwZGEtNGNkNy1hMWE0LWNjNDNiYjViMTE4OCIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI2LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTAsICJpc3N1ZWRfb24iOiAiMjAyNS0wMi0xN1QxMTo0NToxOS44NDI3OTYi"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.oSV2phIkZHsVXsQN1X2E4hKab7_-JLaz2b93M3GHx3zvt"
    b"_XTdeZRd-VK8ZvFdFDLh1LkKa4NAs8tSg8H1jN1xprkr-VFGA_-_owZrn59jK7UBOrd8p1WZur36ud5uG"
    b"DRsyw-yLmBhuFj27jE_3GZz-93xPnrDATjbT9NrXfrOggsyhn36tNLqydmrdpu45KdLD1SRrm7zcKaG8L"
    b"CHnlgSAd8md0923z7xf5vpTtB1rdJKUGj8kpjK7bxNojgmzZasGG424YbmSmk0B6yLvm18hIwv7_2Telk"
    b"hs8huMXL7HHDlEK2O7GmmCBoWT0ACNmcBhq4OcZ0K1pPX7MXvU3RNQ=="
)

VALID_SECOND_PREMIUM_5_SEAT_15_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImY4YjRlOTk1LTJhMmEtNDg0NS04ZWI1LWM2MjBiYzA5YTdiMiIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI2LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTUsICJpc3N1ZWRfb24iOiAiMjAyNS0wMi0xN1QxMTo0NToyNC44NjM3NjQi"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.GsYLPV63FG5FAncOp6dyLysDqVSMR37C1zwTT-otZgGuu"
    b"TpYg4aa9x-2ODonL9IAUmosyy6FZ1LcI4i8YdDyQ_rt-X_KhwR2S7Eotl6ZEepOYTbC7qKuG30szAKM6d"
    b"4eL0unPB48pLJhSS_j745WgMn-4vUMmm6FTWaIPJaWFzwUjOp5zLgNpvvgkayzQ608XdYVjilVBcTlszj"
    b"hxi00g0la2nMdCqDytZdJCn7XwAMA8itvSjYrWL1gMqTtPL6U92bJz97n8wQRBFW8kNKb2JTPfcbwozeg"
    b"Vd44sPwBqWaA0wwpKyNs-Sa43FHcbQKIGG8A68hKQy2MG3EWHgLWTA=="
)

VALID_ENTERPRISE_15_SEAT_15_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjA2YjliZWMzLWQ1ZDktNDI4Ni1iZTVhLWMyNWI5NDE4ODMwMyIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI4LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMTUsICJ"
    b"hcHBsaWNhdGlvbl91c2VycyI6IDE1LCAiaXNzdWVkX29uIjogIjIwMjUtMDItMTFUMTM6MzU6MjYuODYy"
    b"NTg3IiwgImlzc3VlZF90b19lbWFpbCI6ICJwZXRlckBiYXNlcm93LmlvIiwgImlzc3VlZF90b19uYW1lI"
    b"jogIlBldGVyIiwgImluc3RhbmNlX2lkIjogIjEifQ==.u1ws8JSZHta15GVqiUdQRb592aeIuAUxSNMDm"
    b"_WAY1rSFzeY74MLhl7aQ3ZB5JalUwuT8Bi1PqCBqiSSVJGdF5pL4u25Gwn10mNDvfXmRh34DvV7ZIYdpV"
    b"C_WiPOkeojoXtawuNmIzePON1pAv6TfG9Qq_57vSshht49TiG2PTYGdeeZa9sbrP589dhkIk0UY6Z6aCZ"
    b"voGAXz0rbrsS6lQUFqkYdBgA4LpgsrWWjLRxKdmy64CYj1k37ERtU8w-uauhYW3IUHDmDiZQYjNrL7g7q"
    b"Elk5YJBqjseMM_J4VkgULax1TDyG-q114UKCeCrCFA4pqsbxvGJ41-Le_-JOEg=="
)
VALID_ENTERPRISE_FIVE_SEAT_LICENSE = (
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
@patch("baserow_premium.license.registries.BuilderHandler.aggregate_user_source_counts")
def test_get_builder_usage_summary_for_single_premium_license(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 5
    valid_license = premium_data_fixture.create_premium_license(
        license=VALID_FIRST_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    summary = valid_license.license_type.get_builder_usage_summary(valid_license)

    assert summary.application_users_taken == 5
    assert valid_license.application_users == 10


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_premium.license.registries.BuilderHandler.aggregate_user_source_counts")
def test_get_builder_usage_summary_for_multiple_stacked_premium_licenses(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    mock_aggregate_user_source_counts.return_value = 26  # one more than allowed

    valid_license_a = premium_data_fixture.create_premium_license(
        license=VALID_FIRST_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    valid_license_b = premium_data_fixture.create_premium_license(
        license=VALID_SECOND_PREMIUM_5_SEAT_15_APP_USER_LICENSE.decode()
    )

    summary_a = valid_license_a.license_type.get_builder_usage_summary(valid_license_a)
    assert summary_a.application_users_taken == 10
    assert valid_license_a.application_users == 10

    summary_b = valid_license_b.license_type.get_builder_usage_summary(valid_license_b)
    assert summary_b.application_users_taken == 16
    assert valid_license_b.application_users == 15


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_premium.license.registries.BuilderHandler.aggregate_user_source_counts")
def test_get_builder_usage_summary_for_multiple_stacked_premium_and_enterprise_licenses(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    from baserow_premium.license.models import License

    mock_aggregate_user_source_counts.return_value = 26  # one more than allowed

    valid_builder_license_a = premium_data_fixture.create_premium_license(
        license=VALID_FIRST_PREMIUM_5_SEAT_10_APP_USER_LICENSE.decode()
    )
    valid_builder_license_b = License.objects.create(
        license=VALID_ENTERPRISE_15_SEAT_15_APP_USER_LICENSE.decode(),
        cached_untrusted_instance_wide=True,
    )
    valid_non_builder_license_c = License.objects.create(
        license=VALID_ENTERPRISE_FIVE_SEAT_LICENSE.decode(),
        cached_untrusted_instance_wide=True,
    )

    summary_a = valid_builder_license_a.license_type.get_builder_usage_summary(
        valid_builder_license_a
    )
    assert summary_a.application_users_taken == 10
    assert valid_builder_license_a.application_users == 10

    summary_b = valid_builder_license_b.license_type.get_builder_usage_summary(
        valid_builder_license_b
    )
    assert summary_b.application_users_taken == 16
    assert valid_builder_license_b.application_users == 15

    summary_c = valid_non_builder_license_c.license_type.get_builder_usage_summary(
        valid_non_builder_license_c
    )
    assert summary_c.application_users_taken == 0
    assert valid_non_builder_license_c.application_users is None

from unittest.mock import patch

from django.test.utils import override_settings

import pytest

VALID_FIRST_PREMIUM_5_SEAT_10_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImM2MmQwNzdhLTg3YmEtNGM1ZS05Y2M5LTRhN2NhYzZiMmNjNyIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjYtMDEtMDhUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDUwLT"
    b"AxLTA4VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTAsICJpc3N1ZWRfb24iOiAiMjAyNi0wMS0wOFQwOToyNjo0OS43NzE3MTci"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.WmuaTFYMXJF0DrJQVWZDUFRPMllYhuprbzAflf53_Etjc"
    b"haiHztKAQrEM5OwOKHLuVI-V1wuiQOP2ClP339w_bruzhLjIPKhuo6rBsllZvRyfs0axo8bDJ5Ff0xKWz"
    b"BEjOgndVKcFeWVcnhl3OE2cXQYMqcOapuaG3UTbwHa3G8n4TVYDv0Xtztfam9U9Tub8C_n9KBDbswS31Y"
    b"XzBQW86xU-9uIvjq1rLbmSIto3FbSGNNR8GuEuQXe0LuoS5iLf_9B3qF8Rrn8cml5N_2c78K_NA0olHqy"
    b"-ShSx0axC5OrwcpWhAwXccpB0X9VutE97_WtEikiQqhhCeNiyEy2_w=="
)

VALID_SECOND_PREMIUM_5_SEAT_15_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImZmZjMyYTUwLTc4MzMtNDBmZS1iZjJhLTJjYWZkOWY0ZDdkMCIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjYtMDEtMDhUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDUwLT"
    b"AxLTA4VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTUsICJpc3N1ZWRfb24iOiAiMjAyNi0wMS0wOFQwOToyODowNC41MDQ3MDMi"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.uAm7eoMn7LKA-edd10LISe0dkh_ocn-StgqNtGO5rEJRW"
    b"Onwd5a7Nh611NMTq_yI0vSwZ4GjeSxHlkJv-GHZLB3sjdQ5BP6c7g1EFmbN4r4Usue0h1BFDRhLlSdNJa"
    b"zU9nqo3AD6ym_j7cgIbdtNqIkhum9H1Cs73Gyaqh1Va_oQeLQRq7tTc3N8BlzuC6nIU68Cme8-oUhA-NI"
    b"AaID2LDHRipWGKAv8EMbK45WOhrqNwesDOXHvwK8jDLKj2yO2QMN6BY1FxHSjd_kXxwlrzYTUov8sZpnt"
    b"fORFtQyO_RfhBkq1HUjs_O44DObkxYqProsWM45LfasCdFcRZPDaLQ=="
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

from datetime import datetime, timezone

from django.test.utils import override_settings

import pytest
from baserow_premium.license.models import License
from freezegun import freeze_time

VALID_ONE_SEAT_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.e33Z4CxLSmD-R55Es24P3mR"
    b"8Oqn3LpaXvgYLzF63oFHat3paon7IBjBmOX3eyd8KjirVf3empJds4uUw2Nn2m7TVvRAtJ8XzNl-8ytf"
    b"2RLtmjMx1Xkgp5VZ8S7UqJ_cKLyl76eVRtGEA1DH2HdPKu1vBPJ4bzDfnhDPYl4k5z9XSSgqAbQ9WO0U"
    b"5kiI3BYjVRZSKnZMeguAGZ47ezDj_WArGcHAB8Pa2v3HFp5Y34DMJ8r3_hD5hxCKgoNx4AHx1Q-hRDqp"
    b"Aroj-4jl7KWvlP-OJNc1BgH2wnhFmeKHotv-Iumi83JQohyceUbG6j8rDDQvJfcn0W2_ebmUH3TKr-w="
    b"="
)
VALID_TWO_SEAT_LICENSE = (
    # id: "2", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjIiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUzOjM3"
    b"LjA5MjMwMyIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTM6MzcuMDkyMzAzIiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMiwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUzOjM3LjA5MjMwMyIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.d41tB1kx69gw-9xDrRI0kER"
    b"KDUtR-P6yRM3ufKZ_XRDewVCBAniCLe9-ce7TKabnMedE2cqHjYVLlI66Dfa5oH8fGswnyC16c9ZHlOU"
    b"jQ5CpHTorZm6eyCXaP6MDdhstCNKdDrZns3qvVMAqDpmxS8wmiG9Y6gZjvBGXZWeoCraF1SVcUnFBBlf"
    b"UemfGSQUwPitVlxJ6GWN-hzi7b1GZqWJKDb2YYJ0T30VMJeNO7oi6YHMUOH33041FU79DSET2A2NNEFu"
    b"e-jnCcw5NFpH-zGzBDv1wpR3DFmJa78KwGbj0Kdzim85AUzi1xGRlIyxxTdTkVy2B-08lPaoG8Q62bw="
    b"="
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_license_model_properties():
    license = License(license=VALID_ONE_SEAT_LICENSE.decode())
    assert license.license_id == "1"
    assert license.valid_from == datetime(2021, 8, 29, 19, 52, 57, 842696).replace(
        tzinfo=timezone.utc
    )
    assert license.valid_through == datetime(2021, 9, 29, 19, 52, 57, 842696).replace(
        tzinfo=timezone.utc
    )
    assert license.product_code == "premium"
    assert license.seats == 1
    assert license.issued_on == datetime(2021, 8, 29, 19, 52, 57, 842696).replace(
        tzinfo=timezone.utc
    )
    assert license.issued_to_email == "bram@baserow.io"
    assert license.issued_to_name == "Bram"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_license_model_is_active():
    license = License(license=VALID_ONE_SEAT_LICENSE.decode())

    with freeze_time("2021-08-29 19:50"):
        assert not license.is_active

    with freeze_time("2021-08-29 20:00"):
        assert license.is_active

    with freeze_time("2021-09-29 19:50"):
        assert license.is_active

    with freeze_time("2021-09-29 19:54"):
        assert not license.is_active


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_license_model_valid_payload():
    invalid_license = License(license="invalid")
    assert not invalid_license.valid_payload
    valid_license = License(license=VALID_ONE_SEAT_LICENSE.decode())
    assert valid_license.valid_payload


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_premium_license_model_save():
    license_1 = License(license=VALID_ONE_SEAT_LICENSE.decode())
    license_2 = License(license=VALID_TWO_SEAT_LICENSE.decode())

    assert license_1.license_id == "1"

    license_1.license = VALID_TWO_SEAT_LICENSE.decode()
    license_1.save()
    license_2.license = VALID_ONE_SEAT_LICENSE.decode()
    license_2.save()

    assert license_1.license_id == "2"
    assert license_2.license_id == "1"

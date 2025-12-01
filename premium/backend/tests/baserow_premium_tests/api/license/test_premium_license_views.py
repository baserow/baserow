from datetime import datetime, timezone

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
import responses
from baserow_premium.license.models import License, LicenseUser
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

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
VALID_INSTANCE_TWO_LICENSE = (
    # id: "2", instance_id: "2"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMiJ9.i3Og4ZJwz__TxWyFc2B6lDi"
    b"ZBAIOVTZv_jXVzQQqcjG-flPAicqXFECl7MbbexVmtsMES-U7VPebOh0t4oPoDXL1LiftfjmT63wO4An"
    b"A3FMS0Ip0GIx2upkQC-MlU1kSR9Tltrr1qySuQvXORDRUaSxaRQQacwZTOIviVdcxG9vesjkFwn6LMYp"
    b"-GhmCJXB0YfMgsvPm6kj6qTWPh3ed8aLNFnekUhB-dUwA4tqPicCQHRQCRZqzo9vx-hKdeHCGZMg0htG"
    b"EB4cAeV4I29JXPC83qtwt6DSCPxudlJsli3tYsLMcxAHysVN3H_FAY8qg54MP33OKvZuwww5uFDITMQ="
    b"="
)
INVALID_SIGNATURE_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogMSwgInZhbGlkX2Zyb20iOiAiMjAyMS0wOC0yOVQxOTo1NDoxMi4w"
    b"NjY4NDYiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDIxLTA5LTI5VDE5OjU0OjEyLjA2Njg0NiIsICJwcm9k"
    b"dWN0X2NvZGUiOiAicHJlbWl1bSIsICJzZWF0cyI6IDEsICJ0b19lbWFpbCI6ICJicmFtQGJhc2Vyb3cu"
    b"aW8iLCAidG9fbmFtZSI6ICJCcmFtIn0=.hYaWGO0M6s1pA9bhcBlk1fE1QMrhlDGNiBIBG_2O2AMGFPj"
    b"gnsHdwfUIe_eo6dyAyvsToxBrpxr6N1vRqPdA61cKjTlhUdFqvj7NTeydS4Z9TlfP-vFslQk9CO_ok7Z"
    b"ws8AHTQ2pKfsdzqcWNZnWKZeQGEtO73MIoFJbHr07mtWA1ZZgJNBTBpp-7BNtvj2bQyUeXyRKD5LVj8G"
    b"ESDcapZCNt5ufesbYvpfs1c6p6UP4z3gszOYrzMApMqWHty7j10SDjcLIEsUTd02r_Pbip-KxmGfecXg"
    b"B0HF7HJZwkY9ZdlZ7ODGtV0e455dQwh5sSHa3RRd71AXVou-cuOS87g=="
)
INVALID_VERSION_LICENSE = (
    b"eyJ2ZXJzaW9uIjogOTk5OX0=.rzAyL6qBkz_Eb3GYaSOXy9CJ2HJg4uAxtrbinh4aDYy7Eq4e4RpfaPm"
    b"4dZLocIRxSmx_wUYSI0CMqmkwABHgzxRVmzVAmXf5MxX7vAGjjEnQX_dQOl8kY15gXhEQZv5pjSPVcZW"
    b"CLll95OFoBUJhtOQqNC6JLA1LZdiSPG6zFhvi5V27sRGBz3E8jhFLWY-Y2WIq5_9q2d_hVFM0KHwRcxb"
    b"CVof8RBUq1DgMcDKEGE7WRHYDVP1QugBjf4GZlvIE4ZVr3tKr0aKPX8nuNVhbQeudCW8tnturmxevpRN"
    b"vLS5ETSQzJoP46cGuw0HUV20P4SnvQP_NRd5zifgllJqsUw=="
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_list_licenses(api_client, data_fixture, django_assert_num_queries):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    user_3 = data_fixture.create_user()

    license_1 = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license_1, user=user_1)

    license_2 = License.objects.create(
        license=VALID_TWO_SEAT_LICENSE.decode(),
        last_check=datetime(2021, 8, 29, 19, 52, 57, 842696).replace(
            tzinfo=timezone.utc
        ),
    )
    LicenseUser.objects.create(license=license_2, user=user_2)
    LicenseUser.objects.create(license=license_2, user=user_3)

    _, normal_token = data_fixture.create_user_and_token(is_staff=False)
    admin_user = data_fixture.create_user(is_staff=True)

    response = api_client.get(
        reverse("api:premium:license:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    with freeze_time("2021-09-01 00:00"):
        admin_token = data_fixture.generate_token(admin_user)
        # We expect one to count the total number of users, one query for the user
        # check, one for the fetching the licenses including the count of
        # seats that are taken.
        with django_assert_num_queries(5):
            response = api_client.get(
                reverse("api:premium:license:list"),
                format="json",
                HTTP_AUTHORIZATION=f"JWT {admin_token}",
            )
            assert response.status_code == HTTP_200_OK
            response_json = response.json()
            assert len(response_json) == 2
            assert response_json[0]["license_id"] == "1"
            assert response_json[0]["is_active"] is True
            assert response_json[0]["last_check"] is None
            assert response_json[0]["valid_from"] == "2021-08-29T19:52:57.842696Z"
            assert response_json[0]["valid_through"] == "2021-09-29T19:52:57.842696Z"
            assert response_json[0]["seats_taken"] == 1
            assert response_json[0]["seats"] == 1
            assert response_json[0]["product_code"] == "premium"
            assert response_json[0]["issued_on"] == "2021-08-29T19:52:57.842696Z"
            assert response_json[0]["issued_to_email"] == "bram@baserow.io"
            assert response_json[0]["issued_to_name"] == "Bram"
            assert response_json[1]["license_id"] == "2"
            assert response_json[1]["is_active"] is True
            assert response_json[1]["last_check"] == "2021-08-29T19:52:57.842696Z"
            assert response_json[1]["valid_from"] == "2021-08-29T19:53:37.092303Z"
            assert response_json[1]["valid_through"] == "2021-09-29T19:53:37.092303Z"
            assert response_json[1]["seats_taken"] == 2
            assert response_json[1]["seats"] == 2
            assert response_json[1]["issued_on"] == "2021-08-29T19:53:37.092303Z"
            assert response_json[1]["issued_to_email"] == "bram@baserow.io"
            assert response_json[1]["issued_to_name"] == "Bram"

            assert response_json[1]["product_code"] == "premium"

    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    with freeze_time("2021-09-29 19:53"):
        admin_token = data_fixture.generate_token(admin_user)
        response = api_client.get(
            reverse("api:premium:license:list"),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert len(response_json) == 2
        assert response_json[0]["license_id"] == "2"
        assert response_json[0]["is_active"] is True
        assert response_json[0]["last_check"] == "2021-08-29T19:52:57.842696Z"
        assert response_json[0]["valid_from"] == "2021-08-29T19:53:37.092303Z"
        assert response_json[0]["valid_through"] == "2021-09-29T19:53:37.092303Z"
        assert response_json[0]["seats_taken"] == 2
        assert response_json[0]["seats"] == 2
        assert response_json[0]["product_code"] == "premium"
        assert response_json[0]["issued_on"] == "2021-08-29T19:53:37.092303Z"
        assert response_json[0]["issued_to_email"] == "bram@baserow.io"
        assert response_json[0]["issued_to_name"] == "Bram"
        assert response_json[1]["license_id"] == "1"
        assert response_json[1]["is_active"] is False
        assert response_json[1]["last_check"] is None
        assert response_json[1]["valid_from"] == "2021-08-29T19:52:57.842696Z"
        assert response_json[1]["valid_through"] == "2021-09-29T19:52:57.842696Z"
        assert response_json[1]["seats_taken"] == 1
        assert response_json[1]["seats"] == 1
        assert response_json[1]["product_code"] == "premium"
        assert response_json[1]["issued_on"] == "2021-08-29T19:52:57.842696Z"
        assert response_json[1]["issued_to_email"] == "bram@baserow.io"
        assert response_json[1]["issued_to_name"] == "Bram"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_admin_register_license(api_client, data_fixture):
    data_fixture.update_settings(instance_id="1")
    normal_user, normal_token = data_fixture.create_user_and_token(is_staff=False)
    admin_user, admin_token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:premium:license:list"),
        {"license": VALID_ONE_SEAT_LICENSE.decode()},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.post(
        reverse("api:premium:license:list"),
        {"license": INVALID_SIGNATURE_LICENSE.decode()},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_INVALID_LICENSE"

    admin_token = data_fixture.generate_token(admin_user)
    with freeze_time("2021-10-01 00:00"):
        admin_token = data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:premium:license:list"),
            {"license": VALID_ONE_SEAT_LICENSE.decode()},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_LICENSE_HAS_EXPIRED"

    admin_token = data_fixture.generate_token(admin_user)
    with freeze_time("2021-09-01 00:00"):
        admin_token = data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:premium:license:list"),
            {"license": INVALID_VERSION_LICENSE.decode()},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_UNSUPPORTED_LICENSE"

        response = api_client.post(
            reverse("api:premium:license:list"),
            {"license": VALID_INSTANCE_TWO_LICENSE.decode()},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_PREMIUM_LICENSE_INSTANCE_ID_MISMATCH"

        response = api_client.post(
            reverse("api:premium:license:list"),
            {"license": VALID_TWO_SEAT_LICENSE.decode()},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_200_OK

        licenses = License.objects.all()
        assert len(licenses) == 1

        response_json = response.json()
        assert response_json["id"] == licenses[0].id
        assert response_json["license_id"] == "2"
        assert response_json["is_active"] is True
        assert response_json["last_check"] is None
        assert response_json["valid_from"] == "2021-08-29T19:53:37.092303Z"
        assert response_json["valid_through"] == "2021-09-29T19:53:37.092303Z"
        assert response_json["seats_taken"] == 2
        assert response_json["seats"] == 2
        assert response_json["product_code"] == "premium"
        assert response_json["issued_on"] == "2021-08-29T19:53:37.092303Z"
        assert response_json["issued_to_email"] == "bram@baserow.io"
        assert response_json["issued_to_name"] == "Bram"

        admin_token = data_fixture.generate_token(admin_user)
        response = api_client.post(
            reverse("api:premium:license:list"),
            {"license": VALID_TWO_SEAT_LICENSE.decode()},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["error"] == "ERROR_LICENSE_ALREADY_EXISTS"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_get_license(api_client, data_fixture, django_assert_num_queries):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=normal_user)
    LicenseUser.objects.create(license=license, user=admin_user)

    response = api_client.get(
        reverse("api:premium:license:item", kwargs={"id": license.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.get(
        reverse("api:premium:license:item", kwargs={"id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    with freeze_time("2021-09-01 00:00"):
        admin_token = data_fixture.generate_token(admin_user)
        with django_assert_num_queries(6):
            response = api_client.get(
                reverse("api:premium:license:item", kwargs={"id": license.id}),
                format="json",
                HTTP_AUTHORIZATION=f"JWT {admin_token}",
            )
            assert response.status_code == HTTP_200_OK
            response_json = response.json()
            assert response_json["id"] == license.id
            assert response_json["license_id"] == "2"
            assert response_json["is_active"] is True
            assert response_json["last_check"] is None
            assert response_json["valid_from"] == "2021-08-29T19:53:37.092303Z"
            assert response_json["valid_through"] == "2021-09-29T19:53:37.092303Z"
            assert response_json["seats_taken"] == 2
            assert response_json["seats"] == 2
            assert response_json["product_code"] == "premium"
            assert response_json["issued_on"] == "2021-08-29T19:53:37.092303Z"
            assert response_json["issued_to_email"] == "bram@baserow.io"
            assert response_json["issued_to_name"] == "Bram"
            assert len(response_json["users"]) == 2
            assert response_json["users"][0]["id"] == normal_user.id
            assert response_json["users"][0]["email"] == normal_user.email
            assert response_json["users"][0]["first_name"] == normal_user.first_name
            assert response_json["users"][1]["id"] == admin_user.id
            assert response_json["users"][1]["email"] == admin_user.email
            assert response_json["users"][1]["first_name"] == admin_user.first_name


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_delete_license(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())

    response = api_client.delete(
        reverse("api:premium:license:item", kwargs={"id": license.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.delete(
        reverse("api:premium:license:item", kwargs={"id": 0}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse("api:premium:license:item", kwargs={"id": license.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert License.objects.all().count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_add_user_to_license(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())

    response = api_client.post(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.post(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_FOUND"

    response = api_client.post(
        reverse(
            "api:premium:license:user",
            kwargs={"id": 0, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == normal_user.id
    assert response_json["first_name"] == normal_user.first_name
    assert response_json["email"] == normal_user.email


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_delete_user_from_license(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=normal_user)

    response = api_client.delete(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.delete(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_FOUND"

    response = api_client.delete(
        reverse(
            "api:premium:license:user",
            kwargs={"id": 0, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.delete(
        reverse(
            "api:premium:license:user",
            kwargs={"id": license.id, "user_id": normal_user.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert LicenseUser.objects.all().count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_fill_users_in_license(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())

    response = api_client.post(
        reverse(
            "api:premium:license:fill_seats",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.post(
        reverse(
            "api:premium:license:fill_seats",
            kwargs={"id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:premium:license:fill_seats",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 2
    assert response_json[0]["id"] == normal_user.id
    assert response_json[0]["email"] == normal_user.email
    assert response_json[0]["first_name"] == normal_user.first_name
    assert response_json[1]["id"] == admin_user.id
    assert response_json[1]["email"] == admin_user.email
    assert response_json[1]["first_name"] == admin_user.first_name
    assert LicenseUser.objects.all().count() == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_remove_all_users(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=normal_user)
    LicenseUser.objects.create(license=license, user=admin_user)

    response = api_client.post(
        reverse(
            "api:premium:license:remove_all_users",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.post(
        reverse(
            "api:premium:license:remove_all_users",
            kwargs={"id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.post(
        reverse(
            "api:premium:license:remove_all_users",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert LicenseUser.objects.all().count() == 0


@pytest.mark.django_db
def test_admin_license_user_lookup(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False, first_name="Test", email="email@localhost"
    )
    normal_user_2 = data_fixture.create_user(first_name="Foo", email="tmp@localhost")
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True, first_name="Admin test", email="admin@localhost"
    )

    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=admin_user)
    license_2 = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license_2, user=normal_user)

    response = api_client.get(
        reverse(
            "api:premium:license:lookup_users",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.get(
        reverse(
            "api:premium:license:lookup_users",
            kwargs={"id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    response = api_client.get(
        reverse(
            "api:premium:license:lookup_users",
            kwargs={"id": license.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 2
    assert response_json["results"][0]["id"] == normal_user_2.id
    assert response_json["results"][0]["value"] == "Foo (tmp@localhost)"

    url = reverse(
        "api:premium:license:lookup_users",
        kwargs={"id": license.id},
    )
    response = api_client.get(
        f"{url}?page=2",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"] == []

    url = reverse(
        "api:premium:license:lookup_users",
        kwargs={"id": license.id},
    )
    response = api_client.get(
        f"{url}?page=2&size=1",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 2
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == normal_user.id
    assert response_json["results"][0]["value"] == "Test (email@localhost)"

    url = reverse(
        "api:premium:license:lookup_users",
        kwargs={"id": license.id},
    )
    response = api_client.get(
        f"{url}?search=test",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == normal_user.id
    assert response_json["results"][0]["value"] == "Test (email@localhost)"

    url = reverse(
        "api:premium:license:lookup_users",
        kwargs={"id": license.id},
    )
    response = api_client.get(
        f"{url}?search=email",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["count"] == 1
    assert len(response_json["results"]) == 1
    assert response_json["results"][0]["id"] == normal_user.id
    assert response_json["results"][0]["value"] == "Test (email@localhost)"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_admin_check_license(api_client, data_fixture):
    normal_user, normal_token = data_fixture.create_user_and_token(
        is_staff=False,
    )
    admin_user, admin_token = data_fixture.create_user_and_token(
        is_staff=True,
    )

    license_1 = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    license_2 = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())

    response = api_client.get(
        reverse(
            "api:premium:license:check",
            kwargs={"id": license_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {normal_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.get(
        reverse(
            "api:premium:license:check",
            kwargs={"id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_LICENSE_DOES_NOT_EXIST"

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                VALID_ONE_SEAT_LICENSE.decode(): {
                    "type": "invalid",
                    "detail": "",
                },
                VALID_TWO_SEAT_LICENSE.decode(): {
                    "type": "ok",
                    "detail": "",
                },
            },
            status=200,
        )

        admin_token = data_fixture.generate_token(admin_user)
        response = api_client.get(
            reverse(
                "api:premium:license:check",
                kwargs={"id": license_1.id},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        response = api_client.get(
            reverse(
                "api:premium:license:check",
                kwargs={"id": license_2.id},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["id"] == license_2.id
        assert response_json["license_id"] == "2"
        assert len(response_json["users"]) == 0

import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.api.user.registries import UserDataType, user_data_registry
from baserow.contrib.database.models import Database, Table
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.user.handler import UserHandler

User = get_user_model()


@pytest.mark.django_db
def test_create_user(client, data_fixture):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    short_password = "short"
    response = client.post(
        reverse("api:user:index"),
        {"name": "Test1", "email": "test@test.nl", "password": valid_password},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    user = User.objects.get(email="test@test.nl")
    assert user.first_name == "Test1"
    assert user.email == "test@test.nl"
    assert user.password != ""
    assert "password" not in response_json["user"]
    assert response_json["user"]["username"] == "test@test.nl"
    assert response_json["user"]["first_name"] == "Test1"
    assert response_json["user"]["is_staff"] is True
    assert response_json["user"]["id"] == user.id

    # Test profile properties
    response = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1Bis",
            "email": "test1bis@test.nl",
            "password": valid_password,
            "language": "fr",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    user = User.objects.get(email="test1bis@test.nl")
    assert user.profile.language == "fr"
    assert response_json["user"]["language"] == "fr"

    response_failed = client.post(
        reverse("api:user:index"),
        {"name": "Test1", "email": "test@test.nl", "password": valid_password},
        format="json",
    )
    assert response_failed.status_code == 400
    assert response_failed.json()["error"] == "ERROR_EMAIL_ALREADY_EXISTS"

    response_failed = client.post(
        reverse("api:user:index"),
        {"name": "Test1", "email": " teSt@teST.nl ", "password": valid_password},
        format="json",
    )
    assert response_failed.status_code == 400
    assert response_failed.json()["error"] == "ERROR_EMAIL_ALREADY_EXISTS"

    too_long_name = "x" * 151
    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": too_long_name,
            "email": "new@example.com ",
            "password": valid_password,
        },
        format="json",
    )
    assert response_failed.status_code == 400
    assert response_failed.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_failed.json()["detail"] == {
        "name": [
            {
                "code": "max_length",
                "error": "Ensure this field has no more than 150 characters.",
            }
        ]
    }

    data_fixture.update_settings(allow_new_signups=False)
    response_failed = client.post(
        reverse("api:user:index"),
        {"name": "Test1", "email": "test10@test.nl", "password": valid_password},
        format="json",
    )
    assert response_failed.status_code == 400
    assert response_failed.json()["error"] == "ERROR_DISABLED_SIGNUP"
    data_fixture.update_settings(allow_new_signups=True)

    response_failed_2 = client.post(
        reverse("api:user:index"), {"email": "test"}, format="json"
    )
    assert response_failed_2.status_code == 400

    long_password = "x" * 256
    response = client.post(
        reverse("api:user:index"),
        {"name": "Test2", "email": "test2@test.nl", "password": long_password},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    user = User.objects.get(email="test2@test.nl")
    assert user.check_password(long_password)

    long_password = "x" * 257
    response = client.post(
        reverse("api:user:index"),
        {"name": "Test2", "email": "test2@test.nl", "password": long_password},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["password"][0]["code"] == "password_validation_failed"
    )
    assert (
        response_json["detail"]["password"][0]["error"]
        == "This password is too long. It must not exceed 256 characters."
    )

    response = client.post(
        reverse("api:user:index"),
        {"name": "Test2", "email": "random@test.nl", "password": short_password},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["password"][0]["code"] == "password_validation_failed"
    )
    assert (
        response_json["detail"]["password"][0]["error"]
        == "This password is too short. It must contain at least 8 characters."
    )

    # Test profile attribute errors
    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test20@test.nl",
            "password": valid_password,
            "language": "invalid",
        },
        format="json",
    )
    response_json = response_failed.json()
    assert response_failed.status_code == 400
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["language"][0]["code"] == "invalid_language"
    assert response_json["detail"]["language"][0]["error"] == (
        "Only the following language keys are "
        f"valid: {','.join([l[0] for l in settings.LANGUAGES])}"
    )

    # Test username with maximum length
    long_username = "x" * 150
    response = client.post(
        reverse("api:user:index"),
        {
            "name": long_username,
            "email": "longusername@email.com",
            "password": "password",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    user = User.objects.get(email="longusername@email.com")
    assert user.first_name == long_username

    # Test username with length exceeding the maximum
    even_longer_username = "x" * 200
    response = client.post(
        reverse("api:user:index"),
        {
            "name": even_longer_username,
            "email": "evenlongerusername@email.com",
            "password": "password",
        },
        format="json",
    )
    response_json = response.json()
    assert response_failed.status_code == 400


@pytest.mark.django_db
def test_user_account(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test@localhost.nl", language="en", first_name="Nikolas"
    )

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "first_name": "NewOriginalName",
            "language": "fr",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert response_json["first_name"] == "NewOriginalName"
    assert response_json["language"] == "fr"
    assert response_json["completed_onboarding"] is False
    assert response_json["completed_guided_tours"] == []

    user.refresh_from_db()
    assert user.first_name == "NewOriginalName"
    assert user.profile.language == "fr"

    response = api_client.patch(
        reverse("api:user:account"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["non_field_errors"][0]["code"] == "invalid"
    assert response_json["detail"]["non_field_errors"][0]["error"] == (
        "At least one of the fields first_name, language, email_notification_frequency,"
        " completed_onboarding, completed_guided_tours must be provided."
    )

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "language": "invalid",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["language"][0]["code"] == "invalid_language"
    assert response_json["detail"]["language"][0]["error"] == (
        "Only the following language keys are "
        f"valid: {','.join([l[0] for l in settings.LANGUAGES])}"
    )

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "email_notification_frequency": "invalid",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["email_notification_frequency"][0]["code"]
        == "invalid_choice"
    )
    assert response_json["detail"]["email_notification_frequency"][0]["error"] == (
        '"invalid" is not a valid choice.'
    )

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "email_notification_frequency": "daily",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert response_json["first_name"] == "NewOriginalName"
    assert response_json["language"] == "fr"
    assert response_json["email_notification_frequency"] == "daily"

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "completed_onboarding": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert response_json["first_name"] == "NewOriginalName"
    assert response_json["language"] == "fr"
    assert response_json["email_notification_frequency"] == "daily"
    assert response_json["completed_onboarding"] is True
    assert response_json["completed_guided_tours"] == []

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "completed_onboarding": True,
            "completed_guided_tours": ["core"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert response_json["first_name"] == "NewOriginalName"
    assert response_json["language"] == "fr"
    assert response_json["email_notification_frequency"] == "daily"
    assert response_json["completed_onboarding"] is True
    assert response_json["completed_guided_tours"] == ["core"]


@pytest.mark.django_db
def test_user_account_completed_guided_tours(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test@localhost.nl", language="en", first_name="Nikolas"
    )

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "completed_guided_tours": ["core"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert set(response_json["completed_guided_tours"]) == set(["core"])

    response = api_client.patch(
        reverse("api:user:account"),
        {
            "completed_guided_tours": ["core", "database"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert set(response_json["completed_guided_tours"]) == set(["core", "database"])

    # It should not be possible to remove entries.
    response = api_client.patch(
        reverse("api:user:account"),
        {
            "completed_guided_tours": ["core", "application"],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == 200
    assert set(response_json["completed_guided_tours"]) == set(
        ["core", "database", "application"]
    )


@pytest.mark.django_db
def test_create_user_with_invitation(data_fixture, client):
    data_fixture.create_password_provider()
    core_handler = CoreHandler()
    valid_password = "thisIsAValidPassword"
    invitation = data_fixture.create_workspace_invitation(email="test0@test.nl")
    signer = core_handler.get_workspace_invitation_signer()

    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test@test.nl",
            "password": valid_password,
            "workspace_invitation_token": "INVALID",
        },
        format="json",
    )
    assert response_failed.status_code == HTTP_400_BAD_REQUEST
    assert response_failed.json()["error"] == "BAD_TOKEN_SIGNATURE"

    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test0@test.nl",
            "password": valid_password,
            "workspace_invitation_token": f"{signer.dumps(invitation.id)}2",
        },
        format="json",
    )
    assert response_failed.status_code == HTTP_400_BAD_REQUEST
    assert response_failed.json()["error"] == "BAD_TOKEN_SIGNATURE"
    assert User.objects.all().count() == 1

    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test@test.nl",
            "password": valid_password,
            "workspace_invitation_token": signer.dumps(99999),
        },
        format="json",
    )
    assert response_failed.status_code == HTTP_404_NOT_FOUND
    assert response_failed.json()["error"] == "ERROR_GROUP_INVITATION_DOES_NOT_EXIST"

    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test@test.nl",
            "password": valid_password,
            "workspace_invitation_token": signer.dumps(invitation.id),
        },
        format="json",
    )
    assert response_failed.status_code == HTTP_400_BAD_REQUEST
    assert response_failed.json()["error"] == "ERROR_GROUP_INVITATION_EMAIL_MISMATCH"
    assert User.objects.all().count() == 1

    response_failed = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test0@test.nl",
            "password": valid_password,
            "workspace_invitation_token": signer.dumps(invitation.id),
        },
        format="json",
    )
    assert response_failed.status_code == HTTP_200_OK
    assert User.objects.all().count() == 2
    assert Workspace.objects.all().count() == 1
    assert Workspace.objects.all().first().id == invitation.workspace_id
    assert WorkspaceUser.objects.all().count() == 2
    assert Database.objects.all().count() == 0
    assert Table.objects.all().count() == 0


@pytest.mark.django_db
def test_create_user_with_template(data_fixture, client):
    data_fixture.create_password_provider()
    old_templates = settings.APPLICATION_TEMPLATES_DIR
    valid_password = "thisIsAValidPassword"
    settings.APPLICATION_TEMPLATES_DIR = os.path.join(
        settings.BASE_DIR, "../../../tests/templates"
    )
    template = data_fixture.create_template(slug="example-template")

    response = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test0@test.nl",
            "password": valid_password,
            "template_id": -1,
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["template_id"][0]["code"] == "does_not_exist"

    response = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test0@test.nl",
            "password": valid_password,
            "template_id": "random",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["template_id"][0]["code"] == "incorrect_type"

    response = client.post(
        reverse("api:user:index"),
        {
            "name": "Test1",
            "email": "test0@test.nl",
            "password": valid_password,
            "template_id": template.id,
        },
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert Workspace.objects.all().count() == 2
    assert WorkspaceUser.objects.all().count() == 1
    # We expect the example template to be installed
    assert Database.objects.all().count() == 1, Database.objects.values_list(
        "name", flat=True
    )
    assert Database.objects.all().first().name == "Event marketing"
    assert Table.objects.all().count() == 2

    settings.APPLICATION_TEMPLATES_DIR = old_templates


@pytest.mark.django_db(transaction=True)
def test_send_reset_password_email(data_fixture, client, mailoutbox):
    data_fixture.create_password_provider()
    data_fixture.create_user(email="test@localhost.nl")

    response = client.post(
        reverse("api:user:send_reset_password_email"), {}, format="json"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": "unknown@localhost.nl", "base_url": "http://localhost:3000"},
        format="json",
    )
    assert response.status_code == 204
    assert len(mailoutbox) == 0

    response = client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": "test@localhost.nl", "base_url": "http://test.nl"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_HOSTNAME_IS_NOT_ALLOWED"
    assert len(mailoutbox) == 0

    response = client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": "test@localhost.nl", "base_url": "http://localhost:3000"},
        format="json",
    )
    assert response.status_code == 204
    assert len(mailoutbox) == 1

    response = client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": " teST@locAlhost.nl ", "base_url": "http://localhost:3000"},
        format="json",
    )
    assert response.status_code == 204
    assert len(mailoutbox) == 2

    email = mailoutbox[0]
    assert "test@localhost.nl" in email.to
    assert email.body.index("http://localhost:3000")

    user = data_fixture.create_user(is_staff=True)
    CoreHandler().update_settings(user, allow_reset_password=False)

    response = client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": " teST@locAlhost.nl ", "base_url": "http://localhost:3000"},
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_send_reset_password_email_password_auth_disabled(
    api_client, data_fixture, mailoutbox
):
    data_fixture.create_password_provider(enabled=False)
    data_fixture.create_user(email="test@localhost.nl")

    response = api_client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": "test@localhost.nl", "base_url": "http://localhost:3000"},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_AUTH_PROVIDER_DISABLED",
        "detail": "Authentication provider is disabled.",
    }
    assert len(mailoutbox) == 0


@pytest.mark.django_db(transaction=True)
def test_send_reset_password_email_password_auth_disabled_staff(
    api_client, data_fixture, mailoutbox
):
    data_fixture.create_password_provider(enabled=False)
    data_fixture.create_user(email="test@localhost.nl", is_staff=True)

    response = api_client.post(
        reverse("api:user:send_reset_password_email"),
        {"email": "test@localhost.nl", "base_url": "http://localhost:3000"},
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_password_reset(data_fixture, client):
    user = data_fixture.create_user(email="test@localhost")
    handler = UserHandler()
    valid_password = "thisIsAValidPassword"
    short_password = "short"
    long_password = (
        "Bgvmt95en6HGJZ9Xz0F8xysQ6eYgo2Y54YzRPxxv10b5n16F4rZ6YH4ulonocwiFK6970KiAxoYhU"
        "LYA3JFDPIQGj5gMZZl25M46sO810Zd3nyBg699a2TDMJdHG7hAAi0YeDnuHuabyBawnb4962OQ1OO"
        "f1MxzFyNWG7NR2X6MZQL5G1V61x56lQTXbvK1AG1IPM87bQ3YAtIBtGT2vK3Wd83q3he5ezMtUfzK"
        "2ibj0WWhf86DyQB4EHRUJjYcBiI78iEJv5hcu33X2I345YosO66cTBWK45SqJEDudrCOq"
    )
    signer = handler.get_reset_password_signer()

    response = client.post(reverse("api:user:reset_password"), {}, format="json")
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = client.post(
        reverse("api:user:reset_password"),
        {"token": "test", "password": valid_password},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "BAD_TOKEN_SIGNATURE"

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(user.id)

    with freeze_time("2020-01-04 12:00"):
        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": valid_password},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "EXPIRED_TOKEN_SIGNATURE"

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(9999)

    with freeze_time("2020-01-02 12:00"):
        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": valid_password},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_USER_NOT_FOUND"

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(user.id)

    with freeze_time("2020-01-02 12:00"):
        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": valid_password},
            format="json",
        )
        assert response.status_code == 204

    user.refresh_from_db()
    assert user.check_password(valid_password)

    with freeze_time("2020-01-02 12:00"):
        token = signer.dumps(user.id)

    with freeze_time("2020-01-02 12:00"):
        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": short_password},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert (
            response_json["detail"]["password"][0]["code"]
            == "password_validation_failed"
        )
        assert (
            response_json["detail"]["password"][0]["error"]
            == "This password is too short. It must contain at least 8 characters."
        )

    user.refresh_from_db()
    assert not user.check_password(short_password)

    with freeze_time("2020-01-02 12:00"):
        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": long_password},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
        assert (
            response_json["detail"]["password"][0]["code"]
            == "password_validation_failed"
        )
        assert (
            response_json["detail"]["password"][0]["error"]
            == "This password is too long. It must not exceed 256 characters."
        )

    user.refresh_from_db()
    assert not user.check_password(long_password)

    user = data_fixture.create_user(is_staff=True)
    CoreHandler().update_settings(user, allow_reset_password=False)

    response = client.post(
        reverse("api:user:reset_password"),
        {"token": token, "password": long_password},
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
def test_password_reset_email_verified_email(data_fixture, client, mailoutbox):
    data_fixture.create_password_provider()
    user = data_fixture.create_user()
    handler = UserHandler()
    signer = handler.get_reset_password_signer()

    with freeze_time("2020-01-01 12:00"):
        token = signer.dumps(user.id)

        response = client.post(
            reverse("api:user:reset_password"),
            {"token": token, "password": "newpassword"},
            format="json",
        )
        assert response.status_code == 204

        user.refresh_from_db()
        assert user.profile.email_verified is True


@pytest.mark.django_db
def test_change_password(data_fixture, client):
    data_fixture.create_password_provider()
    valid_old_password = "thisIsAValidPassword"
    valid_new_password = "thisIsAValidNewPassword"
    short_password = "short"
    long_password = (
        "Bgvmt95en6HGJZ9Xz0F8xysQ6eYgo2Y54YzRPxxv10b5n16F4rZ6YH4ulonocwiFK6970KiAxoYhU"
        "LYA3JFDPIQGj5gMZZl25M46sO810Zd3nyBg699a2TDMJdHG7hAAi0YeDnuHuabyBawnb4962OQ1OO"
        "f1MxzFyNWG7NR2X6MZQL5G1V61x56lQTXbvK1AG1IPM87bQ3YAtIBtGT2vK3Wd83q3he5ezMtUfzK"
        "2ibj0WWhf86DyQB4EHRUJjYcBiI78iEJv5hcu33X2I345YosO66cTBWK45SqJEDudrCOq"
    )
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password=valid_old_password
    )

    response = client.post(
        reverse("api:user:change_password"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = client.post(
        reverse("api:user:change_password"),
        {"old_password": "INCORRECT", "new_password": valid_new_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_OLD_PASSWORD"

    user.refresh_from_db()
    assert user.check_password(valid_old_password)

    response = client.post(
        reverse("api:user:change_password"),
        {"old_password": valid_old_password, "new_password": short_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["new_password"][0]["code"]
        == "password_validation_failed"
    )
    assert (
        response_json["detail"]["new_password"][0]["error"]
        == "This password is too short. It must contain at least 8 characters."
    )

    user.refresh_from_db()
    assert user.check_password(valid_old_password)

    response = client.post(
        reverse("api:user:change_password"),
        {"old_password": valid_old_password, "new_password": long_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert (
        response_json["detail"]["new_password"][0]["code"]
        == "password_validation_failed"
    )
    assert (
        response_json["detail"]["new_password"][0]["error"]
        == "This password is too long. It must not exceed 256 characters."
    )

    user.refresh_from_db()
    assert user.check_password(valid_old_password)

    response = client.post(
        reverse("api:user:change_password"),
        {"old_password": valid_old_password, "new_password": valid_new_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 204

    user.refresh_from_db()
    assert user.check_password(valid_new_password)


@pytest.mark.django_db
def test_change_password_auth_disabled(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=False)
    valid_old_password = "thisIsAValidPassword"
    valid_new_password = "thisIsAValidNewPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password=valid_old_password
    )

    response = api_client.post(
        reverse("api:user:change_password"),
        {"old_password": valid_old_password, "new_password": valid_new_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_AUTH_PROVIDER_DISABLED",
        "detail": "Authentication provider is disabled.",
    }


@pytest.mark.django_db
def test_change_password_auth_disabled_staff(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=False)
    valid_old_password = "thisIsAValidPassword"
    valid_new_password = "thisIsAValidNewPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password=valid_old_password, is_staff=True
    )

    response = api_client.post(
        reverse("api:user:change_password"),
        {"old_password": valid_old_password, "new_password": valid_new_password},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    user.refresh_from_db()
    assert user.check_password(valid_new_password)


@pytest.mark.django_db
def test_dashboard(data_fixture, client):
    user, token = data_fixture.create_user_and_token(email="test@localhost")
    workspace_1 = data_fixture.create_workspace(name="Test1")
    workspace_2 = data_fixture.create_workspace()
    invitation_1 = data_fixture.create_workspace_invitation(
        workspace=workspace_1, email="test@localhost"
    )
    data_fixture.create_workspace_invitation(
        workspace=workspace_1, email="test2@localhost"
    )
    data_fixture.create_workspace_invitation(
        workspace=workspace_2, email="test3@localhost"
    )

    response = client.get(
        reverse("api:user:dashboard"), format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    response_json = response.json()
    assert len(response_json["workspace_invitations"]) == 1
    assert response_json["workspace_invitations"][0]["id"] == invitation_1.id
    assert response_json["workspace_invitations"][0]["email"] == invitation_1.email
    assert response_json["workspace_invitations"][0]["invited_by"] == (
        invitation_1.invited_by.first_name
    )
    assert response_json["workspace_invitations"][0]["workspace"] == "Test1"
    assert response_json["workspace_invitations"][0]["message"] == invitation_1.message
    assert "created_on" in response_json["workspace_invitations"][0]


@pytest.mark.django_db
def test_additional_user_data(api_client, data_fixture):
    data_fixture.create_password_provider()

    class TmpUserDataType(UserDataType):
        type = "type"

        def get_user_data(self, user, request) -> dict:
            return True

    plugin_mock = TmpUserDataType()
    with patch.dict(user_data_registry.registry, {"tmp": plugin_mock}):
        response = api_client.post(
            reverse("api:user:index"),
            {
                "name": "Test1",
                "email": "test@test.nl",
                "password": "thisIsAValidPassword",
                "authenticate": True,
            },
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert response_json["tmp"] is True

        response = api_client.post(
            reverse("api:user:token_auth"),
            {"email": "test@test.nl", "password": "thisIsAValidPassword"},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert response_json["tmp"] is True

        response = api_client.post(
            reverse("api:user:token_refresh"),
            {"refresh_token": response_json["refresh_token"]},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert response_json["tmp"] is True


@pytest.mark.django_db
def test_schedule_user_deletion(client, data_fixture):
    valid_password = "aValidPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password=valid_password, is_staff=True
    )

    response = client.post(
        reverse("api:user:schedule_account_deletion"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_IS_LAST_ADMIN"

    # Creates a new staff user
    data_fixture.create_user(email="test2@localhost", is_staff=True)

    response = client.post(
        reverse("api:user:schedule_account_deletion"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    user.refresh_from_db()
    assert user.profile.to_be_deleted is True


@pytest.mark.django_db
def test_token_error_if_user_deleted_or_disabled(api_client, data_fixture):
    user, _ = data_fixture.create_user_and_token(
        email="test@localhost", password="test"
    )
    refresh_token = data_fixture.generate_refresh_token(user)

    # deactivate user and see that token is no longer valid
    user.is_active = False
    user.save()

    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_INVALID_REFRESH_TOKEN",
        "detail": "Refresh token is expired or invalid.",
    }

    # reactivate the user
    user.is_active = True
    user.save()

    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_200_OK

    # schedule the user for deletion and see that token is no longer valid again
    user.profile.to_be_deleted = True
    user.profile.save()

    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_INVALID_REFRESH_TOKEN",
        "detail": "Refresh token is expired or invalid.",
    }

    # remove the user_id from the token
    token_object = RefreshToken(refresh_token)
    del token_object.payload[jwt_settings.USER_ID_CLAIM]
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": str(token_object)},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_INVALID_REFRESH_TOKEN",
        "detail": "Refresh token is expired or invalid.",
    }


@pytest.mark.django_db
def test_create_user_password_auth_disabled(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=False)
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password="test"
    )

    response = api_client.post(
        reverse("api:user:index"),
        {"name": "Test1", "email": "test@test.nl", "password": "thisIsAValidPassword"},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_AUTH_PROVIDER_DISABLED",
        "detail": "Authentication provider is disabled.",
    }


@pytest.mark.django_db
def test_verify_email_address_with_login(client, data_fixture):
    user = data_fixture.create_user()
    token = UserHandler().create_email_verification_token(user)

    response = client.post(
        reverse("api:user:verify_email"),
        {"token": token},
        format="json",
    )

    response_json = response.json()
    assert "token" in response_json
    assert "refresh_token" in response_json
    assert "user" in response_json
    assert response_json["user"]["username"] == user.email
    assert response.status_code == HTTP_200_OK
    user.refresh_from_db()
    assert user.profile.email_verified is True


@pytest.mark.django_db
def test_verify_email_address_no_login(client, data_fixture):
    user, jwt_token = data_fixture.create_user_and_token()
    token = UserHandler().create_email_verification_token(user)

    response = client.post(
        reverse("api:user:verify_email"),
        {"token": token},
        HTTP_AUTHORIZATION=f"JWT {jwt_token}",
        format="json",
    )

    response_json = response.json()
    assert response_json["email"] == user.email
    assert response.status_code == HTTP_200_OK
    user.refresh_from_db()
    assert user.profile.email_verified is True


@pytest.mark.django_db
def test_verify_email_address_already_verified(client, data_fixture):
    user = data_fixture.create_user()
    profile = user.profile
    profile.email_verified = True
    profile.save()
    token = UserHandler().create_email_verification_token(user)

    response = client.post(
        reverse("api:user:verify_email"),
        {"token": token},
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_verify_email_address_inactive_user(client, data_fixture):
    user = data_fixture.create_user(is_active=False)
    token = UserHandler().create_email_verification_token(user)

    response = client.post(
        reverse("api:user:verify_email"),
        {"token": token},
        format="json",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db(transaction=True)
def test_send_verify_email_address(client, data_fixture, mailoutbox):
    user, token = data_fixture.create_user_and_token()

    response = client.post(
        reverse("api:user:send_verify_email"),
        {
            "email": user.email,
        },
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 1


@pytest.mark.django_db(transaction=True)
def test_send_verify_email_address_user_not_found(client, data_fixture, mailoutbox):
    response = client.post(
        reverse("api:user:send_verify_email"),
        {
            "email": "doesntexist@example.com",
        },
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_send_verify_email_address_already_verified(client, data_fixture, mailoutbox):
    user, token = data_fixture.create_user_and_token()
    profile = user.profile
    profile.email_verified = True
    profile.save()

    response = client.post(
        reverse("api:user:send_verify_email"),
        {
            "email": user.email,
        },
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_send_verify_email_address_inactive_user(client, data_fixture, mailoutbox):
    user, token = data_fixture.create_user_and_token(is_active=False)

    response = client.post(
        reverse("api:user:send_verify_email"),
        {
            "email": user.email,
        },
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 0


@pytest.mark.django_db
@patch("baserow.core.user.handler.share_onboarding_details_with_baserow")
def test_share_onboarding_details_with_baserow(mock_task, client, data_fixture):
    data_fixture.update_settings(instance_id="1")
    user, token = data_fixture.create_user_and_token()

    response = client.post(
        reverse("api:user:share_onboarding_details_with_baserow"),
        {
            "team": "Marketing",
            "role": "CEO",
            "size": "11 - 50",
            "country": "The Netherlands",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    mock_task.delay.assert_called_with(
        email=user.email,
        team="Marketing",
        role="CEO",
        size="11 - 50",
        country="The Netherlands",
    )


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation(data_fixture, client, mailoutbox):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password=valid_password
    )

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "newemail@test.nl",
            "password": "wrongpassword",
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_INVALID_OLD_PASSWORD"

    data_fixture.create_user(email="existing@test.nl")
    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "existing@test.nl",
            "password": valid_password,
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_EMAIL_ALREADY_EXISTS"

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "newemail@test.nl",
            "password": valid_password,
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to[0] == "newemail@test.nl"
    assert "Confirm email address change" in mailoutbox[0].subject


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation_password_auth_disabled(
    data_fixture, client, mailoutbox
):
    data_fixture.create_password_provider(enabled=False)
    valid_password = "thisIsAValidPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password=valid_password
    )

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "newemail@test.nl",
            "password": valid_password,
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_AUTH_PROVIDER_DISABLED",
        "detail": "Authentication provider is disabled.",
    }
    assert len(mailoutbox) == 0


@pytest.mark.django_db(transaction=True)
def test_send_change_email_confirmation_without_password(
    data_fixture, client, mailoutbox
):
    data_fixture.create_password_provider()
    user, token = data_fixture.create_user_and_token(email="test@test.nl")
    user.password = ""
    user.save()

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "newemail@test.nl",
            "password": "dummy_password",  # Provided but user has no password
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": "ERROR_CHANGE_EMAIL_NOT_ALLOWED",
        "detail": "Email changes are only allowed for password-based accounts.",
    }
    assert len(mailoutbox) == 0


@pytest.mark.django_db(transaction=True)
def test_change_email(data_fixture, client, mailoutbox):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password=valid_password
    )

    response = client.post(
        reverse("api:user:send_change_email_confirmation"),
        {
            "new_email": "newemail@test.nl",
            "password": valid_password,
            "base_url": f"{settings.PUBLIC_WEB_FRONTEND_URL}/change-email",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert len(mailoutbox) == 1

    handler = UserHandler()
    signer = handler.get_change_email_signer()
    change_token = signer.dumps({"user_id": user.id, "new_email": "newemail@test.nl"})

    response = client.post(
        reverse("api:user:change_email"),
        {"token": "invalid_token"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "BAD_TOKEN_SIGNATURE"

    response = client.post(
        reverse("api:user:change_email"),
        {"token": change_token},
        format="json",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    user.refresh_from_db()
    assert user.email == "newemail@test.nl"
    assert user.username == "newemail@test.nl"

    response = client.post(
        reverse("api:user:change_email"),
        {"token": change_token},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_EMAIL_ALREADY_CHANGED"

    user.refresh_from_db()
    assert user.email == "newemail@test.nl"
    assert user.username == "newemail@test.nl"


@pytest.mark.django_db
def test_change_email_with_expired_token(data_fixture, client):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@test.nl", password=valid_password)

    handler = UserHandler()
    signer = handler.get_change_email_signer()

    with freeze_time("2023-01-01 12:00:00"):
        change_token = signer.dumps(
            {"user_id": user.id, "new_email": "newemail@test.nl"}
        )

    with freeze_time("2023-01-10 12:00:00"):  # More than the token max age
        response = client.post(
            reverse("api:user:change_email"),
            {"token": change_token},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response_json["error"] == "EXPIRED_TOKEN_SIGNATURE"


@pytest.mark.django_db
def test_change_email_same_as_current(data_fixture, client):
    data_fixture.create_password_provider()
    valid_password = "thisIsAValidPassword"
    user = data_fixture.create_user(email="test@test.nl", password=valid_password)

    handler = UserHandler()
    signer = handler.get_change_email_signer()

    change_token = signer.dumps({"user_id": user.id, "new_email": "test@test.nl"})
    response = client.post(
        reverse("api:user:change_email"),
        {"token": change_token},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_EMAIL_ALREADY_CHANGED"

    change_token = signer.dumps({"user_id": user.id, "new_email": "TeSt@TeSt.nl"})
    response = client.post(
        reverse("api:user:change_email"),
        {"token": change_token},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_EMAIL_ALREADY_CHANGED"

    user.refresh_from_db()
    assert user.email == "test@test.nl"

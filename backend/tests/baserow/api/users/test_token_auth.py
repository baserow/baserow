from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.shortcuts import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.core.handler import CoreHandler
from baserow.core.models import BlacklistedToken, Settings, UserLogEntry
from baserow.core.registries import Plugin, plugin_registry
from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import generate_session_tokens_for_user
from baserow.core.utils import generate_hash
from baserow.test_utils.helpers import AnyStr

User = get_user_model()


@pytest.mark.django_db
def test_token_auth(api_client, data_fixture):
    data_fixture.create_password_provider()

    class TmpPlugin(Plugin):
        type = "tmp_plugin"
        called = False

        def user_signed_in(self, user):
            self.called = True

    plugin_mock = TmpPlugin()

    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1", is_active=True
    )

    assert not user.last_login

    response = api_client.post(
        reverse("api:user:token_auth"), {"password": "password"}, format="json"
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["email"] == ["This field is required."]

    # accept username for backward compatibility
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"username": "invalid_mail", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["username"] == ["Enter a valid email address."]

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "invalid_mail", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["email"] == ["Enter a valid email address."]

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "no_existing@test.nl", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert (
        response_json["detail"] == "No active account found with the given credentials."
    )

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@test.nl", "password": "wrong_password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert (
        response_json["detail"] == "No active account found with the given credentials."
    )

    with patch.dict(plugin_registry.registry, {"tmp": plugin_mock}):
        with freeze_time("2020-01-01 12:00"):
            response = api_client.post(
                reverse("api:user:token_auth"),
                {"email": "test@test.nl", "password": "password"},
                format="json",
            )
            response_json = response.json()
            assert response.status_code == HTTP_200_OK
            assert "access_token" in response_json
            assert "refresh_token" in response_json
            assert "user" in response_json
            assert response_json["user"]["username"] == "test@test.nl"
            assert response_json["user"]["first_name"] == "Test1"
            assert response_json["user"]["id"] == user.id
            assert response_json["user"]["is_staff"] is False
            assert plugin_mock.called

    user.refresh_from_db()
    assert user.last_login == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)

    logs = UserLogEntry.objects.all()
    assert len(logs) == 1
    assert logs[0].actor_id == user.id
    assert logs[0].action == "SIGNED_IN"
    assert logs[0].timestamp == datetime(2020, 1, 1, 12, 00, tzinfo=timezone.utc)

    with freeze_time("2020-01-02 12:00"):
        response = api_client.post(
            reverse("api:user:token_auth"),
            {"email": " teSt@teSt.nL ", "password": "password"},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert "access_token" in response_json
        assert "refresh_token" in response_json
        assert "user" in response_json
        assert response_json["user"]["username"] == "test@test.nl"
        assert response_json["user"]["first_name"] == "Test1"
        assert response_json["user"]["id"] == user.id
        assert response_json["user"]["is_staff"] is False

    user.refresh_from_db()
    assert user.last_login == datetime(2020, 1, 2, 12, 0, tzinfo=timezone.utc)

    data_fixture.create_user(
        email="test2@test.nl", password="password", first_name="Test1", is_active=False
    )
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test2@test.nl", "password": "wrong_password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert (
        response_json["detail"] == "No active account found with the given credentials."
    )

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test2@test.nl", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_DEACTIVATED_USER"
    assert response_json["detail"] == "User account has been disabled."

    # Check that a login cancel user deletion
    user_to_be_deleted = data_fixture.create_user(
        email="test3@test.nl", password="password", to_be_deleted=True
    )

    # check that the user cannot refresh the token if set to be deleted
    refresh_token = str(RefreshToken.for_user(user_to_be_deleted))
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response_json = response.json()
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"
    assert response_json["detail"] == "Refresh token is expired or invalid."

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test3@test.nl", "password": "password"},
        format="json",
    )

    user_to_be_deleted.refresh_from_db()
    assert user_to_be_deleted.profile.to_be_deleted is False

    # check that now the user can refresh the token
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "access_token" in response_json
    assert "user" in response_json


@pytest.mark.django_db
def test_token_auth_email_verification_required(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_EMAIL_VERIFICATION_REQUIRED"


@pytest.mark.django_db
def test_token_auth_email_verification_not_required(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.RECOMMENDED
    settings.save()

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json


@pytest.mark.django_db
def test_token_auth_email_verification_not_required_staff(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(
        email="test@example.com", password="password", is_staff=True
    )
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json


@pytest.mark.django_db
def test_token_password_auth_disabled(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=False)
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password="test"
    )

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@localhost", "password": "test"},
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_AUTH_PROVIDER_DISABLED",
        "detail": "Authentication provider is disabled.",
    }


@pytest.mark.django_db
def test_token_auth_2fa_required(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=True)
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password="test"
    )
    data_fixture.configure_totp(user)

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@localhost", "password": "test"},
        format="json",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json() == {"two_factor_auth": "totp", "token": AnyStr()}


@pytest.mark.django_db
def test_token_password_auth_disabled_superadmin(api_client, data_fixture):
    data_fixture.create_password_provider(enabled=False)
    user, token = data_fixture.create_user_and_token(
        email="test@localhost", password="test", is_staff=True
    )

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@localhost", "password": "test"},
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "access_token" in response_json
    assert "refresh_token" in response_json
    assert "user" in response_json
    assert response_json["user"]["id"] == user.id
    assert response_json["user"]["is_staff"] is True


@pytest.mark.django_db
def test_token_refresh(api_client, data_fixture):
    class TmpPlugin(Plugin):
        type = "tmp_plugin"
        called = False

        def user_signed_in(self, user):
            self.called = True

    plugin_mock = TmpPlugin()

    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )
    refresh_token = str(RefreshToken.for_user(user))

    response = api_client.post(
        reverse("api:user:token_refresh"), {"token": "WRONG_TOKEN"}, format="json"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    response_json = response.json()
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"
    assert response_json["detail"] == "Refresh token is expired or invalid."

    # DEPRECATED: "token" as body param is deprecated, use "refresh_token" instead
    with patch.dict(plugin_registry.registry, {"tmp": plugin_mock}):
        response = api_client.post(
            reverse("api:user:token_refresh"),
            {"token": refresh_token},
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert "access_token" in response_json
        assert "user" in response_json
        assert response_json["user"]["username"] == "test@test.nl"
        assert response_json["user"]["first_name"] == "Test1"
        assert response_json["user"]["id"] == user.id
        assert response_json["user"]["is_staff"] is False
        assert not plugin_mock.called

    with patch.dict(plugin_registry.registry, {"tmp": plugin_mock}):
        response = api_client.post(
            reverse("api:user:token_refresh"),
            {"refresh_token": refresh_token},
            format="json",
        )
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert "access_token" in response_json
        assert "user" in response_json
        assert response_json["user"]["username"] == "test@test.nl"
        assert response_json["user"]["first_name"] == "Test1"
        assert response_json["user"]["id"] == user.id
        assert response_json["user"]["is_staff"] is False
        assert not plugin_mock.called

    with freeze_time("2019-01-01 12:00"):
        response = api_client.post(
            reverse("api:user:token_refresh"),
            json={"refresh_token": str(RefreshToken.for_user(user))},
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED
        response_json = response.json()
        assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"
        assert response_json["detail"] == "Refresh token is expired or invalid."


@pytest.mark.django_db
def test_refresh_token_is_invalidated_after_password_change(api_client, data_fixture):
    with freeze_time("2020-01-01 12:00"):
        user = data_fixture.create_user(
            email="test@test.nl",
            password="password",
            first_name="Test1",
            is_active=True,
        )

        response = api_client.post(
            reverse("api:user:token_auth"),
            {"email": "test@test.nl", "password": "password"},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        refresh_token = response_json["refresh_token"]

    with freeze_time("2020-01-01 12:01"):
        UserHandler().change_password(user, "password", "test1234")

    with freeze_time("2020-01-01 12:02"):
        response = api_client.post(
            reverse("api:user:token_refresh"),
            {"refresh_token": refresh_token},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_401_UNAUTHORIZED
        assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_token_email_verification_required(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")

    # obtain refresh token
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    refresh_token = response_json["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is not possible any more
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_EMAIL_VERIFICATION_REQUIRED"


@pytest.mark.django_db
def test_refresh_token_email_verification_not_enforced(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")

    # obtain refresh token
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    refresh_token = response_json["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.RECOMMENDED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is possible
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_refresh_token_email_verification_not_required(api_client, data_fixture):
    user = data_fixture.create_user(email="test@example.com", password="password")

    # obtain refresh token
    # the auth claim will not be set to password authentication
    tokens = generate_session_tokens_for_user(
        user, include_refresh_token=True, verified_email_claim=None
    )
    refresh_token = tokens["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is possible
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_refresh_token_email_verification_not_required_staff(api_client, data_fixture):
    user = data_fixture.create_user(
        email="test@example.com", password="password", is_staff=True
    )

    # obtain refresh token
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    refresh_token = response_json["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is possible
    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_token_verify(api_client, data_fixture):
    class TmpPlugin(Plugin):
        type = "tmp_plugin"
        called = False

        def user_signed_in(self, user):
            self.called = True

    plugin_mock = TmpPlugin()

    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )
    refresh_token = str(RefreshToken.for_user(user))

    response = api_client.post(
        reverse("api:user:token_verify"), {"token": "WRONG_TOKEN"}, format="json"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    with patch.dict(plugin_registry.registry, {"tmp": plugin_mock}):
        response = api_client.post(
            reverse("api:user:token_verify"),
            {"refresh_token": refresh_token},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        assert "user" in response_json
        assert response_json["user"]["username"] == "test@test.nl"
        assert response_json["user"]["first_name"] == "Test1"
        assert response_json["user"]["id"] == user.id
        assert response_json["user"]["is_staff"] is False
        assert not plugin_mock.called

    with freeze_time("2019-01-01 12:00"):
        response = api_client.post(
            reverse("api:user:token_verify"),
            json={"refresh_token": str(RefreshToken.for_user(user))},
        )
        assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_token_verify_email_verification_required(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")

    # obtain refresh token
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    refresh_token = response_json["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is not possible any more
    response = api_client.post(
        reverse("api:user:token_verify"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_EMAIL_VERIFICATION_REQUIRED"


@pytest.mark.django_db
def test_token_verify_email_verification_not_required(api_client, data_fixture):
    user = data_fixture.create_user(email="test@example.com", password="password")

    # obtain refresh token
    # the auth claim will not be set to password authentication
    tokens = generate_session_tokens_for_user(
        user, include_refresh_token=True, verified_email_claim=None
    )
    refresh_token = tokens["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is possible
    response = api_client.post(
        reverse("api:user:token_verify"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_token_verify_email_verification_not_required_staff(api_client, data_fixture):
    user = data_fixture.create_user(
        email="test@example.com", password="password", is_staff=True
    )

    # obtain refresh token
    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    refresh_token = response_json["refresh_token"]

    # change email verification setting
    settings = CoreHandler().get_settings()
    settings.email_verification = Settings.EmailVerificationOptions.ENFORCED
    settings.save()

    profile = user.profile
    profile.email_verified = False
    profile.save()

    # using the refresh token is possible
    response = api_client.post(
        reverse("api:user:token_verify"),
        {"refresh_token": refresh_token},
        format="json",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_verify_token_is_invalidated_after_password_change(api_client, data_fixture):
    with freeze_time("2020-01-01 12:00"):
        user = data_fixture.create_user(
            email="test@test.nl",
            password="password",
            first_name="Test1",
            is_active=True,
        )

        response = api_client.post(
            reverse("api:user:token_auth"),
            {"email": "test@test.nl", "password": "password"},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        refresh_token = response_json["refresh_token"]

    with freeze_time("2020-01-01 12:01"):
        UserHandler().change_password(user, "password", "test1234")

    with freeze_time("2020-01-01 12:02"):
        response = api_client.post(
            reverse("api:user:token_verify"),
            {"refresh_token": refresh_token},
            format="json",
        )
        response_json = response.json()
        assert response.status_code == HTTP_401_UNAUTHORIZED
        assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_token_blacklist(api_client, data_fixture):
    user = data_fixture.create_user(
        email="test@test.nl", password="password", first_name="Test1"
    )

    response = api_client.post(
        reverse("api:user:token_blacklist"),
        {"refresh_token": "INVALID_TOKEN"},
        format="json",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    response = api_client.post(
        reverse("api:user:token_blacklist"),
        {},
        format="json",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    refresh_token = RefreshToken.for_user(user)
    refresh_token_str = str(RefreshToken.for_user(user))

    response = api_client.post(
        reverse("api:user:token_blacklist"),
        {"refresh_token": refresh_token_str},
        format="json",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    token = BlacklistedToken.objects.all().first()

    assert refresh_token.payload["exp"] == token.expires_at.timestamp()
    assert token.hashed_token == generate_hash(refresh_token_str)

    response = api_client.post(
        reverse("api:user:token_refresh"),
        {"token": refresh_token_str},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"

    response = api_client.post(
        reverse("api:user:token_verify"),
        {"refresh_token": refresh_token_str},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_token_auth_two_factor_token_is_not_access_token(api_client, data_fixture):
    data_fixture.create_password_provider()
    user = data_fixture.create_user(email="test@example.com", password="password")
    data_fixture.configure_totp(user)

    response = api_client.post(
        reverse("api:user:token_auth"),
        {"email": "test@example.com", "password": "password"},
        format="json",
    )

    response_json = response.json()
    two_fa_token = response_json["token"]

    # using 2fa token as access token should not work
    response = api_client.patch(
        reverse("api:user:account"),
        {
            "first_name": "Changed name",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {two_fa_token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED, response_json
    assert response_json["error"] == "ERROR_INVALID_ACCESS_TOKEN"

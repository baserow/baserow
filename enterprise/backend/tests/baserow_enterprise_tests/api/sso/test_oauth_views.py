import json
from unittest.mock import patch
from urllib.parse import parse_qsl, urlparse

from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import HTTP_302_FOUND
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.api.user.jwt import get_user_from_token
from baserow.core.auth_provider.types import UserInfo
from baserow.core.handler import CoreHandler
from baserow.core.models import Settings, WorkspaceUser
from baserow_enterprise.sso.exceptions import AuthFlowError

GET_USER_INFO = (
    "baserow_enterprise.sso.oauth2.auth_provider_types."
    "GoogleAuthProviderType.get_user_info"
)


@pytest.fixture(autouse=True)
def enable_roles_for_all_tests_here(synced_roles):
    pass


def create_get_user_info_stub(provider):
    def get_user_info_stub(self, instance, code, session):
        assert instance == provider
        assert code == "validcode"
        data = json.loads(session.pop("oauth_request_data"))
        return (
            UserInfo(
                email="testuser@example.com",
                name="Test User",
                language=data.get("language", "en"),
                workspace_invitation_token=data.get("workspace_invitation_token", None),
            ),
            data.get("original", ""),
        )

    return get_user_info_stub


@pytest.mark.django_db
def test_oauth2_login_feature_not_active(api_client, enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    response = api_client.get(
        reverse("api:enterprise_sso_oauth2:login", kwargs={"provider_id": provider.id}),
        format="json",
    )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
        "error?error=errorSsoFeatureNotActive"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_login_provider_doesnt_exist(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    response = api_client.get(
        reverse("api:enterprise_sso_oauth2:login", kwargs={"provider_id": 50}),
        format="json",
    )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
        "error?error=errorProviderDoesNotExist"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_login_with_url_param(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )
    response = api_client.get(
        reverse(
            "api:enterprise_sso_oauth2:login",
            kwargs={"provider_id": provider.id},
        )
        + "?original=templates&workspace_invitation_token=t&language=en",
        format="json",
    )

    assert response.status_code == HTTP_302_FOUND

    location = response.headers["Location"]

    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=g_client_id" in location

    session_data = json.loads(api_client.session.pop("oauth_request_data"))
    assert session_data == {
        "original": "templates",
        "workspace_invitation_token": "t",
        "language": "en",
    }


@pytest.mark.django_db
def test_oauth2_callback_feature_not_active(api_client, enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    response = api_client.get(
        reverse(
            "api:enterprise_sso_oauth2:callback", kwargs={"provider_id": provider.id}
        ),
        format="json",
    )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
        "error?error=errorSsoFeatureNotActive"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_provider_doesnt_exist(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    response = api_client.get(
        reverse("api:enterprise_sso_oauth2:callback", kwargs={"provider_id": 50}),
        format="json",
    )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == (
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
        "error?error=errorProviderDoesNotExist"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_signup_success(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
        )

        parsed_url = urlparse(response.headers["Location"])
        params = dict(parse_qsl(parsed_url.query))
        user = get_user_from_token(params["token"], token_class=RefreshToken)
        assert user.email == "testuser@example.com"
        assert user.first_name == "Test User"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_signup_set_language(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "language": "es",
                "oauth_state": "generated_oauth_state",
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
        )

        parsed_url = urlparse(response.headers["Location"])
        params = dict(parse_qsl(parsed_url.query))
        user = get_user_from_token(params["token"], token_class=RefreshToken)
        assert user.email == "testuser@example.com"
        assert user.first_name == "Test User"
        assert user.profile.language == "es"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_signup_workspace_invitation(
    api_client, data_fixture, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    invitation = data_fixture.create_workspace_invitation(email="testuser@example.com")
    core_handler = CoreHandler()
    signer = core_handler.get_workspace_invitation_signer()
    workspace_invitation_token = signer.dumps(invitation.id)

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "workspace_invitation_token": workspace_invitation_token,
                "oauth_state": "generated_oauth_state",
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
        )

        parsed_url = urlparse(response.headers["Location"])
        params = dict(parse_qsl(parsed_url.query))
        user = get_user_from_token(params["token"], token_class=RefreshToken)
        assert user.email == "testuser@example.com"
        assert user.first_name == "Test User"

        assert WorkspaceUser.objects.get(user=user, workspace=invitation.workspace)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_signup_workspace_invitation_email_mismatch(
    api_client, data_fixture, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    invitation = data_fixture.create_workspace_invitation(
        email="differenttestuser@example.com"
    )
    core_handler = CoreHandler()
    signer = core_handler.get_workspace_invitation_signer()
    workspace_invitation_token = signer.dumps(invitation.id)

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "workspace_invitation_token": workspace_invitation_token,
                "oauth_state": "generated_oauth_state",
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            (
                f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
                "error?error=errorWorkspaceInvitationEmailMismatch"
            )
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_signup_disabled(api_client, enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    # disable signups
    instance_settings = Settings.objects.all()[:1].get()
    instance_settings.allow_new_signups = False
    instance_settings.save()

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
            "error?error=errorSignupDisabled"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_login_success(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    When a user already have an account associated with the specific provider,
    they can log in.
    """

    user, token = data_fixture.create_user_and_token(
        first_name="Test User", email="testuser@example.com"
    )

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )
    provider.users.add(user)
    provider.save()

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"].startswith(
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
        )

        parsed_url = urlparse(response.headers["Location"])
        params = dict(parse_qsl(parsed_url.query))
        user = get_user_from_token(params["token"], token_class=RefreshToken)
        assert user.email == "testuser@example.com"
        assert user.first_name == "Test User"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_login_deactivated_user(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    Deactivated user can't log in anymore.
    """

    user, token = data_fixture.create_user_and_token(
        first_name="Test User", email="testuser@example.com", is_active=False
    )

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )
    provider.users.add(user)
    provider.save()

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
            "error?error=errorUserDeactivated"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_login_different_provider(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    Existing user account can't log in through a different auth provider.
    """

    user, token = data_fixture.create_user_and_token(
        first_name="Test User", email="testuser@example.com"
    )

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    with patch(
        GET_USER_INFO,
        create_get_user_info_stub(provider),
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
            "error?error=errorDifferentProvider"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_login_auth_flow_error(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token = data_fixture.create_user_and_token(
        first_name="Test User", email="testuser@example.com"
    )

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    def get_user_info_raise_error(self, instance, code, session):
        raise AuthFlowError()

    with patch(
        GET_USER_INFO,
        get_user_info_raise_error,
    ):
        session = api_client.session
        session["oauth_request_data"] = json.dumps(
            {"original": "templates", "oauth_state": "generated_oauth_state"}
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + "?code=validcode",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/"
            "error?error=errorAuthFlowError"
        )

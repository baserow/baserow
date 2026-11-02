import json
import random
import string
from unittest.mock import patch
from urllib.parse import parse_qsl, urlencode, urlparse

from django.conf import settings
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
import responses
from loguru import logger
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
OAUTH_STATE = "generated_oauth_state"


@pytest.fixture(autouse=True)
def enable_roles_for_all_tests_here(synced_roles):
    pass


def create_get_user_info_stub(provider):
    def get_user_info_stub(self, instance, code, session):
        assert instance == provider
        assert code == "validcode"
        data = json.loads(session.pop("oauth_request_data", "{}"))
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
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorSsoFeatureNotActive"
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
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorSsoFeatureNotActive"
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "language": "es",
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "workspace_invitation_token": workspace_invitation_token,
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps(
            {
                "original": "templates",
                "workspace_invitation_token": workspace_invitation_token,
            }
        )
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorSignupDisabled"
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorUserDeactivated"
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
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
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
            format="json",
        )

        assert response.status_code == HTTP_302_FOUND
        assert response.headers["Location"] == (
            f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorAuthFlowError"
        )


# The MCP consent page carries the authorize request in its path, because the
# return URL only keeps the path.
MCP_CONSENT_PATH = "/mcp-authorize/cmVzcG9uc2VfdHlwZT1jb2RlJmNsaWVudF9pZD1hYmM"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_returns_to_the_mcp_consent_page(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    with patch(GET_USER_INFO, create_get_user_info_stub(provider)):
        session = api_client.session
        provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
        session["oauth_request_data"] = json.dumps({"original": MCP_CONSENT_PATH})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = api_client.get(
            reverse(
                "api:enterprise_sso_oauth2:callback",
                kwargs={"provider_id": provider.id},
            )
            + f"?code=validcode&state={OAUTH_STATE}",
            format="json",
        )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}{MCP_CONSENT_PATH}?token="
    )


def get_callback_url(provider, **query_params):
    url = reverse(
        "api:enterprise_sso_oauth2:callback", kwargs={"provider_id": provider.id}
    )
    return f"{url}?{urlencode(query_params)}"


AUTH_FLOW_ERROR_URL = (
    f"{settings.PUBLIC_WEB_FRONTEND_URL}/login/error?error=errorAuthFlowError"
)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "query_params",
    [
        {},
        {"state": ""},
        {"state": "attacker_state"},
        # A non ASCII value must not break the constant time compare.
        {"state": "\u00e9tat"},
    ],
)
def test_oauth2_callback_rejects_missing_or_wrong_state(
    query_params, api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    session = api_client.session
    provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
    session["oauth_request_data"] = json.dumps({"original": "templates"})
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(provider)
    ) as mock_get_user_info:
        response = api_client.get(
            get_callback_url(provider, code="validcode", **query_params)
        )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("session_has_request_data", [True, False])
def test_oauth2_callback_rejects_session_without_state(
    session_has_request_data, api_client, enterprise_data_fixture
):
    """
    The login CSRF case: the callback carries the state of the attacker's own
    flow, and the victim's browser has no state for it.
    """

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    if session_has_request_data:
        session = api_client.session
        session["oauth_request_data"] = json.dumps({"original": "templates"})
        session.save()
        api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(provider)
    ) as mock_get_user_info:
        response = api_client.get(
            get_callback_url(provider, code="validcode", state="attacker_state")
        )

    assert response.status_code == HTTP_302_FOUND
    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_replay_from_the_same_browser_is_rejected(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )

    session = api_client.session
    provider.get_type().store_oauth_state(provider, session, OAUTH_STATE)
    session["oauth_request_data"] = json.dumps({"original": "templates"})
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    callback_url = get_callback_url(provider, code="validcode", state=OAUTH_STATE)

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(provider)
    ) as mock_get_user_info:
        first_response = api_client.get(callback_url)
        replay_response = api_client.get(callback_url)

    assert first_response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
    )
    assert replay_response.status_code == HTTP_302_FOUND
    assert replay_response.headers["Location"] == AUTH_FLOW_ERROR_URL
    assert mock_get_user_info.call_count == 1


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.example.com"}),
        (
            "openid_connect",
            {
                "base_url": "https://idp.example.com",
                "authorization_url": "https://idp.example.com/authorize",
                "access_token_url": "https://idp.example.com/token",
                "user_info_url": "https://idp.example.com/userinfo",
            },
        ),
    ],
)
def test_oauth2_flow_checks_state_for_every_provider_type(
    provider_type, extra_params, api_client, enterprise_data_fixture
):
    """
    Goes through the real login and callback views, with only the provider's HTTP
    endpoints mocked, so the state comes from what the login view stored.
    """

    enterprise_data_fixture.enable_enterprise()
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type, client_id="client_id", secret="secret", **extra_params
    )
    provider_type_instance = provider.get_type()

    responses.add(
        responses.POST,
        provider_type_instance.get_access_token_url(provider),
        json={"access_token": "testtoken", "token_type": "Bearer"},
    )
    responses.add(
        responses.GET,
        provider_type_instance.get_user_info_url(provider),
        json={"name": "Test User", "email": "testuser@example.com"},
    )
    if provider_type == "github":
        responses.add(
            responses.GET,
            provider_type_instance.EMAILS_URL,
            json=[{"email": "testuser@example.com", "primary": True, "verified": True}],
        )

    login_url = reverse(
        "api:enterprise_sso_oauth2:login", kwargs={"provider_id": provider.id}
    )

    def start_login():
        response = api_client.get(f"{login_url}?original=templates")
        assert response.status_code == HTTP_302_FOUND
        return dict(parse_qsl(urlparse(response.headers["Location"]).query))["state"]

    start_login()
    response = api_client.get(
        get_callback_url(provider, code="validcode", state="attacker_state")
    )
    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    assert len(responses.calls) == 0

    state = start_login()
    callback_url = get_callback_url(provider, code="validcode", state=state)
    response = api_client.get(callback_url)
    assert response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
    )
    calls_after_success = len(responses.calls)
    assert calls_after_success > 0

    response = api_client.get(callback_url)
    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    assert len(responses.calls) == calls_after_success


def start_login(api_client, provider, **query_params):
    """
    Goes through the real login view and returns the state sent to the provider.
    """

    url = reverse(
        "api:enterprise_sso_oauth2:login", kwargs={"provider_id": provider.id}
    )
    response = api_client.get(url, {"original": "templates", **query_params})
    assert response.status_code == HTTP_302_FOUND
    return dict(parse_qsl(urlparse(response.headers["Location"]).query))["state"]


def create_google_and_github_providers(enterprise_data_fixture):
    enterprise_data_fixture.enable_enterprise()
    google = enterprise_data_fixture.create_oauth_provider(
        type="google", client_id="g_client_id", secret="g_secret"
    )
    github = enterprise_data_fixture.create_oauth_provider(
        type="github", client_id="gh_client_id", secret="gh_secret"
    )
    return google, github


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_rejects_state_issued_for_another_provider(
    api_client, enterprise_data_fixture
):
    google, github = create_google_and_github_providers(enterprise_data_fixture)

    state = start_login(api_client, github)

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
    ) as mock_get_user_info:
        response = api_client.get(
            get_callback_url(google, code="validcode", state=state)
        )

    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_login_after_an_abandoned_login_gets_a_new_state(
    api_client, enterprise_data_fixture
):
    google, github = create_google_and_github_providers(enterprise_data_fixture)

    abandoned_state = start_login(api_client, google)
    state_at_other_provider = start_login(api_client, github)
    state_at_same_provider = start_login(api_client, github)

    assert abandoned_state != state_at_other_provider
    assert state_at_other_provider != state_at_same_provider


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_from_a_stale_tab_keeps_the_login_of_the_other_tab_working(
    api_client, enterprise_data_fixture
):
    google, _ = create_google_and_github_providers(enterprise_data_fixture)

    stale_tab_state = start_login(api_client, google)
    other_tab_state = start_login(api_client, google)

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
    ):
        stale_response = api_client.get(
            get_callback_url(google, code="validcode", state=stale_tab_state)
        )
        valid_response = api_client.get(
            get_callback_url(google, code="validcode", state=other_tab_state)
        )

    assert stale_response.headers["Location"] == AUTH_FLOW_ERROR_URL
    assert valid_response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_with_a_wrong_state_keeps_the_stored_state(
    api_client, enterprise_data_fixture
):
    google, _ = create_google_and_github_providers(enterprise_data_fixture)

    state = start_login(api_client, google)

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
    ):
        forced_response = api_client.get(
            get_callback_url(google, code="attacker_code", state="attacker_state")
        )
        valid_response = api_client.get(
            get_callback_url(google, code="validcode", state=state)
        )

    assert forced_response.headers["Location"] == AUTH_FLOW_ERROR_URL
    assert valid_response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/templates?token="
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_callback_replayed_with_an_old_cookie_copy_passes_the_state_check(
    api_client, enterprise_data_fixture
):
    """
    The session is stored in the cookie, so using the state only changes the
    cookie sent back. Only the provider's single use code stops a replay that sends
    an old copy of the cookie.
    """

    google, _ = create_google_and_github_providers(enterprise_data_fixture)

    state = start_login(api_client, google)
    old_cookie = api_client.cookies[settings.SESSION_COOKIE_NAME].value
    callback_url = get_callback_url(google, code="validcode", state=state)

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
    ) as mock_get_user_info:
        api_client.get(callback_url)
        api_client.cookies[settings.SESSION_COOKIE_NAME] = old_cookie
        api_client.get(callback_url)

    assert mock_get_user_info.call_count == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "scenario,expected_reason",
    [
        ("no_state_in_callback", "missing from the callback"),
        ("no_state_in_session", "missing from the session"),
        ("other_provider", "issued for another provider"),
        ("wrong_state", "does not match"),
    ],
)
def test_oauth2_callback_logs_why_the_state_was_rejected(
    scenario, expected_reason, api_client, enterprise_data_fixture
):
    google, github = create_google_and_github_providers(enterprise_data_fixture)

    stored_state = None
    query_params = {"state": "attacker_state"}
    if scenario == "no_state_in_callback":
        stored_state = start_login(api_client, google)
        query_params = {}
    elif scenario == "other_provider":
        stored_state = start_login(api_client, github)
        query_params = {"state": stored_state}
    elif scenario == "wrong_state":
        stored_state = start_login(api_client, google)

    messages = []
    sink_id = logger.add(messages.append, level="WARNING")
    try:
        with patch(
            GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
        ):
            response = api_client.get(
                get_callback_url(google, code="validcode", **query_params)
            )
    finally:
        logger.remove(sink_id)

    assert response.headers["Location"] == AUTH_FLOW_ERROR_URL
    rejections = [m for m in messages if "state" in m.record["message"]]
    assert len(rejections) == 1
    message = rejections[0].record["message"]
    assert expected_reason in message
    assert "google" in message
    assert str(google.id) in message
    # The state sent to the provider must never end up in the logs.
    assert "attacker_state" not in message
    assert not stored_state or stored_state not in message


def random_text(length):
    # Random text barely compresses, unlike a repeated character.
    return "".join(
        random.Random(0).choices(string.ascii_letters + string.digits, k=length)
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_login_never_sets_a_session_cookie_too_big_for_the_browser(
    api_client, enterprise_data_fixture
):
    google, _ = create_google_and_github_providers(enterprise_data_fixture)
    url = reverse("api:enterprise_sso_oauth2:login", kwargs={"provider_id": google.id})
    token = random_text(200)

    for length in [1000, 3000, *range(3600, 4300, 25), 5000, 20000]:
        for query_params in [{}, {"workspace_invitation_token": token}]:
            response = api_client.get(
                url, {"original": f"/{random_text(length)}", **query_params}
            )
            cookie = response.cookies[settings.SESSION_COOKIE_NAME].OutputString()
            assert len(cookie) <= 4096, f"original of {length} chars: {len(cookie)}"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_oauth2_login_with_an_original_too_long_for_the_cookie_still_succeeds(
    api_client, enterprise_data_fixture
):
    google, _ = create_google_and_github_providers(enterprise_data_fixture)

    state = start_login(
        api_client,
        google,
        original=f"/{random_text(5000)}",
        workspace_invitation_token="token",
        language="es",
    )

    request_data = json.loads(api_client.session["oauth_request_data"])
    assert request_data == {"workspace_invitation_token": "token", "language": "es"}
    assert len(api_client.cookies[settings.SESSION_COOKIE_NAME].OutputString()) <= 4096

    # Not an invitation that exists, the login itself is what matters here.
    session = api_client.session
    session["oauth_request_data"] = json.dumps({"language": "es"})
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    with patch(
        GET_USER_INFO, autospec=True, side_effect=create_get_user_info_stub(google)
    ):
        response = api_client.get(
            get_callback_url(google, code="validcode", state=state)
        )

    assert response.headers["Location"].startswith(
        f"{settings.PUBLIC_WEB_FRONTEND_URL}/all-workspaces?token="
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize(
    "original",
    [
        # Fits as is.
        f"/{random_text(3000)}",
        # Longer than the cookie, but it fits once the cookie is compressed.
        f"/{'a' * 6000}",
    ],
)
def test_oauth2_login_keeps_an_original_that_fits_the_cookie(
    original, api_client, enterprise_data_fixture
):
    google, _ = create_google_and_github_providers(enterprise_data_fixture)

    start_login(api_client, google, original=original)

    request_data = json.loads(api_client.session["oauth_request_data"])
    assert request_data["original"] == original

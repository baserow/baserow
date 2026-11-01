from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qsl, urlparse

from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

import pytest
import responses
from rest_framework.status import HTTP_302_FOUND, HTTP_404_NOT_FOUND

from baserow.core.auth_provider.types import UserInfo
from baserow.core.cache import global_cache
from baserow.core.registries import plugin_registry
from baserow_enterprise.application_users.usage import get_over_limit_cache_key
from baserow_enterprise.integrations.common.sso.oauth2.app_auth_provider_types import (
    OpenIdConnectAppAuthProviderType,
)
from baserow_enterprise.integrations.common.sso.oauth2.models import (
    OpenIdConnectAppAuthProviderModel,
)
from baserow_premium.application_user_usage.constants import (
    DEFAULT_APPLICATION_USERS_LIMIT,
)
from baserow_premium.license.plugin import LicensePlugin
from baserow_premium.plugins import PremiumPlugin

from ...local_baserow.helpers import populate_local_baserow_test_data

OAUTH_STATE = "generated_oauth_state"


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


@pytest.fixture
def self_hosted_license_plugin():
    """
    Force the self-hosted license plugin so the application user limit resolves
    from the licenses (the default limit here) in every environment, including
    the SaaS one.
    """

    premium_plugin = plugin_registry.get_by_type(PremiumPlugin)
    with patch.object(
        premium_plugin,
        "get_license_plugin",
        lambda cache_queries=False: LicensePlugin(cache_queries),
    ):
        yield


@pytest.mark.django_db
@override_settings(
    BASEROW_APPLICATION_USER_LIMIT_GRACE_PERIOD_HOURS=1,
)
@patch(
    "baserow_premium.application_user_usage.handler."
    "ApplicationUserUsageHandler.aggregate_user_source_counts"
)
@patch.object(OpenIdConnectAppAuthProviderType, "get_user_info")
def test_oauth2_callback_redirects_with_error_over_application_user_limit(
    mock_get_user_info,
    mock_aggregate_user_source_counts,
    api_client,
    data_fixture,
    self_hosted_license_plugin,
):
    """
    A login through the OIDC app auth provider of a workspace that has been over
    its application user limit for longer than the grace period must redirect
    back to the page the login was initiated from with the
    `errorApplicationUserLimitReached` error code, so the auth form can render it
    inline, instead of signing the user in.
    """

    mock_aggregate_user_source_counts.return_value = DEFAULT_APPLICATION_USERS_LIMIT + 1
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    application_url = user_source.application.get_type().get_application_urls(
        user_source.application.specific
    )[0]
    provider = OpenIdConnectAppAuthProviderModel.objects.create(
        user_source=user_source,
        name="oidc",
        base_url="https://idp.example.com",
        client_id="clientid",
        secret="secret",
    )
    mock_get_user_info.return_value = (
        UserInfo(email="new@baserow.io", name="New user"),
        application_url,
    )

    workspace = user_source.application.specific.get_workspace()
    global_cache.update(
        get_over_limit_cache_key(workspace.id),
        lambda _: (now() - timedelta(hours=2)).isoformat(),
    )

    session = api_client.session
    session["oauth_2_provider_id"] = provider.id
    session["oauth_state"] = OAUTH_STATE
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    UserModel = data["user_table"].get_model()
    count_before = UserModel.objects.count()

    response = api_client.get(
        reverse(
            "api:user_sources:sso_oauth2_openid_connect:callback",
            kwargs={"user_source_uid": user_source.uid},
        ),
        {"code": "testcode", "state": OAUTH_STATE},
    )

    assert response.status_code == HTTP_302_FOUND
    # Redirected back to the originating page (under the application), not signed in.
    assert response["Location"].startswith(application_url)
    query_params = dict(parse_qsl(urlparse(response["Location"]).query))
    assert (
        query_params[f"oidc_error__{user_source.id}"]
        == "errorApplicationUserLimitReached"
    )
    assert f"user_source_oidc_token__{user_source.id}" not in query_params
    # The view swallows the refusal inside its transaction, so a user row created
    # before the limit check would have been committed. The first time user must not
    # have been auto-provisioned.
    assert UserModel.objects.count() == count_before


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
@pytest.mark.parametrize("email_verified", [False, "false"])
@pytest.mark.parametrize(
    "email_attr_key,expected_email,expected_error",
    [
        # AWS Cognito setup identifying app users by their id signs them in even
        # though their email is unverified.
        ("sub", "cognito-sub", None),
        ("email", None, "errorUnverifiedEmail"),
    ],
)
def test_oauth2_callback_email_verified_only_applies_to_email_identifier(
    email_attr_key,
    expected_email,
    expected_error,
    email_verified,
    api_client,
    data_fixture,
):
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    application_url = user_source.application.get_type().get_application_urls(
        user_source.application.specific
    )[0]
    provider = OpenIdConnectAppAuthProviderModel.objects.create(
        user_source=user_source,
        name="cognito",
        base_url="https://idp.example.com",
        client_id="clientid",
        secret="secret",
        authorization_url="https://idp.example.com/oauth2/authorize",
        access_token_url="https://idp.example.com/oauth2/token",
        user_info_url="https://idp.example.com/oauth2/userInfo",
        email_attr_key=email_attr_key,
    )
    responses.add(
        responses.POST,
        provider.access_token_url,
        json={"access_token": "testtoken", "token_type": "Bearer"},
    )
    responses.add(
        responses.GET,
        provider.user_info_url,
        json={
            "sub": "cognito-sub",
            "email": "unverified@example.com",
            "email_verified": email_verified,
            "name": "App user",
        },
    )

    session = api_client.session
    session["oauth_2_provider_id"] = provider.id
    session["oauth_state"] = OAUTH_STATE
    OpenIdConnectAppAuthProviderType().push_request_data_to_session(
        session, {"original": application_url}
    )
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    response = api_client.get(
        reverse(
            "api:user_sources:sso_oauth2_openid_connect:callback",
            kwargs={"user_source_uid": user_source.uid},
        ),
        {"code": "testcode", "state": OAUTH_STATE},
    )

    assert response.status_code == HTTP_302_FOUND
    assert response["Location"].startswith(application_url)
    query_params = dict(parse_qsl(urlparse(response["Location"]).query))
    user_emails = list(
        data["user_table"]
        .get_model()
        .objects.values_list(f"field_{data['fields'][0].id}", flat=True)
    )
    if expected_error:
        assert query_params[f"oidc_error__{user_source.id}"] == expected_error
        assert f"user_source_oidc_token__{user_source.id}" not in query_params
        assert "unverified@example.com" not in user_emails
    else:
        assert f"oidc_error__{user_source.id}" not in query_params
        assert f"user_source_oidc_token__{user_source.id}" in query_params
        assert expected_email in user_emails


def create_provider_and_session(api_client, data_fixture, with_state=True):
    """
    Returns a provider and its application URL, with the client session as the
    login view leaves it.
    """

    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["user_source"]
    application_url = user_source.application.get_type().get_application_urls(
        user_source.application.specific
    )[0]
    provider = OpenIdConnectAppAuthProviderModel.objects.create(
        user_source=user_source,
        name="oidc",
        base_url="https://idp.example.com",
        client_id="clientid",
        secret="secret",
        authorization_url="https://idp.example.com/authorize",
        access_token_url="https://idp.example.com/token",
        user_info_url="https://idp.example.com/userinfo",
    )

    session = api_client.session
    session["oauth_2_provider_id"] = provider.id
    if with_state:
        session["oauth_state"] = OAUTH_STATE
    OpenIdConnectAppAuthProviderType().push_request_data_to_session(
        session, {"original": application_url}
    )
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    return provider, application_url


def get_callback_url(provider):
    return reverse(
        "api:user_sources:sso_oauth2_openid_connect:callback",
        kwargs={"user_source_uid": provider.user_source.uid},
    )


def assert_auth_flow_error(response, provider, application_url):
    assert response.status_code == HTTP_302_FOUND
    assert response["Location"].startswith(application_url)
    query_params = dict(parse_qsl(urlparse(response["Location"]).query))
    user_source_id = provider.user_source.id
    assert query_params[f"oidc_error__{user_source_id}"] == "errorAuthFlowError"
    assert f"user_source_oidc_token__{user_source_id}" not in query_params


def assert_signed_in(response, provider, application_url):
    assert response.status_code == HTTP_302_FOUND
    assert response["Location"].startswith(application_url)
    query_params = dict(parse_qsl(urlparse(response["Location"]).query))
    user_source_id = provider.user_source.id
    assert f"oidc_error__{user_source_id}" not in query_params
    assert f"user_source_oidc_token__{user_source_id}" in query_params


@pytest.mark.django_db
@patch.object(OpenIdConnectAppAuthProviderType, "get_user_info")
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
    mock_get_user_info, query_params, api_client, data_fixture
):
    provider, application_url = create_provider_and_session(api_client, data_fixture)
    mock_get_user_info.return_value = (
        UserInfo(email="new@baserow.io", name="New user"),
        application_url,
    )

    response = api_client.get(
        get_callback_url(provider), {"code": "testcode", **query_params}
    )

    assert_auth_flow_error(response, provider, application_url)
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@patch.object(OpenIdConnectAppAuthProviderType, "get_user_info")
def test_oauth2_callback_rejects_session_without_state(
    mock_get_user_info, api_client, data_fixture
):
    """
    The login CSRF case: the victim's browser went through the login view for a
    provider, but the callback carries the state of the attacker's own flow.
    """

    provider, application_url = create_provider_and_session(
        api_client, data_fixture, with_state=False
    )
    mock_get_user_info.return_value = (
        UserInfo(email="new@baserow.io", name="New user"),
        application_url,
    )

    response = api_client.get(
        get_callback_url(provider), {"code": "testcode", "state": "attacker_state"}
    )

    assert_auth_flow_error(response, provider, application_url)
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@patch.object(OpenIdConnectAppAuthProviderType, "get_user_info")
def test_oauth2_callback_rejects_fresh_session(
    mock_get_user_info, api_client, data_fixture
):
    data = populate_local_baserow_test_data(data_fixture)
    provider = OpenIdConnectAppAuthProviderModel.objects.create(
        user_source=data["user_source"],
        name="oidc",
        base_url="https://idp.example.com",
        client_id="clientid",
        secret="secret",
    )

    response = api_client.get(
        get_callback_url(provider), {"code": "testcode", "state": OAUTH_STATE}
    )

    # Without the provider id in the session there is no application to redirect to.
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_AUTH_PROVIDER_DOES_NOT_EXIST"
    mock_get_user_info.assert_not_called()


@pytest.mark.django_db
@patch.object(OpenIdConnectAppAuthProviderType, "get_user_info")
def test_oauth2_callback_state_can_only_be_used_once(
    mock_get_user_info, api_client, data_fixture
):
    provider, application_url = create_provider_and_session(api_client, data_fixture)
    mock_get_user_info.return_value = (
        UserInfo(email="new@baserow.io", name="New user"),
        application_url,
    )
    callback_url = get_callback_url(provider)
    params = {"code": "testcode", "state": OAUTH_STATE}

    assert_signed_in(api_client.get(callback_url, params), provider, application_url)

    # The provider id is popped by the first callback too. Put it back so this
    # checks the state itself.
    session = api_client.session
    session["oauth_2_provider_id"] = provider.id
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    assert_auth_flow_error(
        api_client.get(callback_url, params), provider, application_url
    )
    assert mock_get_user_info.call_count == 1


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
def test_oauth2_flow_checks_state_from_the_login_view(api_client, data_fixture):
    """
    Goes through the real login and callback views, with only the provider's HTTP
    endpoints mocked, so the state comes from what the login view stored.
    """

    provider, application_url = create_provider_and_session(
        api_client, data_fixture, with_state=False
    )
    responses.add(
        responses.POST,
        provider.access_token_url,
        json={"access_token": "testtoken", "token_type": "Bearer"},
    )
    responses.add(
        responses.GET,
        provider.user_info_url,
        json={"email": "new@baserow.io", "name": "New user"},
    )

    login_url = reverse(
        "api:user_sources:sso_oauth2_openid_connect:login",
        kwargs={"user_source_uid": provider.user_source.uid},
    )

    def start_login():
        response = api_client.get(
            login_url, {"iss": provider.base_url, "original": application_url}
        )
        assert response.status_code == HTTP_302_FOUND
        return dict(parse_qsl(urlparse(response["Location"]).query))["state"]

    callback_url = get_callback_url(provider)

    start_login()
    response = api_client.get(
        callback_url, {"code": "testcode", "state": "attacker_state"}
    )
    assert_auth_flow_error(response, provider, application_url)
    assert len(responses.calls) == 0

    state = start_login()
    response = api_client.get(callback_url, {"code": "testcode", "state": state})
    assert_signed_in(response, provider, application_url)

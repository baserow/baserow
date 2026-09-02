from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qsl, urlparse

from django.conf import settings
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.timezone import now

import pytest
from rest_framework.status import HTTP_302_FOUND

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
    BASEROW_APPLICATION_USER_LIMIT_ENFORCED=True,
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
    session.save()
    api_client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    response = api_client.get(
        reverse(
            "api:user_sources:sso_oauth2_openid_connect:callback",
            kwargs={"user_source_uid": user_source.uid},
        ),
        {"code": "testcode"},
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

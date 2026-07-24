from django.test.utils import override_settings

import pytest
import requests

import advocate
from baserow_enterprise.api.sso.utils import (
    get_valid_frontend_url,
    redirect_user_on_success,
    urlencode_user_tokens,
)
from baserow_enterprise.sso.utils import (
    enforce_sso_ssrf_protection,
    get_sso_request_function,
)


@override_settings(BASEROW_SSO_ALLOW_PRIVATE_ADDRESS=False)
def test_get_sso_request_function_blocks_private_address_when_not_allowed():
    # When private addresses are not allowed, SSO requests to the OpenID Connect
    # well-known/JWKS endpoints must go through advocate so that an admin/builder
    # configured provider URL can't reach Baserow's internal network.
    assert get_sso_request_function() is advocate.request


@override_settings(BASEROW_SSO_ALLOW_PRIVATE_ADDRESS=True)
def test_get_sso_request_function_allows_private_address_when_enabled():
    assert get_sso_request_function() is requests.request


@override_settings(BASEROW_SSO_ALLOW_PRIVATE_ADDRESS=False)
def test_enforce_sso_ssrf_protection_blocks_private_address_when_not_allowed():
    session = enforce_sso_ssrf_protection(requests.Session())
    with pytest.raises(advocate.UnacceptableAddressException):
        # Port 80 is in advocate's whitelist, so the private IP check itself is hit.
        session.get("http://127.0.0.1:80", timeout=5)


@override_settings(BASEROW_SSO_ALLOW_PRIVATE_ADDRESS=True)
def test_enforce_sso_ssrf_protection_disabled_when_private_addresses_allowed():
    session = requests.Session()
    assert enforce_sso_ssrf_protection(session) is session
    assert not isinstance(
        session.get_adapter("http://example.com"), advocate.ValidatingHTTPAdapter
    )


def test_get_valid_front_url():
    assert get_valid_frontend_url() == "http://localhost:3000/dashboard"
    assert (
        get_valid_frontend_url("http://localhost:3000/dashboard")
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/dashboard/after")
        == "http://localhost:3000/dashboard/after"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/other")
        == "http://localhost:3000/other"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/other", allow_any_path=False)
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/")
        == "http://localhost:3000/dashboard"
    )

    assert (
        get_valid_frontend_url("http://something.com/")
        == "http://localhost:3000/dashboard"
    )
    assert (
        get_valid_frontend_url("http://something.com/dashboard/test")
        == "http://localhost:3000/dashboard"
    )


def test_get_valid_front_url_with_defaults():
    defaults = ["https://test.com/toto", "http://random.net/"]
    assert (
        get_valid_frontend_url(default_frontend_urls=defaults)
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("https://test.com/toto", default_frontend_urls=defaults)
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("http://random.net/", default_frontend_urls=defaults)
        == "http://random.net/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/toto/subpath/", default_frontend_urls=defaults
        )
        == "https://test.com/toto/subpath/"
    )
    assert (
        get_valid_frontend_url("https://test.com/titi/", default_frontend_urls=defaults)
        == "https://test.com/titi/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/titi/",
            default_frontend_urls=defaults,
        )
        == "https://test.com/titi/"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/titi/",
            default_frontend_urls=defaults,
            allow_any_path=False,
        )
        == "https://test.com/toto"
    )
    assert (
        get_valid_frontend_url("http://random.net/", default_frontend_urls=defaults)
        == "http://random.net/"
    )
    assert (
        get_valid_frontend_url("http://random.net/path", default_frontend_urls=defaults)
        == "http://random.net/path"
    )
    assert (
        get_valid_frontend_url("http://other.net/path", default_frontend_urls=defaults)
        == "https://test.com/toto"
    )


def test_get_valid_front_url_w_params():
    assert (
        get_valid_frontend_url(query_params={"test": "value"})
        == "http://localhost:3000/dashboard?test=value"
    )
    assert (
        get_valid_frontend_url(
            "http://localhost:3000/dashboard", query_params={"test": "value"}
        )
        == "http://localhost:3000/dashboard?test=value"
    )


@pytest.mark.django_db()
def test_urlencode_user_tokens(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    url = urlencode_user_tokens("http://localhost:3000/dashboard", user)
    assert "token=" in url
    assert "user_session=" in url


@pytest.mark.django_db()
def test_redirect_user_on_success(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    response = redirect_user_on_success(user)
    assert response.status_code == 302
    assert response.has_header("Location")
    location = response.headers["Location"]
    assert "token=" in location
    assert "user_session=" in location

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.test.utils import override_settings

import pytest
import requests

import advocate
from baserow_enterprise.api.sso.utils import (
    get_valid_frontend_url,
    redirect_user_on_success,
    urlencode_user_tokens,
)
from baserow_enterprise.integrations.common.sso.saml.app_auth_provider_types import (
    SamlAppAuthProviderType,
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
    assert get_valid_frontend_url() == "http://localhost:3000/all-workspaces"
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
        == "http://localhost:3000/all-workspaces"
    )
    assert (
        get_valid_frontend_url("http://localhost:3000/")
        == "http://localhost:3000/all-workspaces"
    )

    assert (
        get_valid_frontend_url("http://something.com/")
        == "http://localhost:3000/all-workspaces"
    )
    assert (
        get_valid_frontend_url("http://something.com/dashboard/test")
        == "http://localhost:3000/all-workspaces"
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
        == "http://localhost:3000/all-workspaces?test=value"
    )
    assert (
        get_valid_frontend_url(
            "http://localhost:3000/dashboard", query_params={"test": "value"}
        )
        == "http://localhost:3000/dashboard?test=value"
    )


@pytest.mark.parametrize(
    "requested_url",
    [
        # A browser reads the backslash as the end of the host, urlparse doesn't.
        "https://attacker.example\\@localhost:3000/all-workspaces",
        "http://attacker.example\\@localhost:3000/all-workspaces",
        "http://localhost:3000\\.attacker.example/",
        # Userinfo.
        "https://attacker.example@localhost:3000/",
        "http://attacker.example@localhost:3000/",
        "http://user:password@localhost:3000/",
        # Control characters.
        "http://attacker.example\t@localhost:3000/",
        "http://local\thost:3000/",
        "http://localhost:3000/\ndashboard",
        "http://localhost:3000/dash\r\nboard",
        "http://localhost:3000/dash\x01board",
        "http://localhost:3000/dash\x7fboard",
        "\x01http://localhost:3000/dashboard",
        "/\tdashboard",
        "/\t/attacker.example",
        # Relative urls a browser resolves to another host.
        "/\\attacker.example",
        "\\\\attacker.example",
        "//attacker.example",
        # Allowed host with a scheme that can't be redirected to.
        "ftp://localhost:3000/dashboard",
        "javascript://localhost:3000/%0aalert(1)//",
        # Urls urlparse can't fully parse.
        "http://[attacker.example/",
        "http://localhost:99999/",
    ],
)
@pytest.mark.parametrize("allow_any_path", [True, False])
def test_get_valid_front_url_falls_back_to_default_on_unsafe_url(
    requested_url, allow_any_path
):
    assert (
        get_valid_frontend_url(
            requested_url,
            query_params={"token": "secret"},
            allow_any_path=allow_any_path,
        )
        == "http://localhost:3000/all-workspaces?token=secret"
    )


def test_get_valid_front_url_with_defaults_falls_back_on_unsafe_url():
    defaults = ["https://app.com:3000/", "https://other.net/preview/"]
    for requested_url in [
        "https://attacker.example\\@other.net/preview/",
        "https://attacker.example@other.net/preview/",
        "https://attacker.example/preview/",
    ]:
        assert (
            get_valid_frontend_url(
                requested_url,
                default_frontend_urls=defaults,
                allow_any_path=False,
            )
            == "https://app.com:3000/"
        )


def test_get_valid_front_url_keeps_legitimate_urls():
    assert get_valid_frontend_url("/dashboard") == "http://localhost:3000/dashboard"
    assert get_valid_frontend_url("/a%5Cb%20c") == "http://localhost:3000/a%5Cb%20c"
    assert get_valid_frontend_url("http://localhost:3000/dashboard?a=1#b") == (
        "http://localhost:3000/dashboard?a=1#b"
    )
    # A case or default port difference is the same origin.
    assert get_valid_frontend_url("HTTP://LOCALHOST:3000/dashboard") == (
        "http://localhost:3000/dashboard"
    )

    defaults = ["https://test.com/toto", "http://random.net/"]
    for requested_url, expected_url in [
        ("https://test.com:443/toto/sub", "https://test.com:443/toto/sub"),
        ("HTTPS://TEST.com/toto/sub", "https://test.com/toto/sub"),
    ]:
        assert (
            get_valid_frontend_url(
                requested_url, default_frontend_urls=defaults, allow_any_path=False
            )
            == expected_url
        )
    assert (
        get_valid_frontend_url(
            "http://random.net:80/sub", default_frontend_urls=defaults
        )
        == "http://random.net:80/sub"
    )
    assert (
        get_valid_frontend_url(
            "https://test.com/sub", default_frontend_urls=["https://test.com:443/"]
        )
        == "https://test.com/sub"
    )
    assert (
        get_valid_frontend_url(
            "http://[::1]:3000/sub", default_frontend_urls=["http://[::1]:3000/"]
        )
        == "http://[::1]:3000/sub"
    )


@pytest.mark.parametrize("allow_any_path", [True, False])
@pytest.mark.parametrize(
    "requested_url,allowed_url,expected_url",
    [
        # A domain stores neither scheme nor port, so the allowed url gets them from
        # PUBLIC_WEB_FRONTEND_URL. The site can really be served on another origin.
        (
            "https://shop.example.com/login?next=x",
            "http://shop.example.com:3000",
            "https://shop.example.com/login?next=x&t=1",
        ),
        (
            "https://shop.example.com:8443/login",
            "http://shop.example.com:3000",
            "https://shop.example.com:8443/login?t=1",
        ),
        (
            "http://shop.example.com:4000/login",
            "http://shop.example.com:3000",
            "http://shop.example.com:4000/login?t=1",
        ),
        # A crafted http link can't move the token to plain HTTP.
        (
            "http://shop.example.com/login",
            "https://shop.example.com",
            "https://shop.example.com/login?t=1",
        ),
        (
            "http://shop.example.com:8443/login",
            "https://shop.example.com:8443",
            "https://shop.example.com:8443/login?t=1",
        ),
    ],
)
def test_get_valid_front_url_keeps_the_requested_origin_without_downgrading(
    requested_url, allowed_url, expected_url, allow_any_path
):
    assert (
        get_valid_frontend_url(
            requested_url,
            query_params={"t": "1"},
            default_frontend_urls=[allowed_url],
            allow_any_path=allow_any_path,
        )
        == expected_url
    )


def test_get_valid_front_url_path_outside_allowed_url_keeps_the_requested_origin():
    assert (
        get_valid_frontend_url(
            "https://test.com/other?a=1",
            default_frontend_urls=["http://test.com:3000/toto"],
            allow_any_path=False,
        )
        == "https://test.com/toto"
    )


@pytest.mark.parametrize("allow_any_path", [True, False])
def test_get_valid_front_url_with_an_invalid_port_in_the_allowed_url(allow_any_path):
    # A domain's name is stored free form, so the allowed url can have a bad port.
    assert (
        get_valid_frontend_url(
            "https://shop.example.com/login",
            query_params={"t": "1"},
            default_frontend_urls=["http://shop.example.com:abc"],
            allow_any_path=allow_any_path,
        )
        == "https://shop.example.com/login?t=1"
    )


def test_get_valid_front_url_asks_the_auth_provider_types_for_callback_params():
    with patch.object(
        SamlAppAuthProviderType, "callback_token_query_param_prefix", "custom_token__"
    ):
        assert (
            get_valid_frontend_url(
                "http://test.com/p?custom_token__1=ATTACKER&user_source_saml_token__1=a",
                default_frontend_urls=["http://test.com"],
                allow_any_path=False,
            )
            == "http://test.com/p?user_source_saml_token__1=a"
        )


def test_get_valid_front_url_removes_requested_callback_params():
    defaults = ["http://test.com/"]
    assert (
        get_valid_frontend_url(
            "http://test.com/p?a=1&user_source_oidc_token__1=ATTACKER"
            "&user_source_saml_token__999=x&saml_error__1=e&oidc_error__2=e"
            "&%75ser_source_saml_token__3=encoded",
            query_params={"user_source_oidc_token__1": "real"},
            default_frontend_urls=defaults,
        )
        == "http://test.com/p?a=1&user_source_oidc_token__1=real"
    )


def test_get_valid_front_url_keeps_other_requested_params_untouched():
    assert (
        get_valid_frontend_url(
            "http://test.com/p?next=%2Ftoto&token=mine&empty=#frag",
            default_frontend_urls=["http://test.com/"],
        )
        == "http://test.com/p?next=%2Ftoto&token=mine&empty=#frag"
    )


@pytest.mark.django_db()
def test_urlencode_user_tokens_replaces_requested_tokens(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    url = urlencode_user_tokens(
        "http://localhost:3000/dashboard?a=1&token=ATTACKER&user_session=ATTACKER", user
    )
    params = parse_qs(urlparse(url).query)
    assert params["a"] == ["1"]
    assert len(params["token"]) == 1
    assert len(params["user_session"]) == 1
    assert "ATTACKER" not in url


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

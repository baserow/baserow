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
        # Another origin on an allowed host.
        "https://localhost:3000/dashboard",
        "http://localhost:4000/dashboard",
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
        "https://other.net:8443/preview/",
        "http://other.net/preview/",
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
        ("https://test.com:443/toto/sub", "https://test.com/toto/sub"),
        ("HTTPS://TEST.com/toto/sub", "https://test.com/toto/sub"),
    ]:
        assert (
            get_valid_frontend_url(
                requested_url, default_frontend_urls=defaults, allow_any_path=False
            )
            == expected_url
        )
    assert get_valid_frontend_url(
        "http://random.net:80/sub", default_frontend_urls=defaults
    ) == ("http://random.net/sub")

    assert (
        get_valid_frontend_url(
            "https://test.com/sub", default_frontend_urls=["https://test.com:443/"]
        )
        == "https://test.com:443/sub"
    )


def test_get_valid_front_url_matches_the_allowed_url_with_the_same_port():
    defaults = ["http://test.com:3000", "http://test.com:4000/builder/preview/1/"]
    assert (
        get_valid_frontend_url(
            "http://test.com:3000/login",
            default_frontend_urls=defaults,
            allow_any_path=False,
        )
        == "http://test.com:3000/login"
    )
    assert (
        get_valid_frontend_url(
            "http://test.com:4000/builder/preview/1/login",
            default_frontend_urls=defaults,
            allow_any_path=False,
        )
        == "http://test.com:4000/builder/preview/1/login"
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

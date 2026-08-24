import base64
import json
from urllib.parse import parse_qsl, urlparse

from django.conf import settings
from django.contrib.sessions.backends.base import SessionBase
from django.test.utils import override_settings

import jwt
import pytest
import responses
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import advocate
from advocate.exceptions import UnacceptableAddressException
from baserow.core.registries import auth_provider_type_registry
from baserow_enterprise.sso.exceptions import AuthFlowError, InvalidProviderUrl
from baserow_enterprise.sso.oauth2.auth_provider_types import (
    OAuth2AuthProviderMixin,
    OpenIdConnectAuthProviderType,
    WellKnownUrls,
)

PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDhNhtzJF26phym
WbFsU9zve8pk7ndz2Hc7hts8zcrwZph2Y1gLwZQDdbh6M7TW5ms1hF0Ngxyso8UR
WOFkzAsOmmv0UkIY7LMsdPxnyXUNpTiiaEklCRpv0FQGpON41VnYC7GK0+K4FYxW
+V+XFUY4nlINwokUrZKeG1WHJHgkI086QX3AMn2kGUbPFDrg0/IurMCJ1vSj9n+3
UKZ0+Y1PW85TNiXMpMyN1jBP+PvXJ+u/67Ys0I1gIM3ov6OpsXZxw3sAlXMNsVoc
YzcjJCzGP4ZAdiBdxnIvOzcOQjwyh4AoCkfizu+bfAf1lnrqOFLlnzNxCC2FP6hJ
C6v+J2AbAgMBAAECggEAG4uHnfSeYNF9AueeKLa1I2Fg/ClNLju/5uWenk2OpbVB
WTGGDPdh3W53ir1qP+KHeFCLz7bv5I7/RRjkMHTjC/0yePvanmZ3n6y19me7IQPK
l9U+JQEmXPNTuPWlO3E01OomjpP4ezVqKHUbDkU0L9aas0N44AY+vtxvAIwjBErx
MKiU+YN9TS8WNjv0WzIqipqbM1bXz5Y/MG6e7v6CJJQpLfQgmpgUL6/lwxoA7Dca
OpEQ7wGtjWhE4xef3muJj2Iq/7VCmFFMaKqGOfx5gVBiNWCw1NE9dA2JJfU6FEAz
7TbA0z02gILzom1LGnH2nbtzQdCUHSVQAiaiadv3IQKBgQD36LMAoK5rV7hTa+WM
13cSlFD13z2Rbpcc4oer1Je2mL3aSoTOWbEjFXQqD93QJVcZx0nxyLI81y6+tfpc
+z9a8Y4nCcUh/7a+t/R+NHCxFJCgNscFiWhfdu6EfLFVQhv83eJZL7IJ5ja4muDE
69l3ojZVSEXI+oDEAl9/2qnOawKBgQDoj8R0F6e1fOaNw0mYSwJvWaNOTb60/JCO
O9pyoLgpSkk91ndz/9aKw7h/J650bjQL3PQ5bcwW+GRE2jPNXvN53i1PY++Na1Mq
652A6JFpWPF1+hdSGNmI4RAS5cMxF+K6zhFiIeyKpw4CzH6fh1Zm2bHNeroMd59w
ZGV8yUbBEQKBgQCf/Z5gPlKyVedQdyaq8XcYF330X8FFNUDy1ENIoqfSoNqNoV/6
KCpIgRT5/EljhmWi7lmLX8GfwCOb0qekEEW/9HqQOR7vJS+T//Ya6M79iU8ZBqEE
srwYOBIQkMSFSGf1lmD4u+5Dsz4Hf3SlwawUKCy2dzEKVph5Zyqowb6qxwKBgQDb
F14fdI2Vx+Y4FYuGwtu3ZT4ZLdsFDI9uv+prZQg6NfbMH/kHOjW3Iu30NMEAhTXZ
Gz6lv8+usDFeQCbfSp2b6PjMuzxaAYsnezM112PuWFGaMJK50BlX/5eyBe0emf8K
t8neplD+yqTDdD2yMsDuQhZkm0MdLbDyJFML/V7/0QKBgQDckWlmPHtyo+b6LitA
GGjEduAXfTqx5a58uV+0jidIpnucMylFImw+btL3pPxXzAR4wZd2KR5hm0N/s46e
9AqNwnoELHNkv6gcxL8oSQpeDFFKsq229F7j6yzw4TgmB7wNM/OQ77swQ42R4zDd
cz37dVkQhAQeNqNzFFSZve8LsQ==
-----END PRIVATE KEY-----
"""

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4TYbcyRduqYcplmxbFPc
73vKZO53c9h3O4bbPM3K8GaYdmNYC8GUA3W4ejO01uZrNYRdDYMcrKPFEVjhZMwL
Dppr9FJCGOyzLHT8Z8l1DaU4omhJJQkab9BUBqTjeNVZ2AuxitPiuBWMVvlflxVG
OJ5SDcKJFK2SnhtVhyR4JCNPOkF9wDJ9pBlGzxQ64NPyLqzAidb0o/Z/t1CmdPmN
T1vOUzYlzKTMjdYwT/j71yfrv+u2LNCNYCDN6L+jqbF2ccN7AJVzDbFaHGM3IyQs
xj+GQHYgXcZyLzs3DkI8MoeAKApH4s7vm3wH9ZZ66jhS5Z8zcQgthT+oSQur/idg
GwIDAQAB
-----END PUBLIC KEY-----
"""


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def pem_to_jwk(public_pem: str, kid: str = "my-key-id") -> dict:
    public_key = serialization.load_pem_public_key(
        public_pem.encode("utf-8"), backend=default_backend()
    )
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Key is not an RSA public key")

    numbers = public_key.public_numbers()
    e = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, byteorder="big")
    n = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, byteorder="big")

    return {
        "kty": "RSA",
        "alg": "RS256",
        "use": "sig",
        "kid": kid,
        "n": b64url_encode(n),
        "e": b64url_encode(e),
    }


@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.com"}),
        ("openid_connect", {"base_url": "https://gitlab.com"}),
    ],
)
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_login_options(
    provider_type, extra_params, data_fixture, enterprise_data_fixture
):
    data_fixture.create_password_provider()
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider2 = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="g_client_id",
        secret="g_secret",
        name="provider2",
        enabled=False,
        **extra_params,
    )
    enterprise_data_fixture.enable_enterprise()
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)

    assert provider_type_instance.get_login_options() == {
        "type": provider_type,
        "items": [
            {
                "redirect_url": (
                    f"{settings.PUBLIC_BACKEND_URL}/api/sso/oauth2/login/{provider.id}/"
                ),
                "name": provider.name,
                "type": provider_type,
            }
        ],
        "default_redirect_url": (
            f"{settings.PUBLIC_BACKEND_URL}/api/sso/oauth2/login/{provider.id}/"
        ),
    }


@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.com"}),
        (
            "openid_connect",
            {
                "base_url": "https://gitlab.com",
                "authorization_url": "https://gitlab.com/oauth/authorize",
            },
        ),
    ],
)
@pytest.mark.django_db
def test_get_authorization_url(provider_type, extra_params, enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    query_params = {"query_param": "param_value"}

    auth_url = provider_type_instance.get_authorization_url(
        provider, session, query_params
    )

    parsed_url = urlparse(auth_url)
    params = dict(parse_qsl(parsed_url.query))
    assert params["response_type"] == "code"
    assert params["client_id"] == "test_client_id"
    assert f"/api/sso/oauth2/callback/{provider.id}/" in params["redirect_uri"]
    assert params["state"] == session["oauth_state"]
    stored_query_params = json.loads(session["oauth_request_data"])
    assert stored_query_params["query_param"] == "param_value"


@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.com"}),
        (
            "openid_connect",
            {
                "base_url": "https://gitlab.com",
                "authorization_url": "https://gitlab.com/oauth/authorize",
                "access_token_url": "https://gitlab.com/oauth/token",
                "user_info_url": "https://gitlab.com/api/v4/user",
            },
        ),
    ],
)
@pytest.mark.django_db
@responses.activate
def test_get_oauth_token_and_response(
    provider_type, extra_params, enterprise_data_fixture
):
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    code = "testcode"

    # mock access token response
    access_token_response = {
        "access_token": "MTQ0NjJkZmQ5OTM2NDE1ZTZjNGZmZjI3",
        "token_type": "Bearer",
    }
    responses.add(
        responses.POST,
        provider_type_instance.get_access_token_url(provider),
        json=access_token_response,
        status=200,
    )

    # mock get user info response
    oauth_response_data = {
        "email": "testuser@example.com",
        "name": "Test User",
    }
    responses.add(
        responses.GET,
        provider_type_instance.get_user_info_url(provider),
        json=oauth_response_data,
        status=200,
    )

    token, json_response = provider_type_instance.get_oauth_token_and_response(
        provider, code, session
    )
    assert token == access_token_response
    assert json_response["email"] == oauth_response_data["email"]
    assert json_response["name"] == oauth_response_data["name"]


@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.com"}),
        (
            "openid_connect",
            {
                "base_url": "https://gitlab.com",
                "authorization_url": "https://gitlab.com/oauth/authorize",
                "access_token_url": "https://gitlab.com/oauth/token",
                "user_info_url": "https://gitlab.com/api/v4/user",
            },
        ),
        (
            "openid_connect",
            {
                "base_url": "https://gitlab.com",
                "authorization_url": "https://gitlab.com/oauth/authorize",
                "access_token_url": "https://gitlab.com/oauth/token",
                "user_info_url": "https://gitlab.com/api/v4/user",
                "jwks_url": "https://gitlab.com/oauth/discovery/keys",
                "issuer": "https://example.com",
                "use_id_token": True,
            },
        ),
    ],
)
@pytest.mark.django_db
@responses.activate
def test_get_user_info(provider_type, extra_params, enterprise_data_fixture):
    client_id = "test_client_id"
    kid = "testkey123"

    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id=client_id,
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    code = "testcode"
    query_params = {
        "workspace_invitation_token": "testgrouptoken",
        "language": "es",
        "original": "templates",
    }
    provider_type_instance.push_request_data_to_session(session, query_params)

    # mock get user info response
    oauth_response_data = {
        "email": "testuser@example.com",
        "name": "Test User",
    }
    responses.add(
        responses.GET,
        provider_type_instance.get_user_info_url(provider),
        json=oauth_response_data,
        status=200,
    )

    payload = {
        "iss": "https://example.com",
        "aud": client_id,
        "sub": "user123",
        "email": oauth_response_data["email"],
        "name": oauth_response_data["name"],
    }

    # mock access token response
    access_token_response = {
        "id_token": jwt.encode(
            payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": kid}
        ),
        "access_token": "MTQ0NjJkZmQ5OTM2NDE1ZTZjNGZmZjI3",
        "token_type": "Bearer",
    }
    responses.add(
        responses.POST,
        provider_type_instance.get_access_token_url(provider),
        json=access_token_response,
        status=200,
    )

    if provider_type == "openid_connect":
        jwk = pem_to_jwk(PUBLIC_KEY, kid)

        responses.add(
            responses.GET,
            provider.jwks_url,
            json={"keys": [jwk]},
            status=200,
        )

    # mock emails endpoint for github
    if provider_type == "github":
        responses.add(
            responses.GET,
            provider_type_instance.EMAILS_URL,
            json=[{"email": "testuser@example.com"}],
            status=200,
        )

    user_info, original = provider_type_instance.get_user_info(provider, code, session)
    assert user_info.email == oauth_response_data["email"]
    assert user_info.name == oauth_response_data["name"]
    assert (
        user_info.workspace_invitation_token
        == query_params["workspace_invitation_token"]
    )
    assert user_info.language == query_params["language"]
    assert original == query_params["original"]
    assert user_info.email_verified is True


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
def test_oidc_id_token_propagates_email_verified_false(enterprise_data_fixture):
    client_id = "test_client_id"
    kid = "testkey123"
    provider = enterprise_data_fixture.create_oauth_provider(
        type="openid_connect",
        client_id=client_id,
        secret="test_secret",
        name="oidc1",
        base_url="https://example.com",
        authorization_url="https://example.com/oauth/authorize",
        access_token_url="https://example.com/oauth/token",
        user_info_url="https://example.com/userinfo",
        jwks_url="https://example.com/jwks",
        issuer="https://example.com",
        use_id_token=True,
    )
    pt = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    pt.push_request_data_to_session(session, {"original": "/"})

    responses.add(
        responses.GET,
        pt.get_user_info_url(provider),
        json={"email": "test@example.com", "name": "Test User"},
        status=200,
    )

    payload = {
        "iss": "https://example.com",
        "aud": client_id,
        "sub": "user123",
        "email": "test@example.com",
        "name": "Test User",
        "email_verified": False,
    }

    access_token_response = {
        "id_token": jwt.encode(
            payload, PRIVATE_KEY, algorithm="RS256", headers={"kid": kid}
        ),
        "access_token": "testtoken",
        "token_type": "Bearer",
    }
    responses.add(
        responses.POST,
        pt.get_access_token_url(provider),
        json=access_token_response,
        status=200,
    )

    jwk = pem_to_jwk(PUBLIC_KEY, kid)
    responses.add(
        responses.GET,
        provider.jwks_url,
        json={"keys": [jwk]},
        status=200,
    )

    user_info, _ = pt.get_user_info(provider, "testcode", session)
    assert user_info.email == "test@example.com"
    assert user_info.email_verified is False


@pytest.mark.django_db
@responses.activate
@override_settings(DEBUG=True)
def test_oidc_user_info_endpoint_propagates_email_verified_false(
    enterprise_data_fixture,
):
    client_id = "test_client_id"
    provider = enterprise_data_fixture.create_oauth_provider(
        type="openid_connect",
        client_id=client_id,
        secret="test_secret",
        name="oidc2",
        base_url="https://example.com",
        authorization_url="https://example.com/oauth/authorize",
        access_token_url="https://example.com/oauth/token",
        user_info_url="https://example.com/userinfo",
        issuer="https://example.com",
    )
    pt = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    pt.push_request_data_to_session(session, {"original": "/"})

    access_token_response = {
        "access_token": "testtoken",
        "token_type": "Bearer",
    }
    responses.add(
        responses.POST,
        pt.get_access_token_url(provider),
        json=access_token_response,
        status=200,
    )

    responses.add(
        responses.GET,
        pt.get_user_info_url(provider),
        json={
            "email": "test@example.com",
            "name": "Test User",
            "email_verified": False,
        },
        status=200,
    )

    user_info, _ = pt.get_user_info(provider, "testcode", session)
    assert user_info.email == "test@example.com"
    assert user_info.email_verified is False


@pytest.mark.parametrize(
    "provider_type,extra_params",
    [
        ("google", {}),
        ("facebook", {}),
        ("github", {}),
        ("gitlab", {"base_url": "https://gitlab.com"}),
    ],
)
@pytest.mark.django_db
def test_get_user_info_from_oauth_json_response(
    provider_type, extra_params, enterprise_data_fixture
):
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    query_params = {
        "workspace_invitation_token": "testgrouptoken",
        "language": "es",
        "original": "templates",
    }
    provider_type_instance.push_request_data_to_session(session, query_params)
    oauth_response_data = {
        "email": "testuser@example.com",
        "name": "Test User",
    }

    user_info, original = provider_type_instance.get_user_info_from_oauth_json_response(
        oauth_response_data, session
    )
    assert user_info.email == oauth_response_data["email"]
    assert user_info.name == oauth_response_data["name"]
    assert (
        user_info.workspace_invitation_token
        == query_params["workspace_invitation_token"]
    )
    assert user_info.language == query_params["language"]
    assert original == query_params["original"]

    # missing name
    oauth_response_data = {
        "email": "testuser@example.com",
    }

    user_info, original = provider_type_instance.get_user_info_from_oauth_json_response(
        oauth_response_data, session
    )
    assert user_info.name == oauth_response_data["email"]

    # empty name
    oauth_response_data = {
        "email": "testuser@example.com",
        "name": "   ",
    }

    user_info, original = provider_type_instance.get_user_info_from_oauth_json_response(
        oauth_response_data, session
    )
    assert user_info.name == oauth_response_data["email"]


def test_push_pop_request_data_to_session():
    session = SessionBase()
    query_params = {
        "original": "templates",
        "oauth_state": "state",
        "workspace_invitation_token": "fjkldsfj",
        "language": "es",
    }
    mixin = OAuth2AuthProviderMixin()

    mixin.push_request_data_to_session(session, query_params)
    retrieved_params = mixin.pop_request_data_from_session(session)

    assert query_params == retrieved_params


@responses.activate
def test_openid_get_wellknown_urls():
    base_url = "http://example.com"
    endpoint_response = {
        "authorization_endpoint": "http://example.com/authorization",
        "token_endpoint": "http://example.com/accesstoken",
        "userinfo_endpoint": "http://example.com/userinfo",
        "jwks_uri": "http://example.com/jwks",
        "issuer": "http://example.com/issuer",
    }
    responses.add(
        responses.GET,
        f"{base_url}/.well-known/openid-configuration",
        json=endpoint_response,
        status=200,
    )

    wellknown_urls = OpenIdConnectAuthProviderType().get_wellknown_urls(base_url)

    assert wellknown_urls == WellKnownUrls(
        authorization_url="http://example.com/authorization",
        access_token_url="http://example.com/accesstoken",
        user_info_url="http://example.com/userinfo",
        jwks_url="http://example.com/jwks",
        issuer="http://example.com/issuer",
    )


def test_openid_get_wellknown_urls_private_address_blocked():
    # When private addresses are not allowed the well-known fetch goes through
    # advocate, so a provider URL pointing to a private address must be rejected.
    # Port 80 is in advocate's whitelist, so the private IP check itself is hit.
    with pytest.raises(InvalidProviderUrl) as err:
        OpenIdConnectAuthProviderType().get_wellknown_urls("http://127.0.0.1")
    assert isinstance(err.value.__cause__, UnacceptableAddressException)


@pytest.mark.django_db
def test_get_oauth_token_private_address_blocked(enterprise_data_fixture):
    # The token endpoint URL comes from the provider's well-known document, which
    # the guard on the base URL doesn't constrain, so the OAuth2 session itself
    # must refuse to fetch private addresses.
    provider = enterprise_data_fixture.create_oauth_provider(
        type="openid_connect",
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        base_url="https://gitlab.com",
        authorization_url="https://gitlab.com/oauth/authorize",
        access_token_url="https://127.0.0.1/oauth/token",
        user_info_url="https://127.0.0.1/api/v4/user",
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)

    with pytest.raises(AuthFlowError) as err:
        provider_type_instance.get_oauth_token_and_response(
            provider, "code", SessionBase()
        )
    assert isinstance(err.value.__cause__, UnacceptableAddressException)


@pytest.mark.parametrize(
    "provider_type,extra_params,guarded",
    [
        ("google", {}, False),
        ("facebook", {}, False),
        ("github", {}, False),
        ("gitlab", {"base_url": "https://gitlab.com"}, True),
        (
            "openid_connect",
            {
                "base_url": "https://gitlab.com",
                "authorization_url": "https://gitlab.com/oauth/authorize",
            },
            True,
        ),
    ],
)
@pytest.mark.django_db
def test_get_oauth_session_only_guarded_for_admin_configurable_urls(
    provider_type, extra_params, guarded, enterprise_data_fixture
):
    # Providers with hardcoded URLs (Google, Facebook, GitHub) have no SSRF surface
    # and must keep a plain session so proxied deployments keep working. Providers
    # whose URLs an admin can configure must mount advocate's validating adapter.
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type,
        client_id="test_client_id",
        secret="test_secret",
        name="provider1",
        **extra_params,
    )
    provider_type_instance = auth_provider_type_registry.get_by_model(provider)
    oauth = provider_type_instance.get_oauth_session(provider, SessionBase())
    assert (
        isinstance(
            oauth.get_adapter("https://example.com"), advocate.ValidatingHTTPAdapter
        )
        is guarded
    )


@pytest.mark.django_db
def test_google_email_verified_extraction(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google",
        client_id="cid",
        secret="secret",
        name="google1",
    )
    pt = auth_provider_type_registry.get_by_model(provider)

    assert pt._extract_email_verified({"verified_email": True}) is True
    assert pt._extract_email_verified({"verified_email": False}) is False
    # Missing field → trusted
    assert pt._extract_email_verified({}) is True


@pytest.mark.django_db
def test_github_email_verified_extraction(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="github",
        client_id="cid",
        secret="secret",
        name="github1",
    )
    pt = auth_provider_type_registry.get_by_model(provider)

    assert pt._extract_email_verified({"email_verified": True}) is True
    assert pt._extract_email_verified({"email_verified": False}) is False
    # Missing field → trusted
    assert pt._extract_email_verified({}) is True


@pytest.mark.django_db
@responses.activate
def test_github_get_email_returns_verified_status(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="github",
        client_id="cid",
        secret="secret",
        name="github1",
    )
    pt = auth_provider_type_registry.get_by_model(provider)

    responses.add(
        responses.GET,
        pt.EMAILS_URL,
        json=[
            {"email": "user@example.com", "primary": True, "verified": True},
            {"email": "alt@example.com", "primary": False, "verified": False},
        ],
        status=200,
    )

    email, verified = pt.get_email({"Authorization": "token abc"})
    assert email == "user@example.com"
    assert verified is True

    responses.replace(
        responses.GET,
        pt.EMAILS_URL,
        json=[
            {"email": "unverified@example.com", "primary": True, "verified": False},
        ],
        status=200,
    )

    email, verified = pt.get_email({"Authorization": "token abc"})
    assert email == "unverified@example.com"
    assert verified is False


@pytest.mark.django_db
def test_gitlab_email_verified_extraction(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="gitlab",
        client_id="cid",
        secret="secret",
        name="gitlab1",
        base_url="https://gitlab.com",
    )
    pt = auth_provider_type_registry.get_by_model(provider)

    assert pt._extract_email_verified({"confirmed_at": "2024-01-01T00:00:00Z"}) is True
    assert pt._extract_email_verified({"confirmed_at": None}) is False
    # Missing field → trusted
    assert pt._extract_email_verified({}) is True


@pytest.mark.django_db
def test_facebook_email_verified_defaults_true(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="facebook",
        client_id="cid",
        secret="secret",
        name="facebook1",
    )
    pt = auth_provider_type_registry.get_by_model(provider)

    # Facebook never sends email_verified, base implementation returns True
    assert pt._extract_email_verified({}) is True
    assert pt._extract_email_verified({"some_field": "value"}) is True


@pytest.mark.django_db
def test_google_email_verified_in_user_info_response(enterprise_data_fixture):
    provider = enterprise_data_fixture.create_oauth_provider(
        type="google",
        client_id="cid",
        secret="secret",
        name="google1",
    )
    pt = auth_provider_type_registry.get_by_model(provider)
    session = SessionBase()
    pt.push_request_data_to_session(session, {"original": "/"})

    user_info, _ = pt.get_user_info_from_oauth_json_response(
        {"email": "test@example.com", "name": "Test", "verified_email": False},
        session,
    )
    assert user_info.email_verified is False

    pt.push_request_data_to_session(session, {"original": "/"})
    user_info, _ = pt.get_user_info_from_oauth_json_response(
        {"email": "test@example.com", "name": "Test", "verified_email": True},
        session,
    )
    assert user_info.email_verified is True

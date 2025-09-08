import json

from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow_enterprise.sso.saml.auth_provider_types import SamlAuthProviderType
from baserow_enterprise.sso.saml.models import SamlAuthProviderModel


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_list_saml_provider_without_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    enterprise_data_fixture.create_saml_auth_provider(domain="test1.com")
    enterprise_data_fixture.create_saml_auth_provider(domain="acme.com")

    _, unauthorized_token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.get(
        reverse("api:enterprise:admin:auth_provider:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_list_saml_provider_with_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    data_fixture.create_password_provider()
    auth_prov_1 = enterprise_data_fixture.create_saml_auth_provider(domain="test.com")
    auth_prov_2 = enterprise_data_fixture.create_saml_auth_provider(domain="acme.com")

    _, admin_token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    _, unauthorized_token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse("api:enterprise:admin:auth_provider:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.get(
        reverse("api:enterprise:admin:auth_provider:list"),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "auth_provider_types" in response_json
    response_providers_types = response_json["auth_provider_types"]
    assert len(response_providers_types) >= 1, "At least SAML type should be available"
    response_saml = next(
        provider_type
        for provider_type in response_providers_types
        if provider_type["type"] == SamlAuthProviderType.type
    )
    assert response_saml is not None
    assert response_saml["can_create_new"] is True, response_saml
    assert "auth_providers" in response_saml
    response_providers = response_saml["auth_providers"]
    assert len(response_providers) == 2
    # SAML providers are returned order alphabetically by domain
    assert response_providers[0]["id"] == auth_prov_2.id
    assert response_providers[0]["domain"] == "acme.com"
    assert response_providers[0]["type"] == SamlAuthProviderType.type
    assert response_providers[0]["metadata"] == auth_prov_2.metadata
    assert response_providers[0]["enabled"] is True
    assert response_providers[0]["is_verified"] is False
    assert response_providers[1]["id"] == auth_prov_1.id
    assert response_providers[1]["domain"] == "test.com"
    assert response_providers[1]["type"] == SamlAuthProviderType.type
    assert response_providers[1]["metadata"] == auth_prov_1.metadata
    assert response_providers[1]["enabled"] is True
    assert response_providers[1]["is_verified"] is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_create_saml_provider_without_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    # create a valid SAML provider
    domain = "test.it"
    metadata = enterprise_data_fixture.get_test_saml_idp_metadata()

    _, unauthorized_token = data_fixture.create_user_and_token(is_staff=True)

    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {"type": SamlAuthProviderType.type, "domain": domain, "metadata": metadata},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_create_saml_provider_with_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    data_fixture.create_password_provider()

    # create a valid SAML provider
    domain = "test.it"
    metadata = enterprise_data_fixture.get_test_saml_idp_metadata()

    _, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    _, unauthorized_token = data_fixture.create_user_and_token()

    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {"type": SamlAuthProviderType.type, "domain": domain, "metadata": metadata},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    # cannot create a SAML provider with an invalid domain or metadata
    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {
            "type": SamlAuthProviderType.type,
            "domain": "invalid_domain_name",
            "metadata": metadata,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert json.dumps(response_json["detail"]) == json.dumps(
        {
            "domain": [
                {
                    "error": "The domain value is not a valid domain name.",
                    "code": "invalid",
                }
            ]
        }
    )
    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {
            "type": SamlAuthProviderType.type,
            "domain": "domain2.it",
            "metadata": "invalid_metadata",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert json.dumps(response_json["detail"]) == json.dumps(
        {
            "metadata": [
                {
                    "error": "The metadata is not valid according to the XML schema.",
                    "code": "invalid",
                }
            ]
        }
    )

    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {"type": SamlAuthProviderType.type, "domain": domain, "metadata": metadata},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] is not None
    assert response_json["type"] == SamlAuthProviderType.type
    assert response_json["domain"] == domain
    assert response_json["metadata"] == metadata
    assert response_json["is_verified"] is False
    assert response_json["enabled"] is True

    # cannot create another SAML provider for the same domain
    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {"type": SamlAuthProviderType.type, "domain": domain, "metadata": metadata},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_SAML_PROVIDER_FOR_DOMAIN_ALREADY_EXISTS"

    assert SamlAuthProviderModel.objects.count() == 1

    # ensure the login option is now listed in the login options
    response = api_client.get(
        reverse("api:auth_provider:login_options"),
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "saml" in response_json
    assert response_json["saml"]["domain_required"] is False

    # with multiple SAML domain the domain is required to understand
    # to which IdP the user wants to login
    enterprise_data_fixture.create_saml_auth_provider()
    assert SamlAuthProviderModel.objects.count() == 2

    response = api_client.get(
        reverse("api:auth_provider:login_options"),
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert "saml" in response_json
    assert response_json["saml"]["domain_required"] is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_update_saml_provider_without_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()
    _, unauthorized_token = data_fixture.create_user_and_token(is_staff=True)

    auth_provider_1_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": saml_provider_1.id},
    )

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "domain": "test.it",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_update_saml_provider_with_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()
    saml_provider_2 = enterprise_data_fixture.create_saml_auth_provider()

    _, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    _, unauthorized_token = data_fixture.create_user_and_token()

    auth_provider_1_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": saml_provider_1.id},
    )

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "domain": "test.it",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": 9999},
        ),
        {
            "type": SamlAuthProviderType.type,
            "enabled": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "domain": saml_provider_2.domain,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_SAML_PROVIDER_FOR_DOMAIN_ALREADY_EXISTS"

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "domain": "invalid_domain_name",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert json.dumps(response_json["detail"]) == json.dumps(
        {
            "domain": [
                {
                    "error": "The domain value is not a valid domain name.",
                    "code": "invalid",
                }
            ]
        }
    )

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "metadata": "invalid_metadata",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    response_json = response.json()
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert json.dumps(response_json["detail"]) == json.dumps(
        {
            "metadata": [
                {
                    "error": "The metadata is not valid according to the XML schema.",
                    "code": "invalid",
                }
            ]
        }
    )

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "domain": "test.it",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == saml_provider_1.id
    assert response_json["domain"] == "test.it"

    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "enabled": False,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == saml_provider_1.id
    assert response_json["enabled"] is False

    # Test that is_verified is ignored if the user tries to set it
    # This field is updated only when a user correctly logs in
    # with the SAML provider
    response = api_client.patch(
        auth_provider_1_url,
        {
            "type": SamlAuthProviderType.type,
            "is_verified": True,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json["id"] == saml_provider_1.id
    assert response_json["is_verified"] is False


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_delete_saml_provider_without_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()
    _, unauthorized_token = data_fixture.create_user_and_token(is_staff=True)

    auth_provider_1_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": saml_provider_1.id},
    )

    response = api_client.delete(
        auth_provider_1_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_delete_saml_provider_with_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    unrelated_provider = enterprise_data_fixture.create_saml_auth_provider()
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()

    _, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    _, unauthorized_token = data_fixture.create_user_and_token()

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": saml_provider_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    response = api_client.delete(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": saml_provider_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
    assert SamlAuthProviderModel.objects.count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_get_saml_provider_without_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()
    _, unauthorized_token = data_fixture.create_user_and_token(is_staff=True)

    auth_provider_1_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": saml_provider_1.id},
    )

    response = api_client.get(
        auth_provider_1_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_can_get_saml_provider_with_an_enterprise_license(
    api_client, data_fixture, enterprise_data_fixture
):
    saml_provider_1 = enterprise_data_fixture.create_saml_auth_provider()

    _, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    _, unauthorized_token = data_fixture.create_user_and_token()

    response = api_client.get(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": saml_provider_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {unauthorized_token}",
    )
    assert response.status_code == HTTP_403_FORBIDDEN

    response = api_client.get(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    response = api_client.get(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": saml_provider_1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == saml_provider_1.id
    assert response_json["type"] == SamlAuthProviderType.type
    assert response_json["enabled"] is True
    assert response_json["domain"] == saml_provider_1.domain
    assert response_json["metadata"] == saml_provider_1.metadata
    assert response_json["is_verified"] is False


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
def test_create_and_get_oauth2_provider(
    api_client, data_fixture, enterprise_data_fixture, provider_type, extra_params
):
    """
    Tests that a provider can be successfully created, and that login options
    endpoint will output correct information for the created provider.
    """

    data_fixture.create_password_provider()
    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    # create provider

    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {
            "type": provider_type,
            "name": "Provider name",
            "client_id": "clientid",
            "secret": "secret",
            **extra_params,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] is not None
    assert response_json["type"] == provider_type
    assert response_json["name"] == "Provider name"
    assert response_json["client_id"] == "clientid"
    assert response_json["secret"] == "secret"
    assert response_json["enabled"] is True

    # get created provider

    response = api_client.get(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": response_json["id"]},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == provider_type
    assert response_json["enabled"] is True
    assert response_json["name"] == "Provider name"
    assert response_json["client_id"] == "clientid"
    assert response_json["secret"] == "secret"
    for param in extra_params:
        assert response_json[param] == extra_params[param]

    # ensure the login option is now listed in the login options

    response = api_client.get(
        reverse("api:auth_provider:login_options"),
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json[provider_type]["items"][0]["name"] == "Provider name"
    assert response_json[provider_type]["items"][0]["type"] == provider_type
    assert response_json[provider_type]["items"][0]["redirect_url"]


@pytest.mark.parametrize(
    "provider_type,required_params",
    [
        ("google", ["name", "client_id", "secret"]),
        ("facebook", ["name", "client_id", "secret"]),
        ("github", ["name", "client_id", "secret"]),
        ("gitlab", ["name", "client_id", "secret", "base_url"]),
        ("openid_connect", ["name", "client_id", "secret", "base_url"]),
    ],
)
@pytest.mark.django_db
def test_create_oauth2_provider_required_fields(
    api_client, data_fixture, enterprise_data_fixture, provider_type, required_params
):
    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    response = api_client.post(
        reverse("api:enterprise:admin:auth_provider:list"),
        {
            "type": provider_type,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    for param in required_params:
        assert param in response_json["detail"]


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
def test_update_oauth2_provider(
    api_client, data_fixture, enterprise_data_fixture, provider_type, extra_params
):
    """
    Tests that a provider can be updated after it is created.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    unrelated_provider = enterprise_data_fixture.create_saml_auth_provider()
    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type, **extra_params
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": provider.id},
        ),
        {
            "name": "Provider name updated",
            "client_id": "clientid updated",
            "secret": "secret updated",
            "enabled": False,
            **extra_params,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["id"] is not None
    assert response_json["type"] == provider_type
    assert response_json["name"] == "Provider name updated"
    assert response_json["client_id"] == "clientid updated"
    assert response_json["secret"] == "secret updated"
    assert response_json["enabled"] is False


@pytest.mark.parametrize(
    "provider_type",
    [
        "gitlab",
        "openid_connect",
    ],
)
@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_update_oauth_provider_invalid_url(
    api_client, data_fixture, enterprise_data_fixture, provider_type
):
    """
    Tests that OAuth provider cannot be updated with
    invalid URL.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    provider = enterprise_data_fixture.create_oauth_provider(
        type=provider_type, base_url="https://gitlab.com"
    )

    response = api_client.patch(
        reverse(
            "api:enterprise:admin:auth_provider:item",
            kwargs={"auth_provider_id": provider.id},
        ),
        {"base_url": "not_url"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert json.dumps(response_json["detail"]) == json.dumps(
        {
            "base_url": [
                {
                    "error": "Enter a valid URL.",
                    "code": "invalid",
                }
            ]
        }
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_create_password_provider(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    Password provider cannot be created as to keep only one instance.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    auth_provider_1_url = reverse("api:enterprise:admin:auth_provider:list")

    response = api_client.post(
        auth_provider_1_url,
        {"type": "password", "enabled": True},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AUTH_PROVIDER_CANNOT_BE_CREATED"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_delete_password_provider(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    Password provider cannot be deleted, only enabled and disabled.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    password_provider = data_fixture.create_password_provider()
    auth_provider_1_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": password_provider.id},
    )

    response = api_client.delete(
        auth_provider_1_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_AUTH_PROVIDER_CANNOT_BE_DELETED"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_delete_last_provider(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    At least one auth provider needs to be always enabled.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    last_provider = enterprise_data_fixture.create_oauth_provider(type="github")

    # but they are not the last one
    last_provider_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": last_provider.id},
    )
    response = api_client.delete(
        last_provider_url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DISABLE_ALL_AUTH_PROVIDERS"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_disable_last_provider(
    api_client, data_fixture, enterprise_data_fixture
):
    """
    At least one auth provider needs to be always enabled.
    """

    admin, token = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    password_provider = data_fixture.create_password_provider()
    github_provider = enterprise_data_fixture.create_oauth_provider(type="github")

    # it is possible to disable second provider
    github_provider_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": github_provider.id},
    )
    response = api_client.patch(
        github_provider_url,
        {"enabled": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    # but they are not the last one
    password_provider_url = reverse(
        "api:enterprise:admin:auth_provider:item",
        kwargs={"auth_provider_id": password_provider.id},
    )
    response = api_client.patch(
        password_provider_url,
        {"enabled": False},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_DISABLE_ALL_AUTH_PROVIDERS"

from django.test.utils import override_settings

import pytest

from baserow.core.auth_provider.handler import AuthProviderHandler
from baserow.core.registries import auth_provider_type_registry
from baserow_enterprise.api.sso.saml.validators import (
    normalize_saml_metadata,
    validate_saml_metadata,
)
from baserow_enterprise.sso.saml.exceptions import SamlProviderForDomainAlreadyExists

AZURE_AD_ROLE_DESCRIPTOR = (
    '<RoleDescriptor xmlns:fed="http://docs.oasis-open.org/wsfed/federation/200706" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xsi:type="fed:SecurityTokenServiceType" '
    'protocolSupportEnumeration="http://docs.oasis-open.org/wsfed/federation/200706">'
    "<fed:PassiveRequestorEndpoint>"
    '<EndpointReference xmlns="http://www.w3.org/2005/08/addressing">'
    "<Address>https://login.microsoftonline.com/example/wsfed</Address>"
    "</EndpointReference>"
    "</fed:PassiveRequestorEndpoint>"
    "</RoleDescriptor>"
)


def add_azure_ad_role_descriptor(metadata):
    return metadata.replace(
        "<IDPSSODescriptor",
        f"{AZURE_AD_ROLE_DESCRIPTOR}<IDPSSODescriptor",
        1,
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_login_options(data_fixture, enterprise_data_fixture):
    data_fixture.create_password_provider()
    enterprise_data_fixture.create_saml_auth_provider(domain="test.com")
    login_options = auth_provider_type_registry.get_all_available_login_options()
    assert "saml" not in login_options

    enterprise_data_fixture.enable_enterprise()
    login_options = auth_provider_type_registry.get_all_available_login_options()
    assert login_options["saml"] == {
        "type": "saml",
        "domain_required": False,
        "default_redirect_url": "http://localhost:8000/api/sso/saml/login/",
    }

    enterprise_data_fixture.create_saml_auth_provider(domain="acme.com")
    login_options = auth_provider_type_registry.get_all_available_login_options()
    assert login_options["saml"] == {
        "type": "saml",
        "domain_required": True,
        "default_redirect_url": "http://localhost:3000/login/saml",
    }


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_cannot_create_two_saml_providers_for_the_same_domain(enterprise_data_fixture):
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    AuthProviderHandler.create_auth_provider(
        user,
        auth_provider_type_registry.get("saml"),
        domain="test.com",
        metadata=enterprise_data_fixture.get_test_saml_idp_metadata(),
    )
    with pytest.raises(SamlProviderForDomainAlreadyExists):
        AuthProviderHandler.create_auth_provider(
            user,
            auth_provider_type_registry.get("saml"),
            domain="test.com",
            metadata=enterprise_data_fixture.get_test_saml_idp_metadata(),
        )


def test_saml_metadata_validator_accepts_azure_ad_role_descriptors(
    enterprise_data_fixture,
):
    metadata = add_azure_ad_role_descriptor(
        enterprise_data_fixture.get_test_saml_idp_metadata()
    )

    assert "<RoleDescriptor" in metadata
    assert validate_saml_metadata(metadata) == metadata


def test_normalize_saml_metadata_removes_azure_ad_role_descriptors(
    enterprise_data_fixture,
):
    metadata = add_azure_ad_role_descriptor(
        enterprise_data_fixture.get_test_saml_idp_metadata()
    )

    normalized_metadata = normalize_saml_metadata(metadata)

    assert "RoleDescriptor" not in normalized_metadata
    assert "IDPSSODescriptor" in normalized_metadata


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_saml_provider_stores_normalized_azure_ad_metadata(enterprise_data_fixture):
    user, _ = enterprise_data_fixture.create_enterprise_admin_user_and_token()
    metadata = add_azure_ad_role_descriptor(
        enterprise_data_fixture.get_test_saml_idp_metadata()
    )

    provider = AuthProviderHandler.create_auth_provider(
        user,
        auth_provider_type_registry.get("saml"),
        domain="test.com",
        metadata=metadata,
    )

    assert "RoleDescriptor" not in provider.metadata
    assert "IDPSSODescriptor" in provider.metadata

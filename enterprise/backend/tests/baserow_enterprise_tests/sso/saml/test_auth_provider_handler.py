from django.test.utils import override_settings

import pytest

from baserow_enterprise.sso.saml.exceptions import InvalidSamlRequest
from baserow_enterprise.sso.saml.handler import SamlAuthProviderHandler


@pytest.mark.django_db()
@pytest.mark.parametrize(
    "email_attr_key,first_name_attr_key,last_name_attr_key",
    [
        ("user.email", "user.first_name", "user.last_name"),
        ("user.email", "user.first_name", ""),
        ("email", "name", "giveName"),
        ("email", "name", ""),
    ],
)
@override_settings(DEBUG=True)
def test_get_user_info_from_authn_user_identity(
    email_attr_key, first_name_attr_key, last_name_attr_key, enterprise_data_fixture
):
    auth_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com",
        email_attr_key=email_attr_key,
        first_name_attr_key=first_name_attr_key,
        last_name_attr_key=last_name_attr_key,
    )
    user_info = SamlAuthProviderHandler.get_user_info_from_authn_user_identity(
        auth_provider, {email_attr_key: ["some@email.com"], "user.name": ["John"]}
    )
    assert user_info.email == "some@email.com"
    assert user_info.name == "John"

    user_info = SamlAuthProviderHandler.get_user_info_from_authn_user_identity(
        auth_provider,
        {
            email_attr_key: ["some@email.com"],
            first_name_attr_key: ["John"],
        },
    )
    assert user_info.email == "some@email.com"
    assert user_info.name == "John"

    user_info = SamlAuthProviderHandler.get_user_info_from_authn_user_identity(
        auth_provider,
        {
            email_attr_key: ["some@email.com"],
            first_name_attr_key: ["John"],
            last_name_attr_key: ["Doe"],
        },
    )
    assert user_info.email == "some@email.com"
    assert user_info.name == "John Doe"
    assert user_info.language is None
    assert user_info.workspace_invitation_token is None

    user_info = SamlAuthProviderHandler.get_user_info_from_authn_user_identity(
        auth_provider, {email_attr_key: ["some@email.com"]}
    )
    assert user_info.email == "some@email.com"
    assert user_info.name == "some@email.com"

    user_info = SamlAuthProviderHandler.get_user_info_from_authn_user_identity(
        auth_provider,
        {email_attr_key: ["some@email.com"], "user.name": ["John Doe"]},
        {"language": "it", "workspace_invitation_token": "1234"},
    )
    assert user_info.email == "some@email.com"
    assert user_info.name == "John Doe"
    assert user_info.language == "it"
    assert user_info.workspace_invitation_token == "1234"


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_no_need_for_email_if_single_saml_provider(enterprise_data_fixture):
    saml_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )

    assert (
        SamlAuthProviderHandler.get_saml_auth_provider_from_email().domain
        == saml_provider.domain
    )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_need_valid_email_if_multiple_saml_providers(enterprise_data_fixture):
    saml_provider = enterprise_data_fixture.create_saml_auth_provider(
        domain="test1.com"
    )
    enterprise_data_fixture.create_saml_auth_provider(domain="test2.com")

    with pytest.raises(InvalidSamlRequest):
        assert (
            SamlAuthProviderHandler.get_saml_auth_provider_from_email().domain
            == saml_provider.domain
        )

    assert (
        SamlAuthProviderHandler.get_saml_auth_provider_from_email(
            "hello@test1.com"
        ).domain
        == saml_provider.domain
    )


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_cannot_retrieve_saml_provider_from_invalid_mail(enterprise_data_fixture):
    enterprise_data_fixture.create_saml_auth_provider(domain="test1.com")
    with pytest.raises(InvalidSamlRequest):
        SamlAuthProviderHandler.get_saml_auth_provider_from_email("invalid_mail")

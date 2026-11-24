import pytest

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.integrations.common.sso.saml.models import (
    SamlAppAuthProviderModel,
)

from ...local_baserow.helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


@pytest.mark.django_db
@pytest.mark.parametrize("exclude_sensitive_data", [True, False])
@pytest.mark.parametrize("is_user_template", [True, False])
def test_saml_app_auth_provider_sensitive_settings_round_trip(
    data_fixture, enterprise_data_fixture, exclude_sensitive_data, is_user_template
):
    """Stripped providers import unconfigured; internal copies retain SAML settings."""

    data = populate_local_baserow_test_data(data_fixture)
    metadata = enterprise_data_fixture.get_test_saml_idp_metadata()
    provider = data_fixture.create_app_auth_provider(
        SamlAppAuthProviderModel,
        user_source=data["unpublished_user_source"],
        metadata=metadata,
        is_verified=True,
        email_attr_key="email",
    )
    provider_type = provider.get_type()
    config = ImportExportConfig(
        include_permission_data=False,
        exclude_sensitive_data=exclude_sensitive_data,
        is_user_template=is_user_template,
    )
    exported = provider_type.export_serialized(provider, config)
    assert exported["metadata"] == (None if exclude_sensitive_data else metadata)
    assert exported["is_verified"] is (None if exclude_sensitive_data else True)
    imported = provider_type.import_serialized(provider.user_source, exported, {})
    assert imported.metadata == ("" if exclude_sensitive_data else metadata)
    assert imported.is_verified is (not exclude_sensitive_data)
    assert imported.email_attr_key == "email"
    provider.refresh_from_db()
    assert provider.metadata == metadata
    assert provider.is_verified is True


@pytest.mark.django_db
def test_saml_app_auth_provider_attr_keys_are_exported(
    data_fixture, enterprise_data_fixture
):
    """
    The attribute keys map the IdP response onto the user fields, so losing them on
    export means the published application falls back to the model defaults and can't
    read the email of the user anymore.
    """

    data = populate_local_baserow_test_data(data_fixture)

    auth_provider = data_fixture.create_app_auth_provider(
        SamlAppAuthProviderModel,
        user_source=data["unpublished_user_source"],
        domain="test.com",
        metadata=enterprise_data_fixture.get_test_saml_idp_metadata(),
        email_attr_key="email",
        first_name_attr_key="firstName",
        last_name_attr_key="lastName",
    )

    exported = auth_provider.get_type().export_serialized(auth_provider)

    assert exported["email_attr_key"] == "email"
    assert exported["first_name_attr_key"] == "firstName"
    assert exported["last_name_attr_key"] == "lastName"


@pytest.mark.django_db
def test_saml_app_auth_provider_attr_keys_survive_publishing(
    data_fixture, enterprise_data_fixture
):
    """
    The provider of the published app must keep the configured attribute keys.
    """

    data = populate_local_baserow_test_data(data_fixture)

    domain = data["domain"]
    domain.domain_name = "test.com"
    domain.save()

    data_fixture.create_app_auth_provider(
        SamlAppAuthProviderModel,
        user_source=data["unpublished_user_source"],
        domain="test.com",
        metadata=enterprise_data_fixture.get_test_saml_idp_metadata(),
        email_attr_key="email",
        first_name_attr_key="firstName",
        last_name_attr_key="lastName",
    )

    domain = DomainHandler().publish(domain)

    published_provider = SamlAppAuthProviderModel.objects.get(
        user_source__application=domain.published_to
    )

    assert published_provider.email_attr_key == "email"
    assert published_provider.first_name_attr_key == "firstName"
    assert published_provider.last_name_attr_key == "lastName"

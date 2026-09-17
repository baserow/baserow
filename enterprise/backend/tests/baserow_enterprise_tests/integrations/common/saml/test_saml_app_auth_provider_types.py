import pytest

from baserow.contrib.builder.api.domains.serializers import (
    PublicPolymorphicAppAuthProviderSerializer,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow_enterprise.integrations.common.sso.oauth2.models import (
    OpenIdConnectAppAuthProviderModel,
)
from baserow_enterprise.integrations.common.sso.saml.models import (
    SamlAppAuthProviderModel,
)
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowPasswordAppAuthProvider,
)

from ...local_baserow.helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model, enabled, expected",
    [
        (SamlAppAuthProviderModel, True, True),
        (SamlAppAuthProviderModel, False, False),
        (OpenIdConnectAppAuthProviderModel, True, True),
        (OpenIdConnectAppAuthProviderModel, False, False),
        (LocalBaserowPasswordAppAuthProvider, True, False),
    ],
)
def test_public_provider_declares_callback_support(
    data_fixture, model, enabled, expected
):
    data = populate_local_baserow_test_data(data_fixture)
    provider = data_fixture.create_app_auth_provider(
        model, user_source=data["unpublished_user_source"], enabled=enabled
    )
    assert (
        PublicPolymorphicAppAuthProviderSerializer(provider).data["supports_callback"]
        is expected
    )

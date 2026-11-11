from io import BytesIO

from django.db import transaction

import pytest

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.integrations.common.sso.oauth2.models import (
    OpenIdConnectAppAuthProviderModel,
)

from ...local_baserow.helpers import populate_local_baserow_test_data


@pytest.fixture(autouse=True)
def enable_enterprise_for_all_tests_here(enable_enterprise):
    pass


def create_oidc_app_auth_provider(data_fixture, user_source):
    return data_fixture.create_app_auth_provider(
        OpenIdConnectAppAuthProviderModel,
        user_source=user_source,
        name="oidc",
        base_url="https://idp.example.com",
        client_id="clientid",
        secret="SUPERSECRET",
    )


@pytest.mark.django_db(transaction=True)
def test_oidc_app_auth_provider_workspace_export_excludes_the_secret(data_fixture):
    """
    A workspace export can leave the installation, so it must not carry the client
    secret of the OIDC provider, and the stripped export must still import.
    """

    # The test data publishes the builder, which locks the domain.
    with transaction.atomic():
        data = populate_local_baserow_test_data(data_fixture)
    user = data["user"]
    user_source = data["unpublished_user_source"]
    create_oidc_app_auth_provider(data_fixture, user_source)
    workspace = user_source.application.workspace
    imported_workspace = data_fixture.create_workspace(user=user)

    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(
        workspace,
        BytesIO(),
        ImportExportConfig(include_permission_data=False, exclude_sensitive_data=True),
    )

    assert "SUPERSECRET" not in str(exported)
    (exported_builder,) = [app for app in exported if app["type"] == "builder"]
    (exported_provider,) = [
        ap
        for ap in exported_builder["user_sources"][0]["auth_providers"]
        if ap["type"] == "openid_connect"
    ]
    assert exported_provider["secret"] is None
    assert exported_provider["client_id"] == "clientid"

    core_handler.import_applications_to_workspace(
        imported_workspace,
        exported,
        BytesIO(),
        ImportExportConfig(include_permission_data=False),
        None,
    )

    imported_provider = OpenIdConnectAppAuthProviderModel.objects.get(
        user_source__application__workspace=imported_workspace
    )
    assert imported_provider.secret == ""
    assert imported_provider.client_id == "clientid"
    assert imported_provider.base_url == "https://idp.example.com"


@pytest.mark.django_db
def test_oidc_app_auth_provider_duplicate_keeps_the_secret(data_fixture):
    data = populate_local_baserow_test_data(data_fixture)
    user_source = data["unpublished_user_source"]
    create_oidc_app_auth_provider(data_fixture, user_source)

    duplicated_builder = CoreHandler().duplicate_application(
        data["user"], user_source.application
    )

    duplicated_provider = OpenIdConnectAppAuthProviderModel.objects.get(
        user_source__application=duplicated_builder
    )
    assert duplicated_provider.secret == "SUPERSECRET"


@pytest.mark.django_db
def test_oidc_app_auth_provider_publish_keeps_the_secret(data_fixture):
    data = populate_local_baserow_test_data(data_fixture)
    create_oidc_app_auth_provider(data_fixture, data["unpublished_user_source"])

    domain = DomainHandler().publish(data["domain"])

    published_provider = OpenIdConnectAppAuthProviderModel.objects.get(
        user_source__application=domain.published_to
    )
    assert published_provider.secret == "SUPERSECRET"

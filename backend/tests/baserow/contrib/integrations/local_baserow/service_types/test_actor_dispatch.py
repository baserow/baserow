import pytest

from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_get_acting_user_prefers_the_integration(data_fixture):
    user = data_fixture.create_user()
    clicker = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration
    )

    acting_user = LocalBaserowUpsertRowServiceType().get_acting_user(
        service, FakeDispatchContext(actor=clicker)
    )

    assert acting_user == user


@pytest.mark.django_db
def test_get_acting_user_falls_back_to_the_actor(data_fixture):
    clicker = data_fixture.create_user()
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)

    acting_user = LocalBaserowUpsertRowServiceType().get_acting_user(
        service, FakeDispatchContext(actor=clicker)
    )

    assert acting_user == clicker


@pytest.mark.django_db
def test_get_acting_user_raises_without_an_integration_or_an_actor(data_fixture):
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        LocalBaserowUpsertRowServiceType().get_acting_user(
            service, FakeDispatchContext()
        )


@pytest.mark.django_db
def test_get_permission_workspace_uses_the_integration_application(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    database = data_fixture.create_database_application(
        workspace=page.builder.workspace
    )
    table = data_fixture.create_database_table(database=database)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=integration, table=table
    )

    workspace = LocalBaserowUpsertRowServiceType().get_permission_workspace(service)

    assert workspace == page.builder.workspace


@pytest.mark.django_db
def test_get_permission_workspace_falls_back_to_the_table(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )

    workspace = LocalBaserowUpsertRowServiceType().get_permission_workspace(service)

    assert workspace == table.database.workspace

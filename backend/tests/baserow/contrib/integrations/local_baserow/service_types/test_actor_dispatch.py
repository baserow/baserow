import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
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


def _table_with_name_field(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="Actors",
        fields=[("Name", "text", {})],
    )
    return table, table.field_set.get(name="Name")


@pytest.mark.django_db
def test_create_rows_dispatches_as_the_actor(data_fixture):
    actor = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, actor)
    service = data_fixture.create_local_baserow_create_rows_service(
        integration=None,
        table=table,
        rows='get("page_parameter.rows")',
    )

    ServiceHandler().dispatch_service(
        service,
        FakeDispatchContext(
            actor=actor, context={"page_parameter": {"rows": [{"Name": "Ada"}]}}
        ),
    )

    (row,) = table.get_model().objects.all()
    assert getattr(row, f"field_{name_field.id}") == "Ada"


@pytest.mark.django_db
def test_upsert_row_dispatches_as_the_actor(data_fixture):
    actor = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, actor)
    service = data_fixture.create_local_baserow_upsert_row_service(
        integration=None, table=table
    )
    service.field_mappings.create(field=name_field, value="'Ada'", enabled=True)

    ServiceHandler().dispatch_service(service, FakeDispatchContext(actor=actor))

    (row,) = table.get_model().objects.all()
    assert getattr(row, f"field_{name_field.id}") == "Ada"


@pytest.mark.django_db
def test_update_rows_dispatches_as_the_actor(data_fixture):
    actor = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, actor)
    (row,) = (
        RowHandler()
        .force_create_rows(
            user=actor, table=table, rows_values=[{f"field_{name_field.id}": "Ada"}]
        )
        .created_rows
    )
    service = data_fixture.create_local_baserow_update_rows_service(
        integration=None,
        table=table,
        rows='get("page_parameter.rows")',
    )

    ServiceHandler().dispatch_service(
        service,
        FakeDispatchContext(
            actor=actor,
            context={"page_parameter": {"rows": [{"id": row.id, "Name": "Grace"}]}},
        ),
    )

    row.refresh_from_db()
    assert getattr(row, f"field_{name_field.id}") == "Grace"


@pytest.mark.django_db
def test_delete_row_dispatches_as_the_actor(data_fixture):
    actor = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, actor)
    (row,) = (
        RowHandler()
        .force_create_rows(
            user=actor, table=table, rows_values=[{f"field_{name_field.id}": "Ada"}]
        )
        .created_rows
    )
    service = data_fixture.create_local_baserow_delete_row_service(
        integration=None, table=table, row_id=f"'{row.id}'"
    )

    ServiceHandler().dispatch_service(service, FakeDispatchContext(actor=actor))

    assert table.get_model().objects.count() == 0


@pytest.mark.django_db
def test_dispatching_without_an_integration_or_an_actor_is_rejected(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, user)
    service = data_fixture.create_local_baserow_create_rows_service(
        integration=None,
        table=table,
        rows='get("page_parameter.rows")',
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(
            service,
            FakeDispatchContext(
                context={"page_parameter": {"rows": [{"Name": "Ada"}]}}
            ),
        )


@pytest.mark.django_db
def test_an_actor_without_table_permission_cannot_dispatch(data_fixture):
    owner = data_fixture.create_user()
    outsider = data_fixture.create_user()
    table, name_field = _table_with_name_field(data_fixture, owner)
    service = data_fixture.create_local_baserow_create_rows_service(
        integration=None,
        table=table,
        rows='get("page_parameter.rows")',
    )

    with pytest.raises(UserNotInWorkspace):
        ServiceHandler().dispatch_service(
            service,
            FakeDispatchContext(
                actor=outsider,
                context={"page_parameter": {"rows": [{"Name": "Ada"}]}},
            ),
        )

    assert table.get_model().objects.count() == 0

from unittest.mock import Mock

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowDeleteRow
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
)
from baserow.core.services.exceptions import DoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.mark.django_db
def test_create_local_baserow_delete_row_service(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service_type = LocalBaserowDeleteRowServiceType()
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "row_id": "",
        },
        user,
    )
    service: LocalBaserowDeleteRow = ServiceHandler().create_service(  # type: ignore
        service_type, **values
    )

    assert service.table.id == table.id
    assert service.row_id["formula"] == ""


@pytest.mark.django_db
def test_update_local_baserow_delete_row_service(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    page = data_fixture.create_builder_page(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service = data_fixture.create_local_baserow_delete_row_service(
        integration=integration,
        table=table,
    )

    service_type = LocalBaserowDeleteRowServiceType()
    values = service_type.prepare_values(
        {"row_id": "1"},
        user,
    )

    ServiceHandler().update_service(service_type, service, **values)

    service.refresh_from_db()

    assert service.row_id["formula"] == "1"


@pytest.mark.django_db
def test_local_baserow_delete_row_service_dispatch_data_with_no_row_id(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    assert model.objects.count() == 0

    service = data_fixture.create_local_baserow_delete_row_service(
        integration=integration, table=table, row_id=""
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["data"] == {}


@pytest.mark.django_db
def test_local_baserow_delete_row_service_dispatch_data_row_not_exist(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    model = table.get_model()
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    assert model.objects.count() == 0

    service = data_fixture.create_local_baserow_delete_row_service(
        integration=integration, table=table, row_id="1"
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    with pytest.raises(DoesNotExist) as exc:
        service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert exc.value.args[0] == "The row with id 1 does not exist."


@pytest.mark.django_db
def test_local_baserow_delete_row_service_dispatch_data(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name")
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": "Dog"},
            {f"field_{field.id}": "Badger"},
            {f"field_{field.id}": "Horse"},
        ],
    )

    model = table.get_model()
    row1 = model.objects.get(id=1)
    assert getattr(row1, f"field_{field.id}") == "Dog"

    service = data_fixture.create_local_baserow_delete_row_service(
        integration=integration, table=table, row_id=str(row1.id)
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["data"] == {}
    assert model.objects.count() == 2
    assert model.objects.filter(id=1).exists() is False


@pytest.mark.django_db
def test_local_baserow_delete_row_service_dispatch_transform(data_fixture):
    service_type = LocalBaserowDeleteRowServiceType()
    dispatch_data = {"data": {}, "baserow_table_model": Mock()}
    result = service_type.dispatch_transform(dispatch_data)
    assert result.status == 204

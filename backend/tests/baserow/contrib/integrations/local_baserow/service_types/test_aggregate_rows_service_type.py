from decimal import Decimal
from unittest.mock import Mock

from django.db import transaction

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowAggregateRows
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def test_local_baserow_aggregate_rows_service_get_schema_name():
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    assert service_type.get_schema_name(Mock(id=123)) == "Aggregation123Schema"


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_service_generate_schema(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        table_id=table.id,
        field_id=field.id,
        aggregation_type="sum",
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    assert service_type.generate_schema(service) == {
        "title": f"Aggregation{service.id}Schema",
        "type": "object",
        "properties": {
            "result": {
                "title": f"{field.name} result",
                "type": "string",
            },
        },
    }
    assert service_type.generate_schema(Mock(field=None)) is None
    assert service_type.generate_schema(Mock(aggregation_type="")) is None


def test_local_baserow_aggregate_rows_resolve_service_formulas():
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.resolve_service_formulas(Mock(field=None), FakeDispatchContext())
    assert exc.value.args[0] == "The field property is missing."

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.resolve_service_formulas(
            Mock(field=123, aggregation_type="foobar"), FakeDispatchContext()
        )
    assert exc.value.args[0] == "The field_aggregations type foobar does not exist."


@pytest.mark.django_db
def test_create_local_baserow_aggregate_rows_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )

    service = ServiceHandler().create_service(service_type, **values)

    assert service.integration.id == integration.id
    assert service.table.id == view.table_id
    assert service.view.id == view.id
    assert service.field.id == field.id
    assert service.aggregation_type == "sum"


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_prepare_values_reset_field_when_table_change(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    service = LocalBaserowAggregateRows.objects.create(
        table=view.table,
        view=view,
        field=field,
    )

    prepared_value = service_type.prepare_values(
        {
            "table_id": table_2.id,
        },
        user,
        instance=service,
    )

    assert prepared_value["field"] is None


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_prepare_values_incorrect_field(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table_2)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    # field doesn't exist
    with pytest.raises(
        FieldDoesNotExist, match=f"The field with id 999 does not exist"
    ):
        service_type.prepare_values(
            {
                "view_id": view.id,
                "table_id": view.table_id,
                "integration_id": integration.id,
                "field_id": 999,
                "aggregation_type": "",
            },
            user,
        )

    # field is not in table
    with pytest.raises(
        ValidationError, match=f"The field with ID {field.id} is not related"
    ):
        service_type.prepare_values(
            {
                "view_id": view.id,
                "table_id": view.table_id,
                "integration_id": integration.id,
                "field_id": field.id,
                "aggregation_type": "",
            },
            user,
        )


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_prepare_values_incompatible_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field.id} is not compatible with aggregation type",
    ):
        service_type.prepare_values(
            {
                "view_id": view.id,
                "table_id": view.table_id,
                "integration_id": integration.id,
                "field_id": field.id,
                "aggregation_type": "sum",
            },
            user,
        )


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_with_table(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 6},
            {f"field_{field.id}": 8},
        ],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": Decimal("20")}


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_with_view(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 6},
            {f"field_{field.id}": 8},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": Decimal("20")}


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_with_total(data_fixture):
    """
    Tests an aggregation that is not based only on
    'raw_aggregation' but has additional computation.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "empty_percentage",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": 50.0}


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_with_view_filters(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
            {f"field_{field.id}": 4},
            {f"field_{field.id}": 6},
            {f"field_{field.id}": 8},
            {f"field_{field.id}": None},
            {f"field_{field.id}": None},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_filter(
        view=view, field=field, type="lower_than", value="5"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": 6.0}


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_with_service_filters(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 100},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 200},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 300},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 400},
            {f"field_{field.id}": 10, f"field_{field_2.id}": 500},
            {f"field_{field.id}": 12, f"field_{field_2.id}": 600},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_filter(
        view=view, field=field, type="lower_than", value="10"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field_2, type="higher_than", value="200", order=1
    )
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": 14.0}


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_local_baserow_aggregate_rows_dispatch_data_with_search(data_fixture):
    with transaction.atomic():
        user = data_fixture.create_user()
        page = data_fixture.create_builder_page(user=user)
        dashboard = page.builder
        table = data_fixture.create_database_table(user=user)
        field = data_fixture.create_text_field(table=table)
        field_2 = data_fixture.create_number_field(table=table)
        RowHandler().create_rows(
            user,
            table,
            rows_values=[
                {f"field_{field.id}": "yellow", f"field_{field_2.id}": 100},
                {f"field_{field.id}": "yellow", f"field_{field_2.id}": 200},
                {f"field_{field.id}": "yellow", f"field_{field_2.id}": 300},
                {f"field_{field.id}": "blue", f"field_{field_2.id}": 400},
                {f"field_{field.id}": "blue", f"field_{field_2.id}": 500},
                {f"field_{field.id}": "blue", f"field_{field_2.id}": 600},
            ],
        )
        integration = data_fixture.create_local_baserow_integration(
            application=dashboard, user=user
        )
        service_type = service_type_registry.get("local_baserow_aggregate_rows")
        values = service_type.prepare_values(
            {
                "table_id": table.id,
                "integration_id": integration.id,
                "field_id": field_2.id,
                "aggregation_type": "sum",
                "search_query": "'blue'",
            },
            user,
        )
        service = ServiceHandler().create_service(service_type, **values)
        dispatch_context = FakeDispatchContext()
        dispatch_values = service_type.resolve_service_formulas(
            service, dispatch_context
        )
    result = service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert result["baserow_table_model"]
    assert result["data"] == {"result": 1500.0}


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_field_deleted(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)

    field.delete()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field.id} does not exist."


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_field_trashed(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)

    FieldHandler().delete_field(user, field)
    service.refresh_from_db()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field.id} is trashed."


@pytest.mark.django_db
def test_local_baserow_aggregate_rows_dispatch_data_field_type_not_compatible_anymore(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2},
        ],
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "field_id": field.id,
            "aggregation_type": "sum",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()
    dispatch_values = service_type.resolve_service_formulas(service, dispatch_context)

    FieldHandler().update_field(user, field, "text")
    service.refresh_from_db()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch_data(service, dispatch_values, dispatch_context)
    assert (
        exc.value.args[0] == f"The field with ID {field.id} is not compatible "
        f"with the aggregation type {service.aggregation_type}"
    )


@pytest.mark.django_db
def test_create_local_baserow_aggregate_rows_service_with_unsupported_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    dashboard = page.builder
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        table=table, field=field, integration=integration
    )
    service_type = service.get_type()
    unsupported_agg_type = service_type.unsupported_aggregation_types[0]

    with pytest.raises(
        ValidationError,
        match=f"The {unsupported_agg_type} aggregation type is not currently supported.",
    ):
        service_type.prepare_values({"aggregation_type": unsupported_agg_type}, user)

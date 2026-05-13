from decimal import Decimal
from unittest.mock import Mock

from django.contrib.contenttypes.models import ContentType

import pytest
from pytest_unordered import unordered
from rest_framework.exceptions import ValidationError
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.data_providers.data_provider_types import (
    CurrentRecordDataProviderType,
    DataSourceDataProviderType,
)
from baserow.contrib.builder.elements.element_types import RecordSelectorElementType
from baserow.contrib.builder.formula_property_extractor import (
    get_element_property_names,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
    LocalBaserowTableServiceAggregationSortBy,
)
from baserow_premium.integrations.local_baserow.service_types import (
    LocalBaserowGroupedAggregateRowsUserServiceType,
)


@pytest.fixture(autouse=True)
def enable_grouped_aggregate_rows_feature(mocker):
    mocker.patch(
        "baserow_premium.integrations.local_baserow.service_types."
        "LicenseHandler.workspace_has_feature",
        return_value=True,
    )
    mocker.patch(
        "baserow_premium.integrations.local_baserow.service_types."
        "LicenseHandler.raise_if_workspace_doesnt_have_feature",
        return_value=None,
    )


def without_grouped_row_ids(result):
    return {
        **result,
        "results": [
            {key: value for key, value in row.items() if key != "id"}
            for row in result["results"]
        ],
    }


def expected_grouped_dispatch_data(service, expected):
    expects_unordered_results = type(expected["results"]).__name__ == "UnorderedList"
    results = [
        {
            key: value
            for key, value in service.get_type()
            ._convert_result_property_names_to_human_names(service, row)
            .items()
            if key != "id"
        }
        for row in expected["results"]
    ]

    return {
        **expected,
        "results": unordered(results) if expects_unordered_results else results,
    }


def test_grouped_aggregate_rows_service_get_schema_name():
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    assert service_type.get_schema_name(Mock(id=123)) == "GroupedAggregation123Schema"


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_generate_schema_without_group_by(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    schema = service_type.generate_schema(service)
    result_property = schema["items"]["properties"][f"field_{field.id}_sum"]

    assert schema["type"] == "array"
    assert f"field_{field.id}_sum" in schema["items"]["properties"]
    assert result_property["metadata"] == {
        "display_name": "Amount sum",
        "source_field": {
            "id": field.id,
            "name": field.db_column,
            "display_name": "Amount",
        },
        "aggregation": {
            "type": "sum",
        },
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_generate_schema_with_group_by(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    schema = service_type.generate_schema(service)

    assert schema["type"] == "array"
    assert f"field_{field.id}_sum" in schema["items"]["properties"]
    assert f"field_{group_by_field.id}" in schema["items"]["properties"]
    assert (
        schema["items"]["properties"][f"field_{group_by_field.id}"]["filterable"]
        is False
    )
    assert (
        schema["items"]["properties"][f"field_{group_by_field.id}"]["sortable"] is False
    )
    assert (
        schema["items"]["properties"][f"field_{group_by_field.id}"]["searchable"]
        is False
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_generate_schema_with_row_id_group_by(
    data_fixture,
):
    table = data_fixture.create_database_table()
    primary_field = data_fixture.create_text_field(table=table, primary=True)
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    schema = service_type.generate_schema(service)
    primary_field_schema = schema["items"]["properties"][primary_field.db_column]

    assert schema["items"]["properties"]["id"]["filterable"] is False
    assert primary_field_schema["filterable"] is False
    assert primary_field_schema["sortable"] is False
    assert primary_field_schema["searchable"] is False


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_generate_schema_allowed_fields(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table)
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    assert service_type.generate_schema(service, allowed_fields=["other"]) == {
        "type": "array",
        "title": service_type.get_schema_name(service),
        "items": {"type": "object", "properties": {}},
    }
    assert (
        f"field_{field.id}_sum"
        in service_type.generate_schema(
            service, allowed_fields=[f"field_{field.id}_sum"]
        )["items"]["properties"]
    )
    assert service_type.generate_schema(service, allowed_fields=["id"])["items"][
        "properties"
    ] == {
        "id": {
            "title": "Id",
            "type": "string",
            "sortable": False,
            "filterable": False,
            "searchable": False,
        }
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_extract_properties(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    sum_property = f"field_{field.id}_sum"
    group_by_property = f"field_{group_by_field.id}"
    all_properties = ["id", group_by_property, sum_property]

    assert service_type.extract_properties(service, []) == all_properties
    assert service_type.extract_properties(service, [sum_property]) == [sum_property]
    assert service_type.extract_properties(service, ["0", sum_property]) == []
    assert service_type.extract_properties(service, ["*", group_by_property]) == []
    assert service_type.extract_properties(service, ["0"]) == []
    assert service_type.extract_properties(service, ["*", sum_property, "value"]) == []
    assert service_type.extract_properties(service, [group_by_property, "value"]) == [
        group_by_property
    ]
    assert service_type.extract_properties(service, ["unknown"]) == []


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_prepare_value_path(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    sum_property = f"field_{field.id}_sum"
    group_by_property = f"field_{group_by_field.id}"

    assert service_type.prepare_value_path(service, []) == []
    assert service_type.prepare_value_path(service, ["unknown"]) == ["unknown"]
    assert service_type.prepare_value_path(service, [group_by_property]) == ["Category"]
    assert service_type.prepare_value_path(service, [sum_property]) == ["Amount sum"]
    assert service_type.prepare_value_path(service, [sum_property, "value"]) == [
        "Amount sum",
        "value",
    ]


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_extract_properties(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page, service=service)
    sum_property = f"field_{field.id}_sum"

    result = DataSourceDataProviderType().extract_properties(
        [data_source.id, "0", sum_property]
    )

    assert result == {service.id: [sum_property]}

    result = DataSourceDataProviderType().extract_properties(
        [data_source.id, "0", "id"]
    )

    assert result == {service.id: ["id"]}


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_can_be_used_by_record_selector(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    data_source = data_fixture.create_builder_data_source(page=page, service=service)
    element = data_fixture.create_builder_element(
        RecordSelectorElementType, user=user, page=page
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )

    url = reverse(
        "api:builder:element:item",
        kwargs={"element_id": element.id},
    )
    response = api_client.patch(
        url,
        {
            "data_source_id": data_source.id,
            "items_per_page": 20,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["data_source_id"] == data_source.id


@pytest.mark.django_db
def test_grouped_aggregate_rows_current_record_extract_properties(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page, service=service)
    sum_property = f"field_{field.id}_sum"

    result = CurrentRecordDataProviderType().extract_properties(
        [sum_property], data_source.id
    )

    assert result == {service.id: [sum_property]}


@pytest.mark.django_db
def test_grouped_aggregate_rows_table_field_extract_properties(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_data_source(page=page, service=service)
    sum_property = f"field_{field.id}_sum"
    table_element = data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Amount sum",
                "type": "text",
                "config": {"value": f"get('current_record.{sum_property}')"},
            },
        ],
    )

    result = get_element_property_names([table_element], {})

    assert result == {"external": {service.id: unordered([sum_property, "id"])}}


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_adds_synthetic_row_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    integration = data_fixture.create_local_baserow_integration(user=user)
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: 1, group_by_field.db_column: "A"},
            {field.db_column: 2, group_by_field.db_column: "B"},
        ],
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    dispatch_context = FakeDispatchContext()

    result = service_type.dispatch_data(service, {}, dispatch_context)["data"][
        "results"
    ]

    assert [row["id"] for row in result] == ["A", "B"]
    dispatch_context.only_record_id = result[1]["id"]

    result = service_type.dispatch_data(service, {}, dispatch_context)["data"][
        "results"
    ]

    assert len(result) == 1
    assert result[0]["id"] == "B"


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_get_record_names(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    integration = data_fixture.create_local_baserow_integration(user=user)
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: 1, group_by_field.db_column: "A"},
            {field.db_column: 2, group_by_field.db_column: "B"},
        ],
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    assert service_type.get_name_property(service) == group_by_field.db_column

    record_names = service_type.get_record_names(
        service, {"A", "B"}, FakeDispatchContext()
    )

    assert set(record_names.keys()) == {"A", "B"}
    assert set(record_names.values()) == {"A", "B"}


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_record_id_uses_field_type_human_value(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_single_select_field(table=table)
    option_a = data_fixture.create_select_option(
        field=group_by_field, value="Category A", color="red"
    )
    option_b = data_fixture.create_select_option(
        field=group_by_field, value="Category B", color="blue"
    )
    integration = data_fixture.create_local_baserow_integration(user=user)
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: 1, group_by_field.db_column: option_a.id},
            {field.db_column: 2, group_by_field.db_column: option_b.id},
        ],
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    result = service_type.dispatch_data(service, {}, FakeDispatchContext())["data"][
        "results"
    ]
    record_names = service_type.get_record_names(
        service, {"Category A", "Category B"}, FakeDispatchContext()
    )

    assert {row["id"] for row in result} == {"Category A", "Category B"}
    assert record_names == {
        "Category A": "Category A",
        "Category B": "Category B",
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_data_source_get_record_names_endpoint(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    data_source = data_fixture.create_builder_data_source(page=page, service=service)
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: 1, group_by_field.db_column: "A"},
            {field.db_column: 2, group_by_field.db_column: "B"},
        ],
    )

    url = reverse(
        "api:builder:data_source:record-names",
        kwargs={"data_source_id": data_source.id},
    )
    response = api_client.get(
        f"{url}?record_ids=A,B,Not%20currently%20loaded",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "A": "A",
        "B": "B",
        "Not currently loaded": "Not currently loaded",
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_ungrouped_record_id_is_readable(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    integration = data_fixture.create_local_baserow_integration(user=user)
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[{field.db_column: 1}, {field.db_column: 2}],
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    result = service_type.dispatch_data(service, {}, FakeDispatchContext())["data"][
        "results"
    ]

    assert result[0]["id"] == "Result"


@pytest.mark.django_db
def test_grouped_aggregate_rows_sanitize_result_uses_grouped_result_keys(data_fixture):
    table = data_fixture.create_database_table()
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_text_field(table=table, name="Category")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    sum_property = f"field_{field.id}_sum"
    group_by_property = f"field_{group_by_field.id}"

    result = service_type.sanitize_result(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    group_by_property: "Fruit",
                    sum_property: 10,
                    "field_unused": "removed",
                }
            ],
        },
        [group_by_property, sum_property],
    )

    assert result == {
        "has_next_page": False,
        "results": [
            {
                group_by_property: "Fruit",
                sum_property: 10,
            }
        ],
    }


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_no_data(data_fixture):
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    service = ServiceHandler().create_service(service_type)

    assert service.content_type == ContentType.objects.get_for_model(
        LocalBaserowGroupedAggregateRows
    )
    assert service.table_id is None
    assert service.view_id is None
    assert service.integration_id is None
    assert service.service_aggregation_series.all().count() == 0
    assert service.service_aggregation_group_bys.all().count() == 0


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
            "service_filters": [
                {
                    "field": field_2,
                    "type": "lower_than",
                    "value": "5",
                }
            ],
        },
        user,
    )

    service = ServiceHandler().create_service(service_type, **values)

    assert service.integration.id == integration.id
    assert service.table.id == table.id
    assert service.view.id == view.id
    aggregation_series = service.service_aggregation_series.all()
    assert aggregation_series.count() == 2
    assert aggregation_series[0].field_id == field.id
    assert aggregation_series[0].aggregation_type == "sum"
    assert aggregation_series[1].field_id == field_2.id
    assert aggregation_series[1].aggregation_type == "sum"
    group_bys = service.service_aggregation_group_bys.all()
    assert group_bys.count() == 1
    assert group_bys[0].field_id == field.id
    service_filters = service.service_filters.all()
    assert service_filters.count() == 1
    assert service_filters[0].field_id == field_2.id
    assert service_filters[0].type == "lower_than"
    assert service_filters[0].value["formula"] == "5"


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_field_not_in_table(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table_2)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field_2.id} is not related"
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_agg_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "avg"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The aggregation type 'avg' doesn't exist.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_series_incompatible_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} is not compatible with aggregation type",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_group_by_field_not_in_table(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table_2)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field_2.id} is not related"
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_group_by_field_not_compatible(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    table_2 = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_uuid_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used as a group by field.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_duplicate_series(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The series with the field ID {field_2.id} and aggregation type sum can only be defined once.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_max_series_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    field_4 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
                {"field_id": field_3.id, "aggregation_type": "sum"},
                {"field_id": field_4.id, "aggregation_type": "sum"},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of series exceeds the maximum allowed length of 3.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_max_group_bys_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [
                {"field_id": field.id},
                {"field_id": field_2.id},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of group by fields exceeds the maximum allowed length of 1.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_field_outside_of_series_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
            "service_aggregation_sorts": [
                {
                    "sort_on": "SERIES",
                    "reference": f"field_{field_2.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field_2.id}' cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [],
            "service_aggregation_sorts": [
                {
                    "sort_on": "PRIMARY",
                    "reference": f"field_{field_2.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field_2.id}' cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_sort_by_primary_field_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
            "service_aggregation_sorts": [
                {
                    "sort_on": "PRIMARY",
                    "reference": f"field_{field.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field.id}' cannot be used for sorting.",
    ):
        ServiceHandler().create_service(service_type, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_field_2 = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field, type="lower_than", value="5", order=1
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
                {"field_id": table_2_field_2.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    service = (
        ServiceHandler().update_service(service_type, service=service, **values).service
    )

    assert service.integration.id == table_2_integration.id
    assert service.table.id == table_2.id
    assert service.view.id == table_2_view.id
    aggregation_series = service.service_aggregation_series.all()
    assert aggregation_series.count() == 2
    assert aggregation_series[0].field_id == table_2_field.id
    assert aggregation_series[0].aggregation_type == "sum"
    assert aggregation_series[1].field_id == table_2_field_2.id
    assert aggregation_series[1].aggregation_type == "sum"
    group_bys = service.service_aggregation_group_bys.all()
    assert group_bys.count() == 1
    assert group_bys[0].field_id == table_2_field.id
    assert service.service_filters.count() == 0


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_filters(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field, type="lower_than", value="5", order=1
    )

    values = service_type.prepare_values(
        {
            "service_filters": [
                {
                    "field": field_2,
                    "type": "higher_than",
                    "value": "10",
                }
            ],
        },
        user,
        service,
    )

    service = (
        ServiceHandler().update_service(service_type, service=service, **values).service
    )

    service_filters = service.service_filters.all()
    assert service_filters.count() == 1
    assert service_filters[0].field_id == field_2.id
    assert service_filters[0].type == "higher_than"
    assert service_filters[0].value["formula"] == "10"


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_field_not_in_table(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field.id} is not related"
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_agg_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "avg"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError,
        match=f"The aggregation type 'avg' doesn't exist.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_series_incompatible_aggregation_type(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_text_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": table_2_field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {table_2_field.id} is not compatible with aggregation type",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_group_by_field_not_in_table(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    table_2_field = data_fixture.create_number_field(table=table_2)
    table_2_view = data_fixture.create_grid_view(user=user, table=table_2)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    table_2_integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "view_id": table_2_view.id,
            "table_id": table_2.id,
            "integration_id": table_2_integration.id,
            "service_aggregation_series": [
                {"field_id": table_2_field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError, match=f"The field with ID {field.id} is not related"
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_group_by_field_not_in_compatible(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_uuid_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
        },
        user,
        service,
    )

    with pytest.raises(
        ValidationError,
        match=f"The field with ID {field_2.id} cannot be used as a group by field.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_max_series_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    field_4 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
                {"field_id": field_3.id, "aggregation_type": "sum"},
                {"field_id": field_4.id, "aggregation_type": "sum"},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of series exceeds the maximum allowed length of 3.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_max_group_bys_exceeded(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [
                {"field_id": field.id},
                {"field_id": field_2.id},
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The number of group by fields exceeds the maximum allowed length of 1.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_field_outside_of_series_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": field.id}],
            "service_aggregation_sorts": [
                {
                    "sort_on": "GROUP_BY",
                    "reference": f"field_{field_2.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field_2.id}' cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [],
            "service_aggregation_sorts": [
                {
                    "sort_on": "PRIMARY",
                    "reference": f"field_{field_2.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field_2.id}' cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_sort_by_primary_field_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": view.table_id,
            "integration_id": integration.id,
            "service_aggregation_series": [],
            "service_aggregation_group_bys": [{"field_id": field_2.id}],
            "service_aggregation_sorts": [
                {
                    "sort_on": "PRIMARY",
                    "reference": f"field_{field.id}",
                    "direction": "ASC",
                },
            ],
        },
        user,
    )

    with pytest.raises(
        ValidationError,
        match=f"The reference sort 'field_{field.id}' cannot be used for sorting.",
    ):
        ServiceHandler().update_service(service_type, service=service, **values)


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_reset_after_table_change(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field.id}_sum",
        order=2,
        direction="ASC",
    )

    values = service_type.prepare_values(
        {
            "table_id": table_2.id,
        },
        user,
        service,
    )

    service = (
        ServiceHandler().update_service(service_type, service=service, **values).service
    )

    # integration is kept
    assert service.integration.id == integration.id
    # table is changed
    assert service.table.id == table_2.id
    # everything else is resetted
    assert service.view is None
    assert service.service_aggregation_series.all().count() == 0
    assert service.service_aggregation_group_bys.all().count() == 0
    assert service.service_aggregation_sorts.all().count() == 0


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 2},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}_sum": Decimal("8"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_same_agg_fields(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="min", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="max", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 1},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 1},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 1},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 1},
            {f"field_{field.id}": 1, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 3, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 9, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 10, f"field_{field_2.id}": 2},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_max": Decimal("8"),
                    f"field_{field.id}_min": Decimal("2"),
                    f"field_{field_2.id}": Decimal("1"),
                },
                {
                    f"field_{field.id}_max": Decimal("10"),
                    f"field_{field.id}_min": Decimal("1"),
                    f"field_{field_2.id}": Decimal("2"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_view(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    data_fixture.create_view_filter(
        view=view, field=field, type="lower_than", value="5"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 6},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 6},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("6"),
                    f"field_{field_2.id}_sum": Decimal("4"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_service_filters(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = None
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=service, field=field_2, type="lower_than", value="5", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 6},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 6},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("6"),
                    f"field_{field_2.id}_sum": Decimal("4"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_no_series(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = None
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == "There are no aggregation series defined."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_aggregation_type_doesnt_exist(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="invalid", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == "The the aggregation type invalid doesn't exist."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_incompatible_aggregation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="not_checked_percentage", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert (
        exc.value.args[0]
        == f"The field with ID {field.id} is not compatible with the aggregation type not_checked_percentage."
    )


@pytest.mark.django_db
def test_dispatch_grouped_aggregate_rows_service_duplicate_series(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert (
        exc.value.args[0]
        == f"The series with field ID {field.id} and aggregation type sum can only be defined once."
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_agg_series_field_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, trashed=True)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field.id} is trashed."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_group_by_field_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table, trashed=True)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == f"The field with ID {field_2.id} is trashed."


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_group_by_field_not_compatible(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_uuid_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert (
        exc.value.args[0]
        == f"The field with ID {field_2.id} cannot be used for group by."
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_table_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user, trashed=True)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, dispatch_context)
    assert exc.value.args[0] == "The selected table is trashed"


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_with_total_aggregation(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_boolean_field(table=table)
    field_2 = data_fixture.create_boolean_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="checked_percentage", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service,
        field=field_2,
        aggregation_type="not_checked_percentage",
        order=1,
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": True, f"field_{field_2.id}": True},
            {f"field_{field.id}": False, f"field_{field_2.id}": False},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_checked_percentage": 75.0,
                    f"field_{field_2.id}_not_checked_percentage": 25.0,
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_3, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": "First group",
            },
            {
                f"field_{field.id}": 4,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 6,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": "First group",
            },
            {
                f"field_{field.id}": 8,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": "Second group",
            },
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": "Third group",
            },
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": None,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("1"),
                    f"field_{field_2.id}_sum": Decimal("1"),
                    f"field_{field_3.id}": None,
                },
                {
                    f"field_{field.id}_sum": Decimal("1"),
                    f"field_{field_2.id}_sum": Decimal("1"),
                    f"field_{field_3.id}": "Third group",
                },
                {
                    f"field_{field.id}_sum": Decimal("8"),
                    f"field_{field_2.id}_sum": Decimal("6"),
                    f"field_{field_3.id}": "First group",
                },
                {
                    f"field_{field.id}_sum": Decimal("22"),
                    f"field_{field_2.id}_sum": Decimal("7"),
                    f"field_{field_3.id}": "Second group",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by_single_select(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_single_select_field(table=table)
    option_a = data_fixture.create_select_option(
        field=field_2, value="Category A", color="red"
    )
    option_b = data_fixture.create_select_option(
        field=field_2, value="Category B", color="blue"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": option_a.id},
            {f"field_{field.id}": 4, f"field_{field_2.id}": option_a.id},
            {f"field_{field.id}": 8, f"field_{field_2.id}": option_b.id},
            {f"field_{field.id}": 1, f"field_{field_2.id}": None},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": unordered(
                [
                    {
                        f"{field.name} sum": Decimal("1"),
                        field_2.name: None,
                    },
                    {
                        f"{field.name} sum": Decimal("6"),
                        field_2.name: {
                            "id": option_a.id,
                            "value": "Category A",
                            "color": "red",
                        },
                    },
                    {
                        f"{field.name} sum": Decimal("8"),
                        field_2.name: {
                            "id": option_b.id,
                            "value": "Category B",
                            "color": "blue",
                        },
                    },
                ]
            ),
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_other_bucket_uses_raw_group_values(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 2
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_single_select_field(
        table=table, name="Category"
    )
    option_a = data_fixture.create_select_option(
        field=group_by_field, value="Category A", color="red"
    )
    option_b = data_fixture.create_select_option(
        field=group_by_field, value="Category B", color="blue"
    )
    option_c = data_fixture.create_select_option(
        field=group_by_field, value="Category C", color="green"
    )
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=group_by_field, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{group_by_field.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 10, f"field_{group_by_field.id}": option_a.id},
            {f"field_{field.id}": 20, f"field_{group_by_field.id}": option_b.id},
            {f"field_{field.id}": 30, f"field_{group_by_field.id}": option_c.id},
        ],
    )

    result = ServiceHandler().dispatch_service(service, FakeDispatchContext())

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    "Amount sum": Decimal("10"),
                    "Category": {
                        "id": option_a.id,
                        "value": "Category A",
                        "color": "red",
                    },
                },
                {
                    "Amount sum": Decimal("50"),
                    "Category": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by_id(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{field.id}": 2, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 4, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 6, f"field_{field_2.id}": 2},
            {f"field_{field.id}": 8, f"field_{field_2.id}": 2},
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": unordered(
                [
                    {
                        f"field_{field.id}": Decimal("2"),
                        f"field_{field.id}_sum": Decimal("2"),
                        f"field_{field_2.id}_sum": Decimal("2"),
                        "id": 1,
                    },
                    {
                        f"field_{field.id}": Decimal("4"),
                        f"field_{field.id}_sum": Decimal("4"),
                        f"field_{field_2.id}_sum": Decimal("2"),
                        "id": 2,
                    },
                    {
                        f"field_{field.id}": Decimal("6"),
                        f"field_{field.id}_sum": Decimal("6"),
                        f"field_{field_2.id}_sum": Decimal("2"),
                        "id": 3,
                    },
                    {
                        f"field_{field.id}": Decimal("8"),
                        f"field_{field.id}_sum": Decimal("8"),
                        f"field_{field_2.id}_sum": Decimal("2"),
                        "id": 4,
                    },
                ]
            ),
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_3.id}_sum",
        order=1,
        direction="ASC",
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_2.id}_sum",
        order=2,
        direction="DESC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}": Decimal("30"),
                    f"field_{field.id}_sum": Decimal("90"),
                    f"field_{field_2.id}_sum": Decimal("9"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                },
                {
                    f"field_{field.id}": Decimal("20"),
                    f"field_{field.id}_sum": Decimal("60"),
                    f"field_{field_2.id}_sum": Decimal("6"),
                    f"field_{field_3.id}_sum": Decimal("6"),
                },
                {
                    f"field_{field.id}": Decimal("10"),
                    f"field_{field.id}_sum": Decimal("30"),
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("6"),
                },
                {
                    f"field_{field.id}": None,
                    f"field_{field.id}_sum": None,
                    f"field_{field_2.id}_sum": Decimal("100"),
                    f"field_{field_3.id}_sum": Decimal("100"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by_row_id(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_3.id}_sum",
        order=1,
        direction="ASC",
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_2.id}_sum",
        order=2,
        direction="DESC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}": None,
                    f"field_{field.id}_sum": None,
                    f"field_{field_2.id}_sum": Decimal("5"),
                    f"field_{field_3.id}_sum": Decimal("1"),
                    "id": 5,
                },
                {
                    f"field_{field.id}": Decimal("3"),
                    f"field_{field.id}_sum": Decimal("3"),
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("2"),
                    "id": 4,
                },
                {
                    f"field_{field.id}": Decimal("3"),
                    f"field_{field.id}_sum": Decimal("3"),
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                    "id": 3,
                },
                {
                    f"field_{field.id}": Decimal("2"),
                    f"field_{field.id}_sum": Decimal("2"),
                    f"field_{field_2.id}_sum": Decimal("2"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                    "id": 2,
                },
                {
                    f"field_{field.id}": Decimal("1"),
                    f"field_{field.id}_sum": Decimal("1"),
                    f"field_{field_2.id}_sum": Decimal("1"),
                    f"field_{field_3.id}_sum": Decimal("4"),
                    "id": 1,
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_without_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field.id}_sum",
        order=1,
        direction="ASC",
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_2.id}_sum",
        order=2,
        direction="DESC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 1,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": 2,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": 3,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("9"),
                    f"field_{field_2.id}_sum": Decimal("14"),
                    f"field_{field_3.id}_sum": Decimal("13"),
                }
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_group_by_field(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}": None,
                    f"field_{field_2.id}_sum": Decimal("100"),
                    f"field_{field_3.id}_sum": Decimal("100"),
                },
                {
                    f"field_{field.id}": Decimal("10"),
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("6"),
                },
                {
                    f"field_{field.id}": Decimal("20"),
                    f"field_{field_2.id}_sum": Decimal("6"),
                    f"field_{field_3.id}_sum": Decimal("6"),
                },
                {
                    f"field_{field.id}": Decimal("30"),
                    f"field_{field_2.id}_sum": Decimal("9"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_group_by_row_id(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": "A",
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 4,
            },
            {
                f"field_{field.id}": "H",
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": "I",
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 3,
            },
            {
                f"field_{field.id}": "B",
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": "",
                f"field_{field_2.id}": 5,
                f"field_{field_3.id}": 1,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}": "",
                    f"field_{field_2.id}_sum": Decimal("5"),
                    f"field_{field_3.id}_sum": Decimal("1"),
                    "id": 5,
                },
                {
                    f"field_{field.id}": "A",
                    f"field_{field_2.id}_sum": Decimal("1"),
                    f"field_{field_3.id}_sum": Decimal("4"),
                    "id": 1,
                },
                {
                    f"field_{field.id}": "B",
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("2"),
                    "id": 4,
                },
                {
                    f"field_{field.id}": "H",
                    f"field_{field_2.id}_sum": Decimal("2"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                    "id": 2,
                },
                {
                    f"field_{field.id}": "I",
                    f"field_{field_2.id}_sum": Decimal("3"),
                    f"field_{field_3.id}_sum": Decimal("3"),
                    "id": 3,
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_field_outside_series_or_group_bys(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException,
        match=f"The sort reference 'field_{field_2.id}' cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_primary_field_no_group_by(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="PRIMARY",
        reference=f"field_{field.id}",
        order=2,
        direction="ASC",
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException,
        match=f"The sort reference 'field_{field.id}' cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_primary_field_group_by_another_field(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, primary=True)
    field_2 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="PRIMARY",
        reference=f"field_{field.id}",
        order=2,
        direction="ASC",
    )

    dispatch_context = FakeDispatchContext()

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException,
        match=f"The sort reference 'field_{field.id}' cannot be used for sorting.",
    ):
        ServiceHandler().dispatch_service(service, dispatch_context)


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_sort_by_series_with_group_by_ignore_view_sort(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    # these sorts will be ignored
    data_fixture.create_view_sort(view=view, field=field_3, order="ASC")
    data_fixture.create_view_sort(view=view, field=field_2, order="DESC")
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="sum", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            # group 1
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": 1,
                f"field_{field_3.id}": 2,
            },
            # group 2
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 2,
                f"field_{field_3.id}": 2,
            },
            # group 3
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": 3,
                f"field_{field_3.id}": 1,
            },
            # group 4
            {
                f"field_{field.id}": None,
                f"field_{field_2.id}": 100,
                f"field_{field_3.id}": 100,
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": unordered(
                [
                    {
                        f"field_{field.id}": None,
                        f"field_{field.id}_sum": None,
                        f"field_{field_2.id}_sum": Decimal("100"),
                        f"field_{field_3.id}_sum": Decimal("100"),
                    },
                    {
                        f"field_{field.id}": Decimal("10"),
                        f"field_{field.id}_sum": Decimal("30"),
                        f"field_{field_2.id}_sum": Decimal("3"),
                        f"field_{field_3.id}_sum": Decimal("6"),
                    },
                    {
                        f"field_{field.id}": Decimal("30"),
                        f"field_{field.id}_sum": Decimal("90"),
                        f"field_{field_2.id}_sum": Decimal("9"),
                        f"field_{field_3.id}_sum": Decimal("3"),
                    },
                    {
                        f"field_{field.id}": Decimal("20"),
                        f"field_{field.id}_sum": Decimal("60"),
                        f"field_{field_2.id}_sum": Decimal("6"),
                        f"field_{field_3.id}_sum": Decimal("6"),
                    },
                ]
            ),
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_group_by_field(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 40,
                f"field_{field_2.id}": "Z",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": 50,
                f"field_{field_2.id}": "M",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("10"),
                    f"field_{field_2.id}": "A",
                },
                {
                    f"field_{field.id}_sum": Decimal("60"),
                    f"field_{field_2.id}": "H",
                },
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}": "K",
                },
                {
                    f"field_{field.id}_sum": Decimal("120"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_series(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field.id}_sum",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 40,
                f"field_{field_2.id}": "Z",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
            {
                f"field_{field.id}": 50,
                f"field_{field_2.id}": "M",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("10"),
                    f"field_{field_2.id}": "A",
                },
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}": "K",
                },
                {
                    f"field_{field.id}_sum": Decimal("30"),
                    f"field_{field_2.id}": "L",
                },
                {
                    f"field_{field.id}_sum": Decimal("150"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_max_buckets_sort_on_primary_field(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table, primary=True)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{field.id}": 40,
                    f"field_{field_2.id}": "Z",
                },
                {
                    f"field_{field.id}": 20,
                    f"field_{field_2.id}": "K",
                },
                {
                    f"field_{field.id}": 30,
                    f"field_{field_2.id}": "L",
                },
                {
                    f"field_{field.id}": 10,
                    f"field_{field_2.id}": "A",
                },
                {
                    f"field_{field.id}": 60,
                    f"field_{field_2.id}": "H",
                },
                {
                    f"field_{field.id}": 50,
                    f"field_{field_2.id}": "M",
                },
            ],
        )
        .created_rows
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("10"),
                    f"field_{field_2.id}": "A",
                    "id": rows[3].id,
                },
                {
                    f"field_{field.id}_sum": Decimal("60"),
                    f"field_{field_2.id}": "H",
                    "id": rows[4].id,
                },
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}": "K",
                    "id": rows[1].id,
                },
                {
                    f"field_{field.id}_sum": Decimal("120"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                    "id": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_within_max_buckets(
    data_fixture, settings
):
    """OTHER bucket is not created"""

    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("10"),
                    f"field_{field_2.id}": "A",
                },
                {
                    f"field_{field.id}_sum": Decimal("60"),
                    f"field_{field_2.id}": "H",
                },
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}": "K",
                },
                {
                    f"field_{field.id}_sum": Decimal("30"),
                    f"field_{field_2.id}": "L",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_1_bucket(data_fixture, settings):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 1
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("20"),
                    f"field_{field_2.id}": "K",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_1_other_bucket(data_fixture, settings):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 1
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="ASC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("120"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_not_within_max_buckets_no_sort(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 2
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("30"),
                    f"field_{field_2.id}": "L",
                },
                {
                    f"field_{field.id}_sum": Decimal("90"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_not_within_max_buckets_sort_group_by(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 2
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_2, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=f"field_{field_2.id}",
        order=1,
        direction="DESC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": "K",
            },
            {
                f"field_{field.id}": 30,
                f"field_{field_2.id}": "L",
            },
            {
                f"field_{field.id}": 10,
                f"field_{field_2.id}": "A",
            },
            {
                f"field_{field.id}": 60,
                f"field_{field_2.id}": "H",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("30"),
                    f"field_{field_2.id}": "L",
                },
                {
                    f"field_{field.id}_sum": Decimal("90"),
                    f"field_{field_2.id}": "OTHER_VALUES",
                },
            ],
        },
    )


# TODO: different group by field types


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_not_within_max_buckets_sort_on_series(
    data_fixture, settings
):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 4
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_3, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field.id}_sum",
        order=1,
        direction="DESC",
    )

    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 10,
                f"field_{field_3.id}": "T",
            },
            {
                f"field_{field.id}": 31,
                f"field_{field_2.id}": 30,
                f"field_{field_3.id}": "L",
            },
            {
                f"field_{field.id}": 32,
                f"field_{field_2.id}": 40,
                f"field_{field_3.id}": "A",
            },
            {
                f"field_{field.id}": 32,
                f"field_{field_2.id}": 30,
                f"field_{field_3.id}": "H",
            },
            {
                f"field_{field.id}": 20,
                f"field_{field_2.id}": 20,
                f"field_{field_3.id}": "B",
            },
            {
                f"field_{field.id}": 19,
                f"field_{field_2.id}": 20,
                f"field_{field_3.id}": "K",
            },
        ],
    )

    dispatch_context = FakeDispatchContext()

    result = ServiceHandler().dispatch_service(service, dispatch_context)

    assert without_grouped_row_ids(result.data) == expected_grouped_dispatch_data(
        service,
        {
            "has_next_page": False,
            "results": [
                {
                    f"field_{field.id}_sum": Decimal("59"),
                    f"field_{field_2.id}_sum": Decimal("50"),
                    f"field_{field_3.id}": "OTHER_VALUES",
                },
                {
                    f"field_{field.id}_sum": Decimal("32"),
                    f"field_{field_2.id}_sum": Decimal("30"),
                    f"field_{field_3.id}": "H",
                },
                {
                    f"field_{field.id}_sum": Decimal("32"),
                    f"field_{field_2.id}_sum": Decimal("40"),
                    f"field_{field_3.id}": "A",
                },
                {
                    f"field_{field.id}_sum": Decimal("31"),
                    f"field_{field_2.id}_sum": Decimal("30"),
                    f"field_{field_3.id}": "L",
                },
            ],
        },
    )


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_export_serialized(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        view=view,
    )
    series_1 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    series_2 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="min", order=2
    )
    series_3 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_3, aggregation_type="max", order=3
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field_3, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field.id}_sum",
        order=1,
        direction="ASC",
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"field_{field_2.id}_min",
        order=1,
        direction="ASC",
    )

    result = LocalBaserowGroupedAggregateRowsUserServiceType().export_serialized(
        service, import_export_config=None, files_zip=None, storage=None, cache=None
    )

    assert result == {
        "filter_type": "AND",
        "filters": [],
        "filter_groups": [],
        "id": service.id,
        "integration_id": service.integration.id,
        "sample_data": None,
        "service_aggregation_group_bys": [
            {"field_id": field_3.id},
        ],
        "service_aggregation_series": [
            {"aggregation_type": "sum", "field_id": field.id, "id": series_1.id},
            {"aggregation_type": "min", "field_id": field_2.id, "id": series_2.id},
            {"aggregation_type": "max", "field_id": field_3.id, "id": series_3.id},
        ],
        "service_aggregation_sorts": [
            {
                "direction": "ASC",
                "reference": f"field_{field.id}_sum",
                "sort_on": "SERIES",
            },
            {
                "direction": "ASC",
                "reference": f"field_{field_2.id}_min",
                "sort_on": "SERIES",
            },
        ],
        "table_id": table.id,
        "type": "local_baserow_grouped_aggregate_rows",
        "view_id": view.id,
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_import_serialized(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table)
    field_2 = data_fixture.create_number_field(table=table)
    field_3 = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )

    serialized_service = {
        "filter_type": "AND",
        "filters": [],
        "filter_groups": [],
        "id": 999,
        "integration_id": integration.id,
        "service_aggregation_group_bys": [
            {"field_id": field_3.id},
        ],
        "service_aggregation_series": [
            {"aggregation_type": "sum", "field_id": field.id},
            {"aggregation_type": "min", "field_id": field_2.id},
            {"aggregation_type": "max", "field_id": field_3.id},
        ],
        "service_aggregation_sorts": [
            {
                "direction": "ASC",
                "reference": f"field_{field.id}_sum",
                "sort_on": "SERIES",
            },
            {
                "direction": "DESC",
                "reference": f"field_{field_2.id}_min",
                "sort_on": "SERIES",
            },
        ],
        "table_id": table.id,
        "type": "local_baserow_grouped_aggregate_rows",
        "view_id": view.id,
    }
    id_mapping = {}

    instance = LocalBaserowGroupedAggregateRowsUserServiceType().import_serialized(
        parent=integration,
        serialized_values=serialized_service,
        id_mapping=id_mapping,
        import_formula=Mock(),
    )

    assert instance.content_type == ContentType.objects.get_for_model(
        LocalBaserowGroupedAggregateRows
    )
    assert instance.filter_type == "AND"
    assert instance.service_filters.count() == 0
    assert instance.id != 999
    assert instance.integration_id == integration.id
    assert instance.table_id == table.id
    assert instance.view_id == view.id

    series = instance.service_aggregation_series.all()
    assert series.count() == 3
    assert series[0].aggregation_type == "sum"
    assert series[0].field_id == field.id
    assert series[1].aggregation_type == "min"
    assert series[1].field_id == field_2.id
    assert series[2].aggregation_type == "max"
    assert series[2].field_id == field_3.id

    group_bys = instance.service_aggregation_group_bys.all()
    assert group_bys.count() == 1
    assert group_bys[0].field_id == field_3.id

    sorts = instance.service_aggregation_sorts.all()
    assert sorts.count() == 2
    assert sorts[0].direction == "ASC"
    assert sorts[0].sort_on == "SERIES"
    assert sorts[0].reference == f"field_{field.id}_sum"
    assert sorts[1].direction == "DESC"
    assert sorts[1].sort_on == "SERIES"
    assert sorts[1].reference == f"field_{field_2.id}_min"

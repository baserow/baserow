from decimal import Decimal
from unittest.mock import Mock

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext

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
from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_premium.api.integrations.local_baserow.serializers import (
    LocalBaserowTableServiceAggregationGroupBySerializer,
    LocalBaserowTableServiceAggregationSeriesSerializer,
)
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
@pytest.mark.parametrize("group_name", ["Amount sum", "id"])
@pytest.mark.parametrize("group_by_row_id", [False, True])
def test_grouped_aggregate_rows_result_name_collisions(
    data_fixture, group_name, group_by_row_id
):
    """Colliding labels remain distinct in results, formulas and restricted schemas."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    group_field = data_fixture.create_text_field(
        table=table, name=group_name, primary=group_by_row_id
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        integration=data_fixture.create_local_baserow_integration(
            application=data_fixture.create_builder_application(
                workspace=table.database.workspace
            ),
            user=user,
        ),
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None if group_by_row_id else group_field, order=0
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[{group_field.db_column: "Fruit", amount.db_column: 10}],
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    group_key = group_field.db_column
    sum_key = f"{amount.db_column}_sum"
    group_result_name = f"{group_name} [{group_key}]"
    sum_result_name = (
        f"Amount sum [{sum_key}]" if group_name == "Amount sum" else "Amount sum"
    )

    result = ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
    assert result == {
        "has_next_page": False,
        "results": [
            {"id": "Fruit", group_result_name: "Fruit", sum_result_name: Decimal("10")}
        ],
    }
    expected_names = {
        "id": "id",
        group_key: group_result_name,
        sum_key: sum_result_name,
    }
    expected_values = {"id": "Fruit", group_key: "Fruit", sum_key: Decimal("10")}
    full_schema = service_type.generate_schema(service)["items"]["properties"]
    assert set(full_schema) == set(expected_names)
    assert full_schema[group_key]["title"] == group_name
    for key, result_name in expected_names.items():
        path = service_type.prepare_value_path(service, [key])
        assert path == [result_name]
        assert result["results"][0][path[0]] == expected_values[key]
        restricted_schema = service_type.generate_schema(service, allowed_fields=[key])
        assert restricted_schema["items"]["properties"] == {key: full_schema[key]}
        sanitized = service_type.sanitize_result(service, result, [key])
        assert sanitized == {
            "has_next_page": False,
            "results": [{result_name: result["results"][0][result_name]}],
        }


def test_grouped_aggregate_result_names_avoid_generated_suffix_collisions():
    """Generated suffixes never overwrite real labels or depend on series order."""

    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    titles = {
        "id": "Id",
        "field_1": "Amount sum",
        "field_2_sum": "Amount sum",
        "field_3": "Amount sum [field_1]",
        "field_4": "Amount sum [field_1] (2)",
    }
    mappings = []
    for keys in (list(titles), list(reversed(titles))):
        properties = {key: {"title": titles[key]} for key in keys}
        service_type._disambiguate_result_property_names(properties)
        mappings.append(
            {
                key: prop.get("metadata", {}).get("result_name", titles[key])
                for key, prop in properties.items()
            }
        )
    assert (
        mappings[0]
        == mappings[1]
        == {
            "id": "Id",
            "field_1": "Amount sum [field_1] (3)",
            "field_2_sum": "Amount sum [field_2_sum]",
            "field_3": "Amount sum [field_1]",
            "field_4": "Amount sum [field_1] (2)",
        }
    )


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
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_builder_application(
            workspace=table.database.workspace
        ),
        user=user,
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


def test_grouped_readable_ids_disambiguate_duplicate_and_suffix_labels():
    """Duplicate labels get readable suffixes which cannot overwrite real labels."""

    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    rows = [
        {"id": name} for name in ["Sales", "Sales", "Sales (1)", "-", "-", "- (1)", "0"]
    ]
    service_type._set_unique_record_ids(rows)
    assert [row["id"] for row in rows] == [
        "Sales (2)",
        "Sales (3)",
        "Sales (1)",
        "- (2)",
        "- (3)",
        "- (1)",
        "0",
    ]


def test_grouped_record_names_do_not_dispatch(mocker):
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    dispatch = mocker.patch.object(service_type, "dispatch_data")
    names = ["Sales (2)", "-", "OTHER_VALUES (2)"]
    assert service_type.get_record_names(Mock(), names, FakeDispatchContext()) == {
        name: name for name in names
    }
    dispatch.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize("row_grouping", [False, True])
def test_grouped_readable_ids_select_one_group(data_fixture, row_grouping):
    """Empty and duplicate labels each select exactly one returned group."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    category = data_fixture.create_text_field(
        table=table, name="Category", primary=True
    )
    amount = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        integration=data_fixture.create_local_baserow_integration(
            application=data_fixture.create_builder_application(
                workspace=table.database.workspace
            ),
            user=user,
        ),
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None if row_grouping else category, order=0
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {category.db_column: name, amount.db_column: index}
            for index, name in enumerate(
                ["Sales", "Sales", "Sales (1)", "", "-", "0"], start=1
            )
        ],
    )
    service_type = service.get_type()
    rows = service_type.dispatch_data(service, {}, FakeDispatchContext())["data"][
        "results"
    ]
    assert any(row["Category"] == "" for row in rows)
    assert all(row["id"] for row in rows)
    assert len(rows) == (6 if row_grouping else 5)
    assert len({row["id"] for row in rows}) == len(rows)
    assert "0" in {row["id"] for row in rows}
    for row in rows:
        selected = service_type.dispatch_data(
            service, {}, FakeDispatchContext(only_record_id=row["id"])
        )["data"]["results"]
        assert selected == [row]


@pytest.mark.django_db
def test_grouped_readable_ids_distinguish_overflow(data_fixture, settings):
    """The overflow label cannot collide with a real OTHER_VALUES group."""

    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 3
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    category = data_fixture.create_text_field(table=table, name="Category")
    amount = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        integration=data_fixture.create_local_baserow_integration(
            application=data_fixture.create_builder_application(
                workspace=table.database.workspace
            ),
            user=user,
        ),
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=category, order=0
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=category.db_column,
        direction="ASC",
        order=0,
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {category.db_column: name, amount.db_column: index}
            for index, name in enumerate(
                ["OTHER_VALUES", "OTHER_VALUES (1)", "Z", "ZZ"], start=1
            )
        ],
    )
    rows = service.get_type().dispatch_data(service, {}, FakeDispatchContext())["data"][
        "results"
    ]
    assert {row["id"]: row["Amount sum"] for row in rows} == {
        "OTHER_VALUES (2)": 1,
        "OTHER_VALUES (1)": 2,
        "OTHER_VALUES (3)": 7,
    }


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
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_builder_application(
            workspace=table.database.workspace
        ),
        user=user,
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
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_builder_application(
            workspace=table.database.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
@pytest.mark.parametrize(
    "field_factory", ["create_date_field", "create_duration_field"]
)
def test_create_grouped_aggregate_rows_service_group_by_database_compatible_field(
    data_fixture, field_factory
):
    """Fields accepted by Database grouping are accepted by grouped aggregations."""
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    aggregation_field = data_fixture.create_number_field(table=table)
    group_by_field = getattr(data_fixture, field_factory)(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    values = service_type.prepare_values(
        {
            "view_id": view.id,
            "table_id": table.id,
            "integration_id": integration.id,
            "service_aggregation_series": [
                {"field_id": aggregation_field.id, "aggregation_type": "sum"},
            ],
            "service_aggregation_group_bys": [{"field_id": group_by_field.id}],
        },
        user,
    )

    service = ServiceHandler().create_service(service_type, **values)

    assert service.service_aggregation_group_bys.get().field_id == group_by_field.id


@pytest.mark.django_db
def test_create_grouped_aggregate_rows_service_group_by_field_not_compatible(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
@pytest.mark.parametrize(
    "change,remaining_sort_indexes",
    [
        ("remove_series", [1, 2]),
        ("change_series_field", [1, 2]),
        ("change_aggregation", [1, 2]),
        ("remove_group", [0, 1]),
        ("change_group", [0, 1]),
        ("to_row_id_group", [0, 1]),
        ("from_row_id_group", [0, 1]),
        ("unchanged", [0, 1, 2]),
    ],
)
def test_update_grouped_aggregate_rows_removes_obsolete_sorts(
    data_fixture, change, remaining_sort_indexes
):
    """Configuration edits drop obsolete sorts while preserving valid sorts in order."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    primary = data_fixture.create_text_field(table=table, primary=True)
    amount = data_fixture.create_number_field(table=table)
    other_amount = data_fixture.create_number_field(table=table)
    replacement_amount = data_fixture.create_number_field(table=table)
    category = data_fixture.create_text_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_builder_application(
            workspace=table.database.workspace
        ),
        user=user,
    )
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, integration=integration, table=table
    )
    series = [
        LocalBaserowTableServiceAggregationSeries.objects.create(
            service=service, field=field, aggregation_type="sum", order=index
        )
        for index, field in enumerate([amount, other_amount])
    ]
    row_id_group = change == "from_row_id_group"
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None if row_id_group else category, order=0
    )
    sorts = [
        LocalBaserowTableServiceAggregationSortBy.objects.create(
            service=service,
            sort_on=sort_on,
            reference=reference,
            direction=direction,
            order=index,
        )
        for index, (sort_on, reference, direction) in enumerate(
            [
                ("SERIES", f"field_{amount.id}_sum", "ASC"),
                ("SERIES", f"field_{other_amount.id}_sum", "DESC"),
                (
                    "GROUP_BY",
                    f"field_{primary.id if row_id_group else category.id}",
                    "ASC",
                ),
            ]
        )
    ]
    series_values = [
        {"id": item.id, "field_id": item.field_id, "aggregation_type": "sum"}
        for item in series
    ]
    if change == "remove_series":
        series_values.pop(0)
    elif change == "change_series_field":
        series_values[0]["field_id"] = replacement_amount.id
    elif change == "change_aggregation":
        series_values[0]["aggregation_type"] = "min"

    if change in {
        "remove_series",
        "change_series_field",
        "change_aggregation",
        "unchanged",
    }:
        values = {"service_aggregation_series": series_values}
    else:
        group_values = {
            "remove_group": [],
            "change_group": [{"field_id": primary.id}],
            "to_row_id_group": [{"field_id": None}],
            "from_row_id_group": [{"field_id": category.id}],
        }
        values = {"service_aggregation_group_bys": group_values[change]}

    # Exercise the prefetched instance used by real service update endpoints.
    service = service_type.enhance_queryset(
        LocalBaserowGroupedAggregateRows.objects.all()
    ).get(pk=service.pk)
    service = ServiceHandler().update_service(service_type, service, **values).service

    assert [
        (sort.id, sort.reference, sort.direction, sort.order)
        for sort in service.service_aggregation_sorts.all()
    ] == [
        (
            sorts[index].id,
            sorts[index].reference,
            sorts[index].direction,
            sorts[index].order,
        )
        for index in remaining_sort_indexes
    ]
    result = ServiceHandler().dispatch_service(service, FakeDispatchContext())
    assert "results" in result.data


@pytest.mark.django_db
def test_update_grouped_aggregate_rows_service_filters(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(user=user, table=table)
    table_2 = data_fixture.create_database_table(database=table.database, user=user)
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
@pytest.mark.parametrize(
    "field_type",
    ["multiple_select", "link_row", "multiple_collaborators"],
)
@pytest.mark.parametrize("bucket_limit", [100, 2])
def test_grouped_aggregate_rows_service_dispatch_group_by_multiple_relations(
    data_fixture,
    settings,
    django_assert_num_queries,
    field_type,
    bucket_limit,
):
    """Collection buckets retain labels, empty values, and overflow aggregation."""
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = bucket_limit
    user = data_fixture.create_user(first_name="Alice")
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    amount = data_fixture.create_number_field(table=table, name="Amount")
    if field_type == "multiple_select":
        group_field = data_fixture.create_multiple_select_field(
            table=table, name="Category", primary=True
        )
        options = [
            data_fixture.create_select_option(field=group_field, value=name)
            for name in ["Alpha", "Beta"]
        ]
        values = [option.id for option in options]
        labels = ["Alpha", "Beta"]
    elif field_type == "link_row":
        linked_table = data_fixture.create_database_table(user=user)
        primary = data_fixture.create_text_field(table=linked_table, primary=True)
        linked_model = linked_table.get_model()
        values = [
            linked_model.objects.create(**{primary.db_column: name}).id
            for name in ["Alpha", "Beta"]
        ]
        group_field = data_fixture.create_link_row_field(
            table=table, link_row_table=linked_table, name="Category", primary=True
        )
        labels = ["Alpha", "Beta"]
    else:
        other_user = data_fixture.create_user(
            first_name="Bob", workspace=table.database.workspace
        )
        group_field = data_fixture.create_multiple_collaborators_field(
            table=table, name="Category", primary=True
        )
        values = [{"id": person.id} for person in [user, other_user]]
        labels = [person.first_name for person in [user, other_user]]

    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, integration=integration, table=table
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"{amount.db_column}_sum",
        order=1,
        direction="ASC",
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {amount.db_column: 1, group_field.db_column: []},
            {amount.db_column: 2, group_field.db_column: values[:1]},
            {amount.db_column: 4, group_field.db_column: values},
        ],
    )

    # Both labels and response values reuse the same single lookup for all buckets.
    model = table.get_model()
    field_object = model.get_field_object(group_field.db_column)
    service_type = service.get_type()
    serializer = field_object["type"].get_response_serializer_field(
        field_object["field"]
    )
    expected_ids = [
        value["id"] if isinstance(value, dict) else value for value in values
    ]
    raw_values = [None, *expected_ids, expected_ids, "OTHER_VALUES"]
    with django_assert_num_queries(1):
        resolve = service_type._get_related_result_values(
            field_object,
            model,
            [{group_field.db_column: value} for value in raw_values] * 10,
        )
    with django_assert_num_queries(0):
        assert [
            service_type._get_human_readable_result_value(value, field_object, resolve)
            for value in raw_values
        ] == ["", *labels, ", ".join(labels), "OTHER_VALUES"]
        assert [
            item["id"] for item in serializer.to_representation(resolve(expected_ids))
        ] == expected_ids

    result = ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
    assert result["has_next_page"] is False
    rows = result["results"]
    if field_type == "multiple_collaborators":
        assert user.email not in str(result)
        assert other_user.email not in str(result)
        assert group_field.get_type().get_human_readable_value(
            resolve(expected_ids), field_object
        ) == ", ".join(
            f"{person.first_name} <{person.email}>" for person in [user, other_user]
        )
    assert rows[0] == {"id": "-", "Amount sum": Decimal(1), "Category": []}
    if bucket_limit == 2:
        assert rows[1] == {
            "id": "OTHER_VALUES",
            "Amount sum": Decimal(6),
            "Category": "OTHER_VALUES",
        }
        assert len(rows) == 2
    else:
        assert [row["id"] for row in rows] == ["-", labels[0], ", ".join(labels)]
        assert [row["Amount sum"] for row in rows] == [1, 2, 4]
        assert [[item["id"] for item in row["Category"] or []] for row in rows] == [
            [],
            expected_ids[:1],
            expected_ids,
        ]
        service.service_aggregation_sorts.update(
            sort_on="GROUP_BY", reference=group_field.db_column, direction="ASC"
        )
        sorted_result = (
            ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
        )
        assert sorted_result == result


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["complete", "individual"])
@pytest.mark.parametrize("bucket_limit", [100, 2, 3])
@pytest.mark.parametrize("primary", [False, True])
def test_grouped_aggregate_rows_multiple_select_modes(
    data_fixture, settings, mode, bucket_limit, primary
):
    """Merge equal selections or shared options, including overlapping overflow buckets."""
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 100
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    amount = data_fixture.create_number_field(table=table, name="Amount")
    category = data_fixture.create_multiple_select_field(
        table=table, name="Category", primary=primary
    )
    alpha = data_fixture.create_select_option(field=category, value="Alpha")
    beta = data_fixture.create_select_option(field=category, value="Beta")
    gamma = data_fixture.create_select_option(field=category, value="Gamma")
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
        bucket_limit=bucket_limit,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="average", order=2
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=category, aggregation_type="count", order=3
    )
    serializer = LocalBaserowTableServiceAggregationGroupBySerializer(
        data={"field_id": category.id, "mode": mode}
    )
    assert serializer.is_valid(), serializer.errors
    service.get_type()._update_service_aggregation_group_bys(
        service, [serializer.validated_data]
    )
    group_by = service.service_aggregation_group_bys.get()
    assert (
        LocalBaserowTableServiceAggregationGroupBySerializer(group_by).data["mode"]
        == mode
    )

    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"{amount.db_column}_sum",
        direction="ASC",
        order=1,
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {amount.db_column: value, category.db_column: options}
            for value, options in [
                (1, []),
                (2, [alpha.id]),
                (4, [alpha.id, beta.id]),
                (8, [beta.id, alpha.id]),
                (16, [alpha.id]),
                (32, [beta.id]),
                (64, [gamma.id]),
            ]
        ],
    )
    result = ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
    assert result["results"][0]["Category count"] == 1
    if mode == "complete":
        expected = [
            ("-", [], 1, 1),
            ("Alpha, Beta", [alpha.id, beta.id], 12, 6),
            ("Alpha", [alpha.id], 18, 9),
            ("Beta", [beta.id], 32, 32),
            ("Gamma", [gamma.id], 64, 64),
        ]
        overflow = {2: (126, Decimal(126) / 6), 3: (114, Decimal(114) / 4)}
    else:
        expected = [
            ("-", None, 1, 1),
            ("Alpha", [alpha.id], 30, Decimal("7.5")),
            ("Beta", [beta.id], 44, Decimal(44) / 3),
            ("Gamma", [gamma.id], 64, 64),
        ]
        overflow = {2: (138, Decimal(138) / 8), 3: (108, Decimal(108) / 4)}
    if len(expected) > bucket_limit:
        total, average = overflow[bucket_limit]
        expected = expected[: bucket_limit - 1] + [
            ("OTHER_VALUES", "OTHER_VALUES", total, average)
        ]
    actual = [
        (
            row["id"],
            [item["id"] for item in row["Category"]]
            if isinstance(row["Category"], list)
            else row["Category"],
            row["Amount sum"],
            row["Amount average"],
        )
        for row in result["results"]
    ]
    assert [(label, options, total) for label, options, total, _ in actual] == [
        (label, options, total) for label, options, total, _ in expected
    ]
    assert [average for _, _, _, average in actual] == pytest.approx(
        [average for _, _, _, average in expected]
    )
    if bucket_limit == 100:
        for direction in ["ASC", "DESC"]:
            service.service_aggregation_sorts.update(
                sort_on="GROUP_BY", reference=category.db_column, direction=direction
            )
            result = (
                ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
            )
            expected_labels = (
                ["-", "Alpha", "Alpha, Beta", "Beta", "Gamma"]
                if mode == "complete"
                else ["-", "Alpha", "Beta", "Gamma"]
            )
            if direction == "DESC":
                expected_labels.reverse()
            assert [row["id"] for row in result["results"]] == expected_labels


@pytest.mark.django_db
def test_grouped_aggregate_rows_export_prepared_values_preserves_group_by_mode(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    category = data_fixture.create_multiple_select_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, integration=integration, table=table
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service,
        field=category,
        mode="individual",
        order=1,
    )

    assert service.get_type().export_prepared_values(service)[
        "service_aggregation_group_bys"
    ] == [{"field_id": category.id, "mode": "individual"}]


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_dispatch_group_by_single_select(
    data_fixture,
):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
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
        "bucket_limit": None,
        "filter_type": "AND",
        "filters": [],
        "filter_groups": [],
        "id": service.id,
        "integration_id": service.integration.id,
        "sample_data": None,
        "service_aggregation_group_bys": [
            {"field_id": field_3.id, "mode": "complete"},
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
@pytest.mark.parametrize("mode", [None, "complete", "individual"])
def test_grouped_aggregate_rows_service_import_serialized(data_fixture, mode):
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
    if mode is not None:
        serialized_service["service_aggregation_group_bys"][0]["mode"] = mode
    serialized_service["bucket_limit"] = 7
    id_mapping = {}

    instance = LocalBaserowGroupedAggregateRowsUserServiceType().import_serialized(
        parent=integration,
        serialized_values=serialized_service,
        id_mapping=id_mapping,
        import_formula=Mock(),
    )

    assert instance.bucket_limit == 7
    assert instance.service_aggregation_group_bys.get().mode == (mode or "complete")
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


def test_grouped_aggregate_rows_rejects_unknown_grouping_mode():
    serializer = LocalBaserowTableServiceAggregationGroupBySerializer(
        data={"field_id": 1, "mode": "unknown"}
    )
    assert not serializer.is_valid()
    assert serializer.errors["mode"][0].code == "invalid_choice"


@pytest.mark.django_db
def test_grouped_aggregate_rows_sanitize_result_does_not_query_per_button_field(
    data_fixture,
):
    """
    Every allowed property rebuilds the table's properties, uncached, so a
    button field's flags would cost queries each time.
    """

    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")

    def sanitize_queries(button_count):
        table = data_fixture.create_database_table()
        field = data_fixture.create_number_field(table=table, name="Amount")
        group_by_field = data_fixture.create_text_field(table=table, name="Category")
        # Every field reads its constraints, so the field count stays the same.
        for _ in range(3 - button_count):
            data_fixture.create_text_field(table=table)
        for _ in range(button_count):
            data_fixture.create_button_field(table=table)
        service = data_fixture.create_service(
            LocalBaserowGroupedAggregateRows, table=table
        )
        allowed = [f"field_{group_by_field.id}", f"field_{field.id}_sum"]
        result = {"has_next_page": False, "results": [{allowed[0]: "Fruit"}]}
        # Only the properties are measured, not the table model they read.
        table.get_model()

        with CaptureQueriesContext(connection) as captured:
            service_type.sanitize_result(service, result, allowed)
        return len(captured)

    sanitize_queries(1)

    assert sanitize_queries(3) == sanitize_queries(1)


@pytest.mark.django_db
def test_grouped_aggregate_rows_dispatch_query_count_is_constant_with_buckets(
    data_fixture, mocker
):
    """
    Converting result keys to human readable names used to rebuild the full table
    schema, at one field constraints query per table field, for every result row
    and key. The dispatch query count must not grow with the number of groups, and
    the table properties must be built at most once per dispatch.
    """

    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(
        database=data_fixture.create_database_application(
            workspace=dashboard.workspace
        ),
        user=user,
    )
    number_field = data_fixture.create_number_field(table=table)
    text_field = data_fixture.create_text_field(table=table)
    for _ in range(5):
        data_fixture.create_text_field(table=table)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=number_field, aggregation_type="max", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=text_field, order=1
    )

    def create_groups(start, count):
        RowHandler().create_rows(
            user,
            table,
            rows_values=[
                {
                    f"field_{number_field.id}": index,
                    f"field_{text_field.id}": f"Group {index}",
                }
                for index in range(start, start + count)
            ],
        )

    def dispatch():
        with CaptureQueriesContext(connection) as context:
            result = ServiceHandler().dispatch_service(service, FakeDispatchContext())
        return len(context.captured_queries), result.data["results"]

    table_properties_spy = mocker.spy(
        LocalBaserowGroupedAggregateRowsUserServiceType, "_get_table_properties"
    )

    create_groups(0, 2)
    # Warm the global table schema cache so both measurements compare like for like.
    dispatch()
    queries_two_groups, results = dispatch()
    assert len(results) == 2

    create_groups(2, 4)
    queries_six_groups, results = dispatch()
    assert len(results) == 6

    assert queries_six_groups == queries_two_groups
    assert table_properties_spy.call_count <= 1


@pytest.mark.django_db
def test_grouped_aggregate_rows_serializes_trashed_configured_fields(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, trashed=True)
    integration = data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    series = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="max", order=1
    )
    group_by = LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=1
    )
    primary_group_by = LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=2
    )

    assert LocalBaserowTableServiceAggregationSeriesSerializer(series).data["trashed"]
    assert LocalBaserowTableServiceAggregationGroupBySerializer(group_by).data[
        "trashed"
    ]
    assert not LocalBaserowTableServiceAggregationGroupBySerializer(
        primary_group_by
    ).data["trashed"]


@pytest.mark.parametrize("value", [0, -1, 11, 1.5, "invalid"])
def test_grouped_aggregate_rows_invalid_bucket_limit(settings, value):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 10
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    serializer_field = service_type.serializer_field_overrides["bucket_limit"]
    with pytest.raises(ValidationError):
        serializer_field.run_validation(value)


@pytest.mark.parametrize("value", [None, 1, 10])
def test_grouped_aggregate_rows_valid_bucket_limit(settings, value):
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = 10
    service_type = service_type_registry.get("local_baserow_grouped_aggregate_rows")
    assert (
        service_type.serializer_field_overrides["bucket_limit"].run_validation(value)
        == value
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "saved_limit,server_limit,expected_count",
    [(2, 10, 2), (10, 2, 2), (None, 3, 3), (1, 10, 1)],
)
def test_grouped_aggregate_bucket_limit_dispatch(
    data_fixture, settings, saved_limit, server_limit, expected_count
):
    """Saved limits, defaults and lowered server caps bound the entire response."""
    settings.BASEROW_PREMIUM_GROUPED_AGGREGATE_SERVICE_MAX_AGG_BUCKETS = server_limit
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        bucket_limit=saved_limit,
        integration_args={"user": user},
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=0
    )
    RowHandler().create_rows(
        user, table, rows_values=[{field.db_column: value} for value in [1, 2, 3, 4]]
    )
    result = ServiceHandler().dispatch_service(service, FakeDispatchContext()).data
    assert len(result["results"]) == expected_count
    assert any(row["id"] == "OTHER_VALUES" for row in result["results"])
    assert sum(row["Amount sum"] for row in result["results"]) == 10


@pytest.mark.django_db
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
@pytest.mark.parametrize("bucket_limit", [2, 10])
def test_grouped_datetime_sort_preserves_minute_totals(
    data_fixture, direction, bucket_limit
):
    """Sorting must not split normalized minutes or drop rows from overflow."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    date_field = data_fixture.create_date_field(
        table=table, name="Date", date_include_time=True
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        bucket_limit=bucket_limit,
        integration_args={"user": user},
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=date_field, order=0
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=date_field.db_column,
        direction=direction,
        order=0,
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {date_field.db_column: timestamp, amount.db_column: amount_value}
            for timestamp, amount_value in [
                ("2026-01-01T10:00:05Z", 1),
                ("2026-01-01T10:00:40Z", 2),
                ("2026-01-01T10:01:00Z", 4),
                ("2026-01-01T10:02:05Z", 8),
                ("2026-01-01T10:02:40Z", 16),
            ]
        ],
    )
    rows = (
        ServiceHandler()
        .dispatch_service(service, FakeDispatchContext())
        .data["results"]
    )
    totals = [row["Amount sum"] for row in rows]
    assert sum(totals) == 31
    if bucket_limit == 2:
        assert totals == ([3, 28] if direction == "ASC" else [24, 7])
        assert rows[-1]["id"] == "OTHER_VALUES"
    else:
        assert totals == ([3, 4, 24] if direction == "ASC" else [24, 4, 3])


@pytest.mark.django_db
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
@pytest.mark.parametrize(
    "kind",
    ["single_select", "date", "multiple_select_complete", "multiple_select_individual"],
)
def test_grouped_aggregate_rows_empty_group_overflows_into_other_bucket(
    data_fixture, direction, kind
):
    """Fold an empty group into the overflow bucket; never drop or double count it."""
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    group_by_kwargs = {}
    if kind == "single_select":
        field = data_fixture.create_single_select_field(table=table, name="Category")
        values = [
            data_fixture.create_select_option(field=field, value=value).id
            for value in ["A", "B", "C"]
        ]
        empty = None
    elif kind == "date":
        field = data_fixture.create_date_field(
            table=table, name="Date", date_include_time=True
        )
        values = [f"2026-01-0{day}T10:00:00Z" for day in [1, 2, 3]]
        empty = None
    else:
        field = data_fixture.create_multiple_select_field(table=table, name="Category")
        values = [
            [data_fixture.create_select_option(field=field, value=value).id]
            for value in ["A", "B", "C"]
        ]
        empty = []
        if kind == "multiple_select_individual":
            group_by_kwargs["mode"] = "individual"
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        bucket_limit=3,
        integration_args={"user": user},
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, order=0, **group_by_kwargs
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="SERIES",
        reference=f"{amount.db_column}_sum",
        direction=direction,
        order=0,
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: group_value, amount.db_column: amount_value}
            for group_value, amount_value in zip([*values, empty], [10, 20, 30, 5])
        ],
    )
    rows = (
        ServiceHandler()
        .dispatch_service(service, FakeDispatchContext())
        .data["results"]
    )
    totals = [row["Amount sum"] for row in rows]
    assert sum(totals) == 65
    assert rows[-1]["id"] == "OTHER_VALUES"
    if direction == "ASC":
        # The empty group is kept and must not be counted again in "Other".
        assert rows[0]["id"] == "-"
        assert totals == [5, 10, 50]
    else:
        # The empty group overflows and must be part of "Other".
        assert totals == [30, 20, 15]


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_public_schema_and_context_data(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_number_field(table=table, name="Amount")
    group_by_field = data_fixture.create_single_select_field(
        table=table, name="Category"
    )
    option = data_fixture.create_select_option(
        field=group_by_field, value="Books", color="blue"
    )
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

    # The creator of the application gets the whole field.
    schema = service_type.generate_schema(service)
    metadata = schema["items"]["properties"][group_by_field.db_column]["metadata"]
    assert metadata["table_id"] == table.id
    assert "single_select_default" in metadata

    # Anonymous visitors only get what they need to format the labels of the
    # chart, in the schema and in the context data alike.
    public_metadata = {
        "id": group_by_field.id,
        "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "name": "Category",
        "type": "single_select",
        "primary": False,
        "read_only": False,
        "database_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "workspace_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
        "select_options": [{"id": option.id, "value": "Books", "color": "blue"}],
    }
    public_schema = service_type.generate_public_schema(service)
    public_properties = public_schema["items"]["properties"]
    assert public_properties[group_by_field.db_column] == {
        **schema["items"]["properties"][group_by_field.db_column],
        "metadata": public_metadata,
    }
    assert (
        public_properties[f"{field.db_column}_sum"]
        == schema["items"]["properties"][f"{field.db_column}_sum"]
    )
    assert service_type.get_public_context_data(service) == {
        "fields": {group_by_field.db_column: public_metadata}
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_service_public_schema_with_row_id_group_by(
    data_fixture,
):
    table = data_fixture.create_database_table()
    primary_field = data_fixture.create_text_field(
        table=table, primary=True, text_default="Unknown"
    )
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

    public_schema = service_type.generate_public_schema(service)
    metadata = public_schema["items"]["properties"][primary_field.db_column]["metadata"]

    # The chart finds the primary field through the metadata of the schema.
    assert metadata["id"] == primary_field.id
    assert metadata["primary"] is True
    assert metadata["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert "text_default" not in metadata
    assert service_type.get_public_context_data(service) == {
        "fields": {primary_field.db_column: metadata}
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_type,linked",
    [
        ("created_by", False),
        ("last_modified_by", False),
        ("multiple_collaborators", False),
        ("created_by", True),
        ("last_modified_by", True),
        ("multiple_collaborators", True),
    ],
)
def test_group_labels_do_not_expose_user_emails(data_fixture, field_type, linked):
    """User-valued primary fields use safe names, directly and through linked rows."""
    user = data_fixture.create_user(first_name="Alice")
    table = data_fixture.create_database_table(user=user)
    primary = getattr(data_fixture, f"create_{field_type}_field")(
        table=table, primary=True, name="Owner"
    )
    values = (
        {primary.db_column: [{"id": user.id}]}
        if field_type == "multiple_collaborators"
        else {}
    )
    row = RowHandler().create_row(user, table, values=values)
    if linked:
        linked_table = table
        table = data_fixture.create_database_table(user=user)
        primary = data_fixture.create_link_row_field(
            table=table, link_row_table=linked_table, primary=True, name="Owner"
        )
        RowHandler().create_row(user, table, values={primary.db_column: [row.id]})
    amount = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        table=table,
        integration_args={"user": user},
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="count", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=None, order=0
    )
    rows = (
        ServiceHandler()
        .dispatch_service(service, FakeDispatchContext())
        .data["results"]
    )
    assert [result["id"] for result in rows] == ["Alice"]
    assert user.email not in str(rows)
    model = table.get_model()
    field_object = model.get_field_object(primary.db_column)
    # Enhancing resolves the linked table's primary on the related model, which
    # the link row human readable value needs for a Multiple collaborators primary.
    value = getattr(model.objects.all().enhance_by_fields().first(), primary.db_column)
    assert user.email in primary.get_type().get_human_readable_value(
        value, field_object
    )
    assert primary.get_type().get_group_by_label(value, field_object) == "Alice"
    if not linked:
        assert primary.get_type().get_group_by_label(None, field_object) == ""


@pytest.mark.django_db
@pytest.mark.parametrize("with_sort", [False, True])
def test_link_row_group_values_use_display_safe_labels(data_fixture, with_sort):
    """
    Linked rows in group values carry the primary's group label, not its e-mail.

    Without a sort nothing resolves the linked table's primary before the dispatch
    prefetches it, which used to raise for a Multiple collaborators primary.
    """
    user = data_fixture.create_user(first_name="Alice")
    people = data_fixture.create_database_table(user=user)
    member = data_fixture.create_multiple_collaborators_field(
        table=people, primary=True
    )
    person = RowHandler().create_row(
        user, people, values={member.db_column: [{"id": user.id}]}
    )
    tasks = data_fixture.create_database_table(user=user, database=people.database)
    owner = data_fixture.create_link_row_field(
        table=tasks, link_row_table=people, name="Owner"
    )
    amount = data_fixture.create_number_field(table=tasks, name="Amount")
    RowHandler().create_row(
        user, tasks, values={owner.db_column: [person.id], amount.db_column: 10}
    )
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, table=tasks, integration_args={"user": user}
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=owner, order=0
    )
    if with_sort:
        LocalBaserowTableServiceAggregationSortBy.objects.create(
            service=service,
            sort_on="GROUP_BY",
            reference=owner.db_column,
            direction="ASC",
            order=0,
        )

    rows = (
        ServiceHandler()
        .dispatch_service(service, FakeDispatchContext())
        .data["results"]
    )

    assert user.email not in str(rows)
    assert rows[0]["id"] == "Alice"
    assert rows[0]["Owner"][0]["id"] == person.id
    assert rows[0]["Owner"][0]["value"] == "Alice"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field_type", ["link_row", "multiple_collaborators", "multiple_select"]
)
@pytest.mark.parametrize("direction", ["ASC", "DESC"])
def test_individual_group_sort_uses_member_field_type(
    data_fixture, field_type, direction
):
    """Each relation member retains its own sortable representation and aggregate."""
    user = data_fixture.create_user(first_name="Zulu")
    table = data_fixture.create_database_table(user=user)
    if field_type == "link_row":
        linked_table = data_fixture.create_database_table(user=user)
        primary = data_fixture.create_number_field(table=linked_table, primary=True)
        model = linked_table.get_model()
        members = [
            model.objects.create(**{primary.db_column: value}).id for value in [10, 2]
        ]
        field = data_fixture.create_link_row_field(
            table=table, link_row_table=linked_table
        )
    elif field_type == "multiple_collaborators":
        other = data_fixture.create_user(
            first_name="Alice", workspace=table.database.workspace
        )
        members = [{"id": person.id} for person in [user, other]]
        field = data_fixture.create_multiple_collaborators_field(table=table)
    else:
        field = data_fixture.create_multiple_select_field(table=table)
        members = [
            data_fixture.create_select_option(field=field, value=value).id
            for value in ["Zulu", "Alice"]
        ]
    amount = data_fixture.create_number_field(table=table, name="Amount")
    service = data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, table=table, integration_args={"user": user}
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=0
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=field, mode="individual", order=0
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=service,
        sort_on="GROUP_BY",
        reference=field.db_column,
        direction=direction,
        order=0,
    )
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {field.db_column: [member], amount.db_column: amount_value}
            for member, amount_value in zip(members, [10, 2])
        ],
    )
    rows = (
        ServiceHandler()
        .dispatch_service(service, FakeDispatchContext())
        .data["results"]
    )
    assert [row["Amount sum"] for row in rows] == (
        [2, 10] if direction == "ASC" else [10, 2]
    )

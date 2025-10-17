import pytest
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
    LocalBaserowTableServiceAggregationSortBy,
)
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import SORT_ORDER_ASC
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.test_utils.helpers import AnyDict, AnyInt


@pytest.mark.django_db
def test_grouped_aggregate_rows_get_dashboard_data_sources(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    table = premium_data_fixture.create_database_table(user=user)
    field = premium_data_fixture.create_number_field(table=table)
    field_2 = premium_data_fixture.create_number_field(table=table)
    field_3 = premium_data_fixture.create_number_field(table=table)
    data_source1 = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, name="Name 1"
    )
    data_source1.service.table = table
    data_source1.service.save()
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=data_source1.service, field=field, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=data_source1.service, field=field_2, aggregation_type="sum", order=2
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=data_source1.service, field=field_3, order=1
    )
    LocalBaserowTableServiceAggregationSortBy.objects.create(
        service=data_source1.service,
        sort_on="GROUP_BY",
        reference=f"field_{field_3.id}",
        direction="ASC",
        order=1,
    )
    premium_data_fixture.create_local_baserow_table_service_sort(
        service=data_source1.service,
        field=field_3,
        order_by=SORT_ORDER_ASC,
        order=2,
    )
    data_source2 = (
        premium_data_fixture.create_dashboard_local_baserow_list_rows_data_source(
            dashboard=dashboard, name="Name 2"
        )
    )

    url = reverse(
        "api:dashboard:data_sources:list", kwargs={"dashboard_id": dashboard.id}
    )
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2
    assert response_json[0] == {
        "aggregation_group_bys": [{"field_id": field_3.id, "order": 1}],
        "aggregation_series": [
            {
                "aggregation_type": "sum",
                "field_id": field.id,
                "id": AnyInt(),
            },
            {
                "aggregation_type": "sum",
                "field_id": field_2.id,
                "id": AnyInt(),
            },
        ],
        "context_data": {
            "fields": {
                f"field_{field_3.id}": {
                    "description": None,
                    "id": field_3.id,
                    "immutable_properties": False,
                    "immutable_type": False,
                    "name": field_3.name,
                    "number_decimal_places": 0,
                    "number_default": None,
                    "number_negative": False,
                    "number_prefix": "",
                    "number_separator": "",
                    "number_suffix": "",
                    "order": 0,
                    "primary": False,
                    "read_only": False,
                    "table_id": table.id,
                    "type": "number",
                    "database_id": table.database.id,
                    "workspace_id": table.database.workspace.id,
                    "db_index": False,
                    "field_constraints": [],
                },
            },
        },
        "context_data_schema": None,
        "dashboard_id": dashboard.id,
        "filter_type": "AND",
        "filters": [],
        "aggregation_sorts": [
            {
                "sort_on": "GROUP_BY",
                "reference": f"field_{field_3.id}",
                "direction": "ASC",
                "order": 1,
            }
        ],
        "id": data_source1.id,
        "integration_id": AnyInt(),
        "name": "Name 1",
        "order": "1.00000000000000000000",
        "schema": AnyDict(),
        "table_id": table.id,
        "type": "local_baserow_grouped_aggregate_rows",
        "view_id": None,
        "sample_data": None,
    }
    assert response_json[1] == {
        "context_data": None,
        "context_data_schema": None,
        "dashboard_id": dashboard.id,
        "default_result_count": 20,
        "filter_type": "AND",
        "filters": [],
        "sortings": [],
        "id": data_source2.id,
        "integration_id": AnyInt(),
        "name": "Name 2",
        "order": "2.00000000000000000000",
        "schema": None,
        "search_query": BaserowFormulaObject(
            formula="",
            version=BASEROW_FORMULA_VERSION_INITIAL,
            mode=BASEROW_FORMULA_MODE_SIMPLE,
        ),
        "table_id": None,
        "type": "local_baserow_list_rows",
        "view_id": None,
        "sample_data": None,
    }


@pytest.mark.django_db
def test_grouped_aggregate_rows_update_data_source(api_client, premium_data_fixture):
    user, token = premium_data_fixture.create_user_and_token()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    table = premium_data_fixture.create_database_table(user=user)
    view = premium_data_fixture.create_grid_view(user, table=table)
    field = premium_data_fixture.create_number_field(table=table)
    field_2 = premium_data_fixture.create_number_field(table=table)
    field_3 = premium_data_fixture.create_number_field(table=table)
    data_source1 = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard
    )
    url = reverse(
        "api:dashboard:data_sources:item", kwargs={"data_source_id": data_source1.id}
    )

    response = api_client.patch(
        url,
        {
            "table_id": table.id,
            "view_id": view.id,
            "name": "name test",
            "aggregation_series": [
                {"field_id": field.id, "aggregation_type": "sum"},
                {"field_id": field_2.id, "aggregation_type": "sum"},
            ],
            "aggregation_group_bys": [{"field_id": field_3.id}],
            "aggregation_sorts": [
                {
                    "sort_on": "SERIES",
                    "reference": f"field_{field.id}_sum",
                    "direction": "ASC",
                }
            ],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["table_id"] == table.id
    assert response_json["view_id"] == view.id
    assert response_json["name"] == "name test"
    assert response_json["type"] == "local_baserow_grouped_aggregate_rows"
    assert response_json["aggregation_series"] == [
        {
            "aggregation_type": "sum",
            "field_id": field.id,
            "id": AnyInt(),
        },
        {
            "aggregation_type": "sum",
            "field_id": field_2.id,
            "id": AnyInt(),
        },
    ]
    assert response_json["aggregation_group_bys"] == [
        {"field_id": field_3.id, "order": 0}
    ]
    assert response_json["aggregation_sorts"] == [
        {
            "sort_on": "SERIES",
            "reference": f"field_{field.id}_sum",
            "direction": "ASC",
            "order": 0,
        }
    ]


@pytest.mark.django_db
def test_grouped_aggregate_rows_dispatch_dashboard_data_source(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user, database=database)
    dashboard = premium_data_fixture.create_dashboard_application(
        user=user, workspace=workspace
    )
    field = premium_data_fixture.create_number_field(table=table)
    field_2 = premium_data_fixture.create_number_field(table=table)
    field_3 = premium_data_fixture.create_number_field(table=table)
    integration = premium_data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = premium_data_fixture.create_service(
        LocalBaserowGroupedAggregateRows,
        integration=integration,
        table=table,
    )
    data_source1 = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, service=service, integration_args={"user": user}
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
    url = reverse(
        "api:dashboard:data_sources:dispatch",
        kwargs={"data_source_id": data_source1.id},
    )

    response = api_client.post(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK, response_json
    assert response_json == {
        "result": [
            {
                f"field_{field.id}": 30.0,
                f"field_{field.id}_sum": 90.0,
                f"field_{field_2.id}_sum": 9.0,
                f"field_{field_3.id}_sum": 3.0,
            },
            {
                f"field_{field.id}": 20.0,
                f"field_{field.id}_sum": 60.0,
                f"field_{field_2.id}_sum": 6.0,
                f"field_{field_3.id}_sum": 6.0,
            },
            {
                f"field_{field.id}": 10.0,
                f"field_{field.id}_sum": 30.0,
                f"field_{field_2.id}_sum": 3.0,
                f"field_{field_3.id}_sum": 6.0,
            },
            {
                f"field_{field.id}": None,
                f"field_{field.id}_sum": None,
                f"field_{field_2.id}_sum": 100.0,
                f"field_{field_3.id}_sum": 100.0,
            },
        ],
    }

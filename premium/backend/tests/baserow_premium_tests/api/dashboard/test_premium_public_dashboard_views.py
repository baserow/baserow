import pytest
from rest_framework.reverse import reverse
from rest_framework.status import HTTP_200_OK

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


def public_info_url(slug):
    return reverse("api:dashboard:public:info", kwargs={"slug": slug})


def public_dispatch_url(slug, data_source_id):
    return reverse(
        "api:dashboard:public:data_source_dispatch",
        kwargs={"slug": slug, "data_source_id": data_source_id},
    )


def create_public_dashboard_with_chart(premium_data_fixture, user):
    """
    Creates a public dashboard with a chart widget that sums an amount per
    category.
    """

    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user, database=database)
    amount = premium_data_fixture.create_number_field(table=table, name="Amount")
    category = premium_data_fixture.create_number_field(table=table, name="Category")
    RowHandler().create_rows(
        user,
        table,
        rows_values=[
            {f"field_{amount.id}": 10, f"field_{category.id}": 1},
            {f"field_{amount.id}": 20, f"field_{category.id}": 1},
            {f"field_{amount.id}": 30, f"field_{category.id}": 2},
        ],
    )
    dashboard = premium_data_fixture.create_dashboard_application(
        user=user, workspace=workspace, public=True
    )
    integration = premium_data_fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = premium_data_fixture.create_service(
        LocalBaserowGroupedAggregateRows, integration=integration, table=table
    )
    data_source = premium_data_fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard,
        service=service,
        name="Amount per category",
        integration_args={"user": user},
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=category, order=1
    )
    widget = premium_data_fixture.create_chart_widget(
        dashboard=dashboard, data_source=data_source, title="Chart"
    )
    return dashboard, data_source, widget, amount, category


@pytest.mark.django_db
def test_public_dashboard_info_exposes_what_the_chart_widget_needs(
    api_client, premium_data_fixture
):
    user = premium_data_fixture.create_user()
    dashboard, data_source, widget, amount, category = (
        create_public_dashboard_with_chart(premium_data_fixture, user)
    )

    response = api_client.get(public_info_url(dashboard.slug), format="json")

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    public_widget = response_json["widgets"][0]
    assert public_widget["id"] == widget.id
    assert public_widget["type"] == "chart"
    assert public_widget["data_source_id"] == data_source.id
    assert "series_config" in public_widget

    public_data_source = response_json["data_sources"][0]
    assert public_data_source["id"] == data_source.id
    assert public_data_source["type"] == "local_baserow_grouped_aggregate_rows"
    assert set(public_data_source.keys()) == {
        "id",
        "name",
        "type",
        "schema",
        "context_data",
        "table_id",
        "aggregation_series",
        "aggregation_group_bys",
    }
    assert [
        (series["field_id"], series["aggregation_type"])
        for series in public_data_source["aggregation_series"]
    ] == [(amount.id, "sum")]
    assert [
        group_by["field_id"] for group_by in public_data_source["aggregation_group_bys"]
    ] == [category.id]
    assert set(public_data_source["context_data"]["fields"].keys()) == {
        f"field_{category.id}"
    }
    assert (
        f"field_{amount.id}_sum" in public_data_source["schema"]["items"]["properties"]
    )
    assert public_data_source["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    # The grouped field is reduced to what the chart needs to format its labels,
    # in the context data and in the metadata of the schema alike.
    public_category = public_data_source["context_data"]["fields"][
        f"field_{category.id}"
    ]
    assert set(public_category.keys()) == {
        "id",
        "table_id",
        "name",
        "type",
        "primary",
        "read_only",
        "database_id",
        "workspace_id",
        "number_decimal_places",
        "number_negative",
        "number_prefix",
        "number_suffix",
        "number_separator",
    }
    assert public_category["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert public_category["database_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert public_category["workspace_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    schema_properties = public_data_source["schema"]["items"]["properties"]
    assert schema_properties[f"field_{category.id}"]["metadata"] == public_category


@pytest.mark.django_db
def test_dispatch_public_grouped_aggregate_rows_data_source(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token()
    dashboard, data_source, _, _, _ = create_public_dashboard_with_chart(
        premium_data_fixture, user
    )

    response = api_client.post(
        public_dispatch_url(dashboard.slug, data_source.id), format="json"
    )

    assert response.status_code == HTTP_200_OK
    assert len(response.json()["results"]) == 2

    authenticated_response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": data_source.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert authenticated_response.status_code == HTTP_200_OK
    assert response.json() == authenticated_response.json()

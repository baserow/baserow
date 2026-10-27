from django.urls import reverse

import pytest

from baserow.contrib.dashboard.filters.service import DashboardFilterService


@pytest.mark.django_db
def test_sources_reference_one_dashboard_filter_without_table_bindings(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    selection = DashboardFilterService().create_filter(
        user, dashboard.id, label="Country", mode="input", values=["France"]
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    widgets = []
    for country_field, rows, expected in [
        ("Country", [["France", 70], ["Belgium", 30]], "70"),
        ("Market", [["France", 12], ["Germany", 8]], "12"),
    ]:
        table, fields, _ = data_fixture.build_table(
            user=user,
            database=data_fixture.create_database_application(
                workspace=dashboard.workspace
            ),
            columns=[(country_field, "text"), ("Amount", "number")],
            rows=rows,
        )
        source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard,
            integration=integration,
            table=table,
            field=fields[1],
            aggregation_type="sum",
        )
        widget = data_fixture.create_summary_widget(
            dashboard=dashboard, data_source=source
        )
        response = api_client.patch(
            reverse(
                "api:dashboard:data_sources:item", kwargs={"data_source_id": source.id}
            ),
            {
                "type": "local_baserow_aggregate_rows",
                "filters": [
                    {
                        "field": fields[0].id,
                        "type": "equal",
                        "value": {
                            "formula": f"get('dashboard_filter.{selection.id}')",
                            "mode": "advanced",
                        },
                    }
                ],
            },
            format="json",
            **headers,
        )
        assert response.status_code == 200, response.json()
        widgets.append((widget, expected))

    unfiltered_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard,
            integration=integration,
            table=table,
            field=fields[1],
            aggregation_type="sum",
        )
    )
    widgets.append(
        (
            data_fixture.create_summary_widget(
                dashboard=dashboard, data_source=unfiltered_source
            ),
            "20",
        )
    )
    for widget, expected in widgets:
        response = api_client.post(
            reverse(
                "api:dashboard:data_sources:dispatch",
                kwargs={"data_source_id": widget.data_source_id},
            ),
            {},
            format="json",
            **headers,
        )
        assert response.status_code == 200, response.json()
        assert response.json() == {"result": expected}


@pytest.mark.django_db
def test_option_formulas_read_widget_table_rows_without_its_aggregation_or_filters(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    dashboard = data_fixture.create_dashboard_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Country", "text"), ("Code", "text")],
        rows=[["France", "FR"], ["Belgium", "BE"]],
    )
    source = data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
        dashboard=dashboard,
        integration=integration,
        table=table,
    )
    data_fixture.create_summary_widget(dashboard=dashboard, data_source=source)
    data_fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=fields[0],
        type="equal",
        value={"formula": "France", "mode": "raw"},
    )
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    response = api_client.post(
        reverse("api:dashboard:filters:list", kwargs={"dashboard_id": dashboard.id}),
        {
            "label": "Country",
            "formula_value": {
                "formula": f"get('table.{table.id}.*.{fields[1].db_column}')",
                "mode": "advanced",
            },
        },
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    response = api_client.post(
        reverse(
            "api:dashboard:filters:options",
            kwargs={"filter_id": response.json()["id"]},
        ),
        {"selected": ["BE"]},
        format="json",
        **headers,
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    snapshot = data.pop("snapshot")
    assert isinstance(snapshot, str) and snapshot
    assert data == {
        "results": ["FR", "BE"],
        "next": None,
        "available": ["BE"],
    }

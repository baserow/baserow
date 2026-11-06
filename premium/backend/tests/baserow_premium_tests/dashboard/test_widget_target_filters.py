from django.http import HttpRequest
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.widgets.models import TextFilterWidget, Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.formula import BaserowFormulaObject
from baserow.core.registries import ImportExportConfig
from baserow.core.trash.handler import TrashHandler
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


@pytest.fixture(params=["chart", "pie_chart"])
def chart_filter_dashboard(premium_data_fixture, request):
    """Create a real grouped source for both chart families with distinct values."""
    fixture = premium_data_fixture
    user, token = fixture.create_user_and_token()
    workspace = fixture.create_workspace(user=user)
    database = fixture.create_database_application(workspace=workspace)
    table = fixture.create_database_table(database=database)
    name = fixture.create_text_field(table=table, name="Name")
    amount = fixture.create_number_field(table=table, name="Amount")
    RowHandler().create_rows(
        user,
        table,
        [
            {name.db_column: "Alpha", amount.db_column: 10},
            {name.db_column: "Beta", amount.db_column: 20},
        ],
    )
    dashboard = fixture.create_dashboard_application(workspace=workspace, public=True)
    integration = fixture.create_local_baserow_integration(
        application=dashboard, user=user
    )
    service = fixture.create_service(
        LocalBaserowGroupedAggregateRows, integration=integration, table=table
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=service, field=name, order=1
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=amount, aggregation_type="sum", order=1
    )
    source = fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, service=service
    )
    target = getattr(fixture, f"create_{request.param}_widget")(
        dashboard=dashboard,
        data_source=source,
        title="Chart",
        grid_width=6,
        grid_height=9,
    )
    owner = TextFilterWidget.objects.create(
        dashboard=dashboard,
        title="Search",
        default_value="Alpha",
        grid_width=2,
        grid_height=4,
        grid_y=9,
    )
    WidgetService().update_widget(
        user,
        owner.id,
        target_filters=[
            {
                "target_widget_id": target.id,
                "empty_behavior": "apply_nothing",
                "group": {
                    "filter_type": "AND",
                    "filter_groups": [],
                    "filters": [
                        {
                            "field": name.id,
                            "type": "equal",
                            "value": BaserowFormulaObject.create(
                                f"get('widget_data.{owner.id}')"
                            ),
                        }
                    ],
                },
            }
        ],
    )
    owner.refresh_from_db()
    return user, token, dashboard, source, target, owner


@pytest.mark.django_db
@pytest.mark.parametrize("public", [False, True])
def test_chart_target_dispatch(
    api_client, premium_data_fixture, chart_filter_dashboard, public
):
    """Both chart types filter privately and publicly, including clearing."""
    _, token, dashboard, source, target, owner = chart_filter_dashboard
    if public:
        url = reverse(
            "api:dashboard:public:data_source_dispatch",
            kwargs={"slug": dashboard.slug, "data_source_id": source.id},
        )
        headers = {}
    else:
        url = reverse(
            "api:dashboard:data_sources:dispatch", kwargs={"data_source_id": source.id}
        )
        headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    for value, expected in [
        ("Alpha", {"Alpha": 10}),
        ("Beta", {"Beta": 20}),
        ("", {"Alpha": 10, "Beta": 20}),
    ]:
        response = api_client.post(
            url, {"widget_data": {str(owner.id): value}}, format="json", **headers
        )
        assert response.status_code == 200, response.json()
        assert {
            row["Name"]: row["Amount sum"] for row in response.json()["results"]
        } == expected
    service = source.service.specific
    premium_data_fixture.create_local_baserow_table_service_filter(
        service=service,
        field=service.table.field_set.get(name="Name"),
        type="equal",
        value=BaserowFormulaObject.create("Beta", mode="raw"),
    )
    response = api_client.post(
        url, {"widget_data": {str(owner.id): "Alpha"}}, format="json", **headers
    )
    assert response.status_code == 200, response.json()
    assert response.json()["results"] == []


@pytest.mark.django_db
def test_chart_target_import_and_restore(chart_filter_dashboard):
    """Import remaps chart links and trash restoration recovers their groups."""
    user, _, dashboard, source, target, owner = chart_filter_dashboard
    links = owner.target_filters
    links[0]["group"]["filter_type"] = "OR"
    WidgetService().update_widget(user, owner.id, target_filters=links)
    app_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True)
    mapping = {}
    copied = app_type.import_serialized(
        dashboard.workspace,
        app_type.export_serialized(dashboard, config),
        config,
        mapping,
    )
    copied_owner = TextFilterWidget.objects.get(dashboard=copied)
    copied_target = Widget.objects.get(
        id=mapping["dashboard_widgets"][target.id]
    ).specific
    assert copied_owner.target_filters[0]["group"]["filter_type"] == "OR"
    assert copied_owner.target_filters[0]["target_widget_id"] == copied_target.id
    assert (
        f"widget_data.{copied_owner.id}"
        in copied_owner.target_filters[0]["group"]["filters"][0]["value"]["formula"]
    )
    original = owner.target_filters
    TrashHandler.trash(user, dashboard.workspace, dashboard, target)
    owner.refresh_from_db()
    assert owner.target_filters == []
    TrashHandler.restore_item(user, "widget", target.id)
    owner.refresh_from_db()
    assert owner.target_filters == original
    result = DashboardDataSourceHandler().dispatch_data_source(
        source, DashboardDispatchContext(HttpRequest(), dashboard=dashboard)
    )
    assert {row["Name"]: row["Amount sum"] for row in result["results"]} == {
        "Alpha": 10
    }

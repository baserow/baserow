from copy import deepcopy

from django.http import HttpRequest
from django.urls import reverse

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.filters.options import DashboardFilterOptionsService
from baserow.contrib.dashboard.filters.service import DashboardFilterService
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.registries import ImportExportConfig
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowTableServiceAggregationGroupBy,
    LocalBaserowTableServiceAggregationSeries,
)


@pytest.mark.django_db
def test_text_filter_is_applied_before_grouped_aggregation(
    api_client, premium_data_fixture
):
    fixture = premium_data_fixture
    user, token = fixture.create_user_and_token()
    dashboard = fixture.create_dashboard_application(user=user)
    integration = fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=user
    )
    table, fields, _ = fixture.build_table(
        user=user,
        database=fixture.create_database_application(workspace=dashboard.workspace),
        columns=[("Team", "text"), ("Region", "text"), ("Budget", "number")],
        rows=[
            ["Design", "Europe", 20],
            ["Design", "Europe", 30],
            ["Sales", "Europe", 70],
            ["Design", "Asia", 10],
        ],
    )
    source = fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, integration=integration, table=table
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=source.service, field=fields[2], aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=source.service, field=fields[1], order=1
    )
    widget = fixture.create_chart_widget(dashboard=dashboard, data_source=source)
    config = DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Team",
        values=["Design"],
    )
    fixture.create_local_baserow_table_service_filter(
        service=source.service,
        field=fields[0],
        type="equal",
        value=BaserowFormulaObject.create(f"get('dashboard_filter.{config.id}')"),
    )
    response = api_client.post(
        reverse(
            "api:dashboard:data_sources:dispatch",
            kwargs={"data_source_id": widget.data_source_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 200, response.json()
    assert sorted(
        (row["Region"], row["Budget sum"]) for row in response.json()["results"]
    ) == [("Asia", 10), ("Europe", 50)]


@pytest.mark.django_db
def test_copy_remaps_option_formulas_for_grouped_source_tables(premium_data_fixture):
    fixture = premium_data_fixture
    user = fixture.create_user()
    dashboard = fixture.create_dashboard_application(user=user)
    integration = fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=user
    )
    table, fields, _ = fixture.build_table(
        user=user,
        columns=[("Country", "text"), ("Amount", "number")],
        rows=[["France", 10]],
    )
    replacement, replacement_fields, _ = fixture.build_table(
        user=user,
        columns=[("Market", "text"), ("Budget", "number")],
        rows=[["Belgium", 20]],
    )
    source = fixture.create_dashboard_local_baserow_grouped_aggregate_rows_data_source(
        dashboard=dashboard, integration=integration, table=table
    )
    LocalBaserowTableServiceAggregationSeries.objects.create(
        service=source.service, field=fields[1], aggregation_type="sum", order=1
    )
    LocalBaserowTableServiceAggregationGroupBy.objects.create(
        service=source.service, field=fields[0], order=1
    )
    fixture.create_chart_widget(dashboard=dashboard, data_source=source)
    DashboardFilterService().create_filter(
        user,
        dashboard.id,
        label="Country",
        formula_value=BaserowFormulaObject.create(
            f"get('table.{table.id}.*.{fields[0].db_column}')"
        ),
    )
    application_type = DashboardApplicationType()
    config = ImportExportConfig(include_permission_data=True, is_duplicate=True)
    exported = application_type.export_serialized(dashboard, config)
    mapping = {
        "database_tables": {table.id: replacement.id},
        "database_fields": {
            old.id: new.id for old, new in zip(fields, replacement_fields)
        },
    }
    copied = application_type.import_serialized(
        dashboard.workspace, deepcopy(exported), config, mapping
    )
    selection = DashboardFilterService().get_filters(user, copied.id)[0]
    request = HttpRequest()
    request.user = user
    options = DashboardFilterOptionsService().get_options(user, selection.id, request)
    assert options["results"] == ["Belgium"]

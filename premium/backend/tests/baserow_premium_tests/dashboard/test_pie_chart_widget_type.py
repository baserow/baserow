import json
from decimal import Decimal
from typing import cast

from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
from django.test.utils import override_settings

import pytest
from baserow_premium.dashboard.widgets.models import (
    PieChartSeriesConfig,
    PieChartWidget,
)
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
    LocalBaserowTableServiceAggregationSeries,
)

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.models import Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.dashboard.widgets.trash_types import WidgetTrashableItemType
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.registries import ImportExportConfig
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder, Progress


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_pie_chart_widget_creates_data_source(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    widget_type = "pie_chart"

    created_widget = WidgetService().create_widget(
        user,
        widget_type,
        dashboard.id,
        title="Pie chart widget",
        description="My description",
    )

    assert created_widget.data_source is not None
    assert (
        created_widget.data_source.service.content_type
        == ContentType.objects.get_for_model(LocalBaserowGroupedAggregateRows)
    )


@pytest.mark.django_db
def test_pie_chart_widget_trash_restore(premium_data_fixture):
    user = premium_data_fixture.create_user()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    pie_chart_widget = premium_data_fixture.create_pie_chart_widget(dashboard=dashboard)
    data_source_id = pie_chart_widget.data_source.id

    TrashHandler.trash(user, dashboard.workspace, dashboard, pie_chart_widget)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is True

    TrashHandler.restore_item(user, WidgetTrashableItemType.type, pie_chart_widget.id)

    ds = DashboardDataSource.objects_and_trash.get(id=data_source_id)
    assert ds.trashed is False


@pytest.mark.django_db
def test_pie_chart_widget_datasource_cannot_be_deleted(premium_data_fixture):
    user = premium_data_fixture.create_user()
    dashboard = premium_data_fixture.create_dashboard_application(user=user)
    pie_chart_widget = premium_data_fixture.create_pie_chart_widget(dashboard=dashboard)

    with pytest.raises(ProtectedError):
        DashboardDataSourceService().delete_data_source(
            user, pie_chart_widget.data_source.id
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_dashboard_export_serialized_with_pie_chart_widget_config(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_number_field(table=table)
    field_2 = premium_data_fixture.create_number_field(table=table)
    dashboard = cast(
        Dashboard,
        CoreHandler().create_application(
            user,
            workspace,
            type_name="dashboard",
            description="Dashboard description",
            init_with_data=True,
        ),
    )
    integration = Integration.objects.filter(application=dashboard).first()
    dashboard_widget = WidgetService().create_widget(
        user, "pie_chart", dashboard.id, title="Pie chart", description="Description 1"
    )
    service = dashboard_widget.data_source.service
    service.table = table
    service.save()
    series_1 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field, aggregation_type="sum", order=1
    )
    series_2 = LocalBaserowTableServiceAggregationSeries.objects.create(
        service=service, field=field_2, aggregation_type="min", order=1
    )
    series_conf_1 = PieChartSeriesConfig.objects.create(
        widget=dashboard_widget, series=series_1, series_chart_type="PIE"
    )
    series_conf_2 = PieChartSeriesConfig.objects.create(
        widget=dashboard_widget, series=series_2, series_chart_type="DOUGHNUT"
    )

    serialized = DashboardApplicationType().export_serialized(
        dashboard, ImportExportConfig(include_permission_data=True)
    )

    serialized = json.loads(json.dumps(serialized))
    assert serialized == {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": "Dashboard description",
        "order": dashboard.order,
        "type": "dashboard",
        "integrations": [
            {
                "authorized_user": user.email,
                "id": integration.id,
                "name": "",
                "order": "1.00000000000000000000",
                "type": "local_baserow",
            },
        ],
        "data_sources": [
            {
                "id": dashboard_widget.data_source.id,
                "name": dashboard_widget.data_source.name,
                "order": "1.00000000000000000000",
                "service": {
                    "filter_type": "AND",
                    "filters": [],
                    "id": service.id,
                    "sample_data": None,
                    "integration_id": service.integration.id,
                    "service_aggregation_group_bys": [],
                    "service_aggregation_sorts": [],
                    "service_aggregation_series": [
                        {
                            "aggregation_type": "sum",
                            "field_id": field.id,
                            "id": series_1.id,
                        },
                        {
                            "aggregation_type": "min",
                            "field_id": field_2.id,
                            "id": series_2.id,
                        },
                    ],
                    "table_id": table.id,
                    "type": "local_baserow_grouped_aggregate_rows",
                    "view_id": None,
                },
            },
        ],
        "widgets": [
            {
                "data_source_id": dashboard_widget.data_source.id,
                "description": "Description 1",
                "id": dashboard_widget.id,
                "order": "1.00000000000000000000",
                "title": "Pie chart",
                "type": "pie_chart",
                "series_config": [
                    {"series_chart_type": "PIE", "series_id": series_1.id},
                    {"series_chart_type": "DOUGHNUT", "series_id": series_2.id},
                ],
                "default_series_chart_type": "PIE",
            },
        ],
    }


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_dashboard_import_serialized_with_pie_chart_widget_config(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    workspace = premium_data_fixture.create_workspace(user=user)
    database = premium_data_fixture.create_database_application(
        user=user, workspace=workspace
    )
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_number_field(table=table)
    field_2 = premium_data_fixture.create_number_field(table=table, primary=True)

    id_mapping = {
        "database_tables": {1: table.id},
        "database_fields": {1: field.id, 2: field_2.id},
    }

    serialized = {
        "id": "999",
        "name": "Dashboard 1",
        "description": "Description 1",
        "order": 99,
        "type": "dashboard",
        "integrations": [
            {
                "authorized_user": user.email,
                "id": 1,
                "name": "IntegrationName",
                "order": "1.00000000000000000000",
                "type": "local_baserow",
            },
        ],
        "data_sources": [
            {
                "id": 1,
                "name": "DataSource1",
                "order": "1.00000000000000000000",
                "service": {
                    "filter_type": "AND",
                    "filters": [],
                    "id": 1,
                    "integration_id": 1,
                    "service_aggregation_group_bys": [],
                    "service_aggregation_series": [
                        {"aggregation_type": "sum", "field_id": 1, "id": 1},
                        {"aggregation_type": "min", "field_id": 2, "id": 2},
                    ],
                    "service_aggregation_sorts": [],
                    "table_id": 1,
                    "type": "local_baserow_grouped_aggregate_rows",
                    "view_id": None,
                },
            },
        ],
        "widgets": [
            {
                "data_source_id": 1,
                "description": "Description 1",
                "id": 45,
                "order": "1.00000000000000000000",
                "title": "Pie chart",
                "type": "pie_chart",
                "series_config": [
                    {"series_chart_type": "PIE", "series_id": 1},
                    {"series_chart_type": "DOUGHNUT", "series_id": 2},
                ],
            },
        ],
    }

    progress = Progress(100)
    progress_builder = ChildProgressBuilder(parent=progress, represents_progress=100)
    assert progress.progress == 0

    dashboard = DashboardApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
        progress_builder=progress_builder,
    )

    assert dashboard.name == "Dashboard 1"
    assert dashboard.description == "Description 1"
    assert dashboard.order == 99

    integrations = Integration.objects.filter(application=dashboard)
    integration = integrations[0].specific
    assert integrations.count() == 1
    assert integration.content_type == ContentType.objects.get_for_model(
        LocalBaserowIntegration
    )
    assert integration.authorized_user.id == user.id
    assert integration.name == "IntegrationName"
    assert integration.order == Decimal("1.0")

    data_sources = DashboardDataSource.objects.filter(dashboard=dashboard)
    assert data_sources.count() == 1

    ds1 = data_sources[0]
    ds1.name = "DataSource1"
    ds1.order = Decimal("1.0")
    service = ds1.service.specific
    assert service.content_type == ContentType.objects.get_for_model(
        LocalBaserowGroupedAggregateRows
    )
    assert service.integration_id == integration.id
    assert service.filter_type == "AND"

    series = service.service_aggregation_series.all()
    assert series.count() == 2
    assert series[0].aggregation_type == "sum"
    assert series[0].field_id == field.id
    assert series[1].aggregation_type == "min"
    assert series[1].field_id == field_2.id

    widgets = Widget.objects.filter(dashboard=dashboard)
    assert widgets.count() == 1
    widget1 = widgets[0].specific
    assert widget1.content_type == ContentType.objects.get_for_model(PieChartWidget)
    assert widget1.title == "Pie chart"
    assert widget1.description == "Description 1"
    assert widget1.order == Decimal("1.0")
    assert widget1.data_source.id == ds1.id

    series_configs = PieChartSeriesConfig.objects.filter(widget=widget1)
    assert series_configs.count() == 2
    assert series_configs[0].series_chart_type == "PIE"
    assert series_configs[1].series_chart_type == "DOUGHNUT"

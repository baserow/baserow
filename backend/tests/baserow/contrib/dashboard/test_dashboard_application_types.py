import json
from decimal import Decimal
from typing import cast

from django.contrib.contenttypes.models import ContentType

import pytest

from baserow.contrib.dashboard.application_types import DashboardApplicationType
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.dashboard.widgets.models import SummaryWidget, Widget
from baserow.contrib.dashboard.widgets.service import WidgetService
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowAggregateRows,
    LocalBaserowIntegration,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.registries import ImportExportConfig
from baserow.core.services.registries import service_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder, Progress


@pytest.mark.django_db
def test_dashboard_export_serialized(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(
        name="Dashboard 1", description="Description 1", user=user
    )
    serialized = DashboardApplicationType().export_serialized(
        dashboard, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized == {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": "Description 1",
        "order": dashboard.order,
        "type": "dashboard",
        "integrations": [],
        "data_sources": [],
        "widgets": [],
    }


@pytest.mark.django_db
def test_dashboard_export_serialized_with_widgets(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    number_field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)
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
    dashboard_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Widget 1", description="Description 1"
    )
    dashboard_widget_2 = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Widget 2", description="Description 2"
    )
    service_type = service_type_registry.get_by_model(
        dashboard_widget_2.data_source.service.specific_class
    )
    DashboardDataSourceService().update_data_source(
        user,
        dashboard_widget_2.data_source.id,
        service_type,
        table_id=table.id,
        view_id=view.id,
        field_id=number_field.id,
        aggregation_type="sum",
    )
    integration = Integration.objects.filter(application=dashboard).first()

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
                    "aggregation_type": "",
                    "field_id": None,
                    "filter_type": "AND",
                    "filters": [],
                    "id": dashboard_widget.data_source.service.id,
                    "integration_id": integration.id,
                    "search_query": {"formula": "", "mode": "simple", "version": "0.1"},
                    "table_id": None,
                    "type": "local_baserow_aggregate_rows",
                    "view_id": None,
                    "sample_data": None,
                },
            },
            {
                "id": dashboard_widget_2.data_source.id,
                "name": dashboard_widget_2.data_source.name,
                "order": "2.00000000000000000000",
                "service": {
                    "aggregation_type": "sum",
                    "field_id": number_field.id,
                    "filter_type": "AND",
                    "filters": [],
                    "id": dashboard_widget_2.data_source.service.id,
                    "integration_id": integration.id,
                    "search_query": {"formula": "", "mode": "simple", "version": "0.1"},
                    "table_id": table.id,
                    "type": "local_baserow_aggregate_rows",
                    "view_id": view.id,
                    "sample_data": None,
                },
            },
        ],
        "widgets": [
            {
                "data_source_id": dashboard_widget.data_source.id,
                "description": "Description 1",
                "id": dashboard_widget.id,
                "order": "1.00000000000000000000",
                "title": "Widget 1",
                "type": "summary",
            },
            {
                "data_source_id": dashboard_widget_2.data_source.id,
                "description": "Description 2",
                "id": dashboard_widget_2.id,
                "order": "2.00000000000000000000",
                "title": "Widget 2",
                "type": "summary",
            },
        ],
    }


@pytest.mark.django_db
def test_dashboard_import_serialized(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    id_mapping = {}
    serialized = {
        "id": "999",
        "name": "Dashboard 1",
        "description": "Description 1",
        "order": 99,
        "type": "dashboard",
        "integrations": [],
        "data_sources": [],
        "widgets": [],
    }

    dashboard = DashboardApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
    )

    assert dashboard.name == "Dashboard 1"
    assert dashboard.description == "Description 1"
    assert dashboard.order == 99


@pytest.mark.django_db()
def test_dashboard_import_serialized_with_widgets(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    number_field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    id_mapping = {
        "database_tables": {1: table.id},
        "database_fields": {1: number_field.id},
        "database_views": {1: view.id},
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
                    "aggregation_type": "",
                    "field_id": None,
                    "filter_type": "AND",
                    "filters": [],
                    "id": 1,
                    "integration_id": 1,
                    "search_query": "",
                    "table_id": None,
                    "type": "local_baserow_aggregate_rows",
                    "view_id": None,
                },
            },
            {
                "id": 2,
                "name": "DataSource2",
                "order": "2.00000000000000000000",
                "service": {
                    "aggregation_type": "sum",
                    "field_id": 1,
                    "filter_type": "AND",
                    "filters": [],
                    "id": 2,
                    "integration_id": 1,
                    "search_query": "",
                    "table_id": 1,
                    "type": "local_baserow_aggregate_rows",
                    "view_id": 1,
                },
            },
        ],
        "widgets": [
            {
                "data_source_id": 1,
                "description": "Description 1",
                "id": 45,
                "order": "1.00000000000000000000",
                "title": "Widget 1",
                "type": "summary",
            },
            {
                "data_source_id": 2,
                "description": "Description 2",
                "id": 46,
                "order": "2.00000000000000000000",
                "title": "Widget 2",
                "type": "summary",
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
    assert data_sources.count() == 2

    ds1 = data_sources[0]
    ds1.name = "DataSource1"
    ds1.order = Decimal("1.0")
    ds1_service = ds1.service.specific
    assert ds1_service.content_type == ContentType.objects.get_for_model(
        LocalBaserowAggregateRows
    )
    assert ds1_service.integration_id == integration.id
    assert ds1_service.aggregation_type == ""
    assert ds1_service.filter_type == "AND"
    assert ds1_service.search_query["formula"] == ""
    assert ds1_service.table_id is None
    assert ds1_service.view_id is None
    assert ds1_service.field_id is None

    ds2 = data_sources[1]
    ds2.name = "DataSource2"
    ds2.order = Decimal("2.0")
    ds2_service = ds2.service.specific

    assert ds2_service.content_type == ContentType.objects.get_for_model(
        LocalBaserowAggregateRows
    )
    assert ds2_service.integration_id == integration.id
    assert ds2_service.aggregation_type == "sum"
    assert ds2_service.filter_type == "AND"
    assert ds2_service.search_query["formula"] == ""
    assert ds2_service.table_id == table.id
    assert ds2_service.view_id == view.id
    assert ds2_service.field_id == number_field.id

    widgets = Widget.objects.filter(dashboard=dashboard)
    assert widgets.count() == 2
    widget1 = widgets[0].specific
    assert widget1.content_type == ContentType.objects.get_for_model(SummaryWidget)
    assert widget1.title == "Widget 1"
    assert widget1.description == "Description 1"
    assert widget1.order == Decimal("1.0")
    assert widget1.data_source.id == ds1.id

    widget2 = widgets[1].specific
    assert widget1.content_type == ContentType.objects.get_for_model(SummaryWidget)
    assert widget2.title == "Widget 2"
    assert widget2.description == "Description 2"
    assert widget2.order == Decimal("2.0")
    assert widget2.data_source.id == ds2.id

    assert progress.progress == 100


@pytest.mark.django_db()
def test_dashboard_permanently_delete(data_fixture, settings):
    settings.HOURS_UNTIL_TRASH_PERMANENTLY_DELETED = 0
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    number_field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)
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
    dashboard_widget = WidgetService().create_widget(
        user, "summary", dashboard.id, title="Widget 1", description="Description 1"
    )
    service_type = service_type_registry.get_by_model(
        dashboard_widget.data_source.service.specific_class
    )
    DashboardDataSourceService().update_data_source(
        user,
        dashboard_widget.data_source.id,
        service_type,
        table_id=table.id,
        view_id=view.id,
        field_id=number_field.id,
        aggregation_type="sum",
    )

    TrashHandler.trash(user, workspace, None, trash_item=dashboard)
    TrashHandler.mark_old_trash_for_permanent_deletion()
    TrashHandler.permanently_delete_marked_trash()

    assert Dashboard.objects_and_trash.count() == 0

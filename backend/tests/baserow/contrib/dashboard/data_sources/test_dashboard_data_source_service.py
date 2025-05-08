from unittest.mock import patch

from django.http import HttpRequest

import pytest

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
)
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.exceptions import PermissionException
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_get_data_source(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source(user=user)

    assert (
        DashboardDataSourceService().get_data_source(user, data_source.id).id
        == data_source.id
    )


@pytest.mark.django_db
def test_get_data_source_does_not_exist(data_fixture):
    user = data_fixture.create_user()

    with pytest.raises(DashboardDataSourceDoesNotExist):
        assert DashboardDataSourceService().get_data_source(user, 0)


@pytest.mark.django_db
def test_get_data_source_permission_denied(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source()

    with pytest.raises(PermissionException):
        DashboardDataSourceService().get_data_source(user, data_source.id)


@pytest.mark.django_db
def test_get_data_source_trashed(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source(user=user, trashed=True)

    assert data_source.trashed is True

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().get_data_source(user, data_source.id)


@pytest.mark.django_db
def test_get_data_source_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    data_source = data_fixture.create_dashboard_data_source(dashboard=dashboard)

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().get_data_source(user, data_source.id)


@pytest.mark.django_db
def test_get_data_sources(data_fixture, stub_check_permissions):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_source1 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user
    )
    data_source2 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user
    )
    data_source3 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, user=user
        )
    )

    assert DashboardDataSource.objects.count() == 3
    assert Service.objects.count() == 3

    assert [
        p.id for p in DashboardDataSourceService().get_data_sources(user, dashboard.id)
    ] == [
        data_source1.id,
        data_source2.id,
        data_source3.id,
    ]

    def exclude_data_source_1(
        actor,
        operation_name,
        queryset,
        workspace=None,
        context=None,
    ):
        return queryset.exclude(id=data_source1.id)

    with stub_check_permissions() as stub:
        stub.filter_queryset = exclude_data_source_1

        assert [
            p.id
            for p in DashboardDataSourceService().get_data_sources(user, dashboard.id)
        ] == [
            data_source2.id,
            data_source3.id,
        ]


@pytest.mark.django_db
def test_get_data_sources_trashed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_source1 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user
    )
    data_source2 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user, trashed=True
    )
    data_source3 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, user=user, trashed=True
        )
    )

    assert [
        p.id for p in DashboardDataSourceService().get_data_sources(user, dashboard.id)
    ] == [
        data_source1.id,
    ]


@pytest.mark.django_db
def test_get_data_sources_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, trashed=True
    )
    data_source1 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user
    )
    data_source2 = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard, user=user
    )

    with pytest.raises(DashboardDoesNotExist):
        DashboardDataSourceService().get_data_sources(user, dashboard.id)


@pytest.mark.django_db
@patch("baserow.contrib.dashboard.data_sources.service.dashboard_data_source_deleted")
def test_delete_data_source(dashboard_data_source_deleted, data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source(user=user)

    service = DashboardDataSourceService()
    service.delete_data_source(user, data_source.id)

    assert DashboardDataSource.objects.count() == 0

    dashboard_data_source_deleted.send.assert_called_once_with(
        service, data_source_id=data_source.id, user=user
    )


@pytest.mark.django_db
def test_delete_data_source_permission_denied(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source()

    with pytest.raises(PermissionException):
        DashboardDataSourceService().delete_data_source(user, data_source.id)


@pytest.mark.django_db
def test_delete_data_source_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = data_fixture.create_dashboard_data_source(
        dashboard=dashboard, trashed=True
    )

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().delete_data_source(user, data_source.id)


@pytest.mark.django_db
def test_delete_data_source_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    data_source = data_fixture.create_dashboard_data_source(dashboard=dashboard)

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().delete_data_source(user, data_source.id)


@pytest.mark.django_db
@patch("baserow.contrib.dashboard.data_sources.service.dashboard_data_source_created")
def test_create_data_source(dashboard_data_source_created, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    service = DashboardDataSourceService()
    created_data_source = service.create_data_source(
        user, dashboard.id, service_type, "My data source"
    )

    assert created_data_source.name == "My data source"
    assert created_data_source.dashboard == dashboard
    assert created_data_source.service is not None
    dashboard_data_source_created.send.assert_called_once_with(
        service, data_source=created_data_source, user=user
    )


@pytest.mark.django_db
def test_create_data_source_permission_denied(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    with pytest.raises(PermissionException):
        DashboardDataSourceService().create_data_source(
            user, dashboard.id, service_type, "My data source"
        )


@pytest.mark.django_db
def test_create_data_source_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()
    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, trashed=True
    )
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    with pytest.raises(DashboardDoesNotExist):
        DashboardDataSourceService().create_data_source(
            user, dashboard.id, service_type, "My data source"
        )


@pytest.mark.django_db
@patch("baserow.contrib.dashboard.data_sources.service.dashboard_data_source_updated")
def test_update_data_source_name(dashboard_data_source_updated, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_source = data_fixture.create_dashboard_data_source(
        dashboard=dashboard, user=user
    )

    service = DashboardDataSourceService()
    updated_data_source = service.update_data_source(
        user, data_source.id, data_source.service.get_type(), name="Updated name"
    )
    assert updated_data_source.data_source.name == "Updated name"

    dashboard_data_source_updated.send.assert_called_once_with(
        service, data_source=updated_data_source.data_source, user=user
    )


@pytest.mark.django_db
def test_update_data_source_permission_denied(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source()

    with pytest.raises(PermissionException):
        DashboardDataSourceService().update_data_source(
            user, data_source.id, data_source.service.get_type()
        )


@pytest.mark.django_db
def test_update_data_source_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = data_fixture.create_dashboard_data_source(
        name="Name 1", dashboard=dashboard, trashed=True
    )

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().update_data_source(
            user, data_source.id, data_source.service.get_type()
        )


@pytest.mark.django_db
def test_update_data_source_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    data_source = data_fixture.create_dashboard_data_source(
        name="Name 1", dashboard=dashboard
    )

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().update_data_source(
            user, data_source.id, data_source.service.get_type()
        )


@pytest.mark.django_db
def test_dispatch_data_source(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    RowHandler().create_rows(
        user,
        table,
        [
            {f"field_{field.id}": 10},
            {f"field_{field.id}": 20},
            {f"field_{field.id}": 30},
        ],
    )
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        authorized_user=user, application=dashboard
    )
    service = data_fixture.create_local_baserow_aggregate_rows_service(
        integration=integration, table=table, field=field, aggregation_type="sum"
    )
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1", user=user, dashboard=dashboard, service=service
        )
    )
    widget = data_fixture.create_summary_widget(
        dashboard=dashboard, data_source=data_source
    )
    dispatch_context = DashboardDispatchContext(HttpRequest(), widget)

    result = DashboardDataSourceService().dispatch_data_source(
        user, data_source.id, dispatch_context
    )

    assert result == {f"result": 60}


@pytest.mark.django_db
def test_dispatch_data_source_permissions_denied(data_fixture):
    user = data_fixture.create_user()
    data_source = data_fixture.create_dashboard_data_source(name="Name 1")
    dispatch_context = DashboardDispatchContext(HttpRequest())

    with pytest.raises(PermissionException):
        DashboardDataSourceService().dispatch_data_source(
            user, data_source.id, dispatch_context
        )


@pytest.mark.django_db
def test_dispatch_data_source_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user)
    data_source = data_fixture.create_dashboard_data_source(
        name="Name 1", dashboard=dashboard, trashed=True
    )
    dispatch_context = DashboardDispatchContext(HttpRequest())

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().dispatch_data_source(
            user, data_source.id, dispatch_context
        )


@pytest.mark.django_db
def test_dispatch_data_source_dashboard_trashed(data_fixture):
    user = data_fixture.create_user()
    dashboard = data_fixture.create_dashboard_application(user=user, trashed=True)
    data_source = data_fixture.create_dashboard_data_source(
        name="Name 1", dashboard=dashboard
    )
    dispatch_context = DashboardDispatchContext(HttpRequest())

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceService().dispatch_data_source(
            user, data_source.id, dispatch_context
        )

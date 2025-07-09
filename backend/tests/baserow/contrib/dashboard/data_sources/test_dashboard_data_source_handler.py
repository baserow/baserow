from django.db import DatabaseError, connections, transaction
from django.db.models import QuerySet
from django.http import HttpRequest

import pytest

from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.models import DashboardDataSource
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowAggregateRows
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_get_data_source(data_fixture, django_assert_num_queries):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )

    fetched_data_source = DashboardDataSourceHandler().get_data_source(
        data_source_id=data_source.id
    )

    with django_assert_num_queries(0):
        fetched_data_source.dashboard.id
        fetched_data_source.dashboard.workspace.id
        fetched_data_source.service.id

    assert fetched_data_source == data_source


@pytest.mark.django_db
def test_get_data_source_does_not_exist(data_fixture):
    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceHandler().get_data_source(data_source_id=999)


@pytest.mark.django_db
def test_get_data_source_with_base_queryset(data_fixture):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 2"
        )
    )
    base_queryset = DashboardDataSource.objects.filter(name="Name 1")

    fetched_data_source = DashboardDataSourceHandler().get_data_source(
        data_source.id, base_queryset
    )
    assert fetched_data_source == data_source

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceHandler().get_data_source(data_source_2.id, base_queryset)


@pytest.mark.django_db
def test_get_data_sources(data_fixture, django_assert_num_queries):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 2"
        )
    )
    data_source_other_dashboard = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard_2, name="Data source dashboard 2"
        )
    )

    data_sources: list = DashboardDataSourceHandler().get_data_sources(
        dashboard, return_specific_services=False
    )
    assert len(data_sources) == 2

    with django_assert_num_queries(0):
        assert data_sources[0].name == data_source.name
        assert data_sources[0].dashboard.id == data_source.dashboard.id
        assert data_sources[0].order == data_source.order
        assert data_sources[0].service.id == data_source.service.id
        assert isinstance(data_sources[0].service, Service)
        assert data_sources[1].name == data_source_2.name
        assert data_sources[1].dashboard.id == data_source_2.dashboard.id
        assert data_sources[1].order == data_source_2.order
        assert data_sources[1].service.id == data_source_2.service.id
        assert isinstance(data_sources[1].service, Service)
        data_sources[0].dashboard.workspace.id
        data_sources[0].service.integration.id
        data_sources[0].service.integration.application.id


@pytest.mark.django_db
def test_get_data_sources_specific_services(data_fixture, django_assert_num_queries):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 2"
        )
    )
    data_source_other_dashboard = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard_2, name="Data source dashboard 2"
        )
    )

    data_sources: QuerySet = DashboardDataSourceHandler().get_data_sources(
        dashboard, return_specific_services=True
    )
    assert len(data_sources) == 2

    with django_assert_num_queries(0):
        assert data_sources[0].name == data_source.name
        assert data_sources[0].dashboard.id == data_source.dashboard.id
        assert data_sources[0].order == data_source.order
        assert data_sources[0].service.id == data_source.service.id
        assert isinstance(data_sources[0].service, LocalBaserowAggregateRows)
        assert data_sources[1].name == data_source_2.name
        assert data_sources[1].dashboard.id == data_source_2.dashboard.id
        assert data_sources[1].order == data_source_2.order
        assert data_sources[1].service.id == data_source_2.service.id
        assert isinstance(data_sources[1].service, LocalBaserowAggregateRows)
        data_sources[0].dashboard.workspace.id
        data_sources[0].service.integration.id
        data_sources[0].service.integration.application.id


@pytest.mark.django_db
def test_get_data_sources_with_base_queryset(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    dashboard_2 = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 1"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="XYZ"
        )
    )
    data_source_3 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Different name"
        )
    )
    data_source_other_dashboard = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard_2, name="Data source dashboard 2"
        )
    )
    base_queryset = DashboardDataSource.objects.filter(name="Data source 1")

    data_sources = DashboardDataSourceHandler().get_data_sources(
        dashboard, base_queryset=base_queryset, return_specific_services=False
    )

    assert len(list(data_sources)) == 1


@pytest.mark.django_db(transaction=True, databases=["default", "default-copy"])
def test_get_data_source_for_update(data_fixture):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )

    with transaction.atomic():
        fetched_data_source = DashboardDataSourceHandler().get_data_source_for_update(
            data_source_id=data_source.id
        )

        with pytest.raises(DatabaseError):
            connections["default-copy"]
            DashboardDataSource.objects.using("default-copy").select_for_update(
                nowait=True
            ).get(id=data_source.id)

    assert fetched_data_source == data_source


@pytest.mark.django_db
def test_get_data_source_for_update_does_not_exist(data_fixture):
    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceHandler().get_data_source_for_update(data_source_id=999)


@pytest.mark.django_db
def test_get_data_source_for_update_with_base_queryset(data_fixture):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )
    data_source_2 = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 2"
        )
    )
    base_queryset = DashboardDataSource.objects.filter(name="Name 1")

    fetched_data_source = DashboardDataSourceHandler().get_data_source_for_update(
        data_source.id, base_queryset
    )
    assert fetched_data_source == data_source

    with pytest.raises(DashboardDataSourceDoesNotExist):
        DashboardDataSourceHandler().get_data_source_for_update(
            data_source_2.id, base_queryset
        )


@pytest.mark.django_db
def test_find_unused_data_source_name(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    service_type = service_type_registry.get("local_baserow_aggregate_rows")
    data_source = DashboardDataSourceHandler().create_data_source(
        dashboard=dashboard, name="Data source", service_type=service_type
    )
    data_source2 = DashboardDataSourceHandler().create_data_source(
        dashboard=dashboard, name="Data source 2", service_type=service_type
    )
    data_source3 = DashboardDataSourceHandler().create_data_source(
        dashboard=dashboard, name="Data source 3", service_type=service_type
    )

    result = DashboardDataSourceHandler().find_unused_data_source_name(
        dashboard, "Data source"
    )

    assert result == "Data source 4"


@pytest.mark.django_db
def test_create_data_source(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    service_type = service_type_registry.get("local_baserow_aggregate_rows")

    data_source = DashboardDataSourceHandler().create_data_source(
        dashboard=dashboard, name="Data source", service_type=service_type
    )

    assert data_source.dashboard.id == dashboard.id
    assert data_source.order == 1
    assert isinstance(data_source.service, LocalBaserowAggregateRows)
    assert data_source.name == "Data source"
    assert DashboardDataSource.objects.count() == 1


@pytest.mark.django_db
def test_update_data_source_name(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, name="Data source 1"
        )
    )

    updated_data_source = DashboardDataSourceHandler().update_data_source(
        data_source, name="Renamed", service_type=data_source.service.get_type()
    )

    assert updated_data_source.data_source.name == "Renamed"


@pytest.mark.django_db
def test_update_data_source_change_type(data_fixture):
    dashboard = data_fixture.create_dashboard_application()
    data_source = data_fixture.create_dashboard_local_baserow_list_rows_data_source(
        dashboard=dashboard
    )
    new_service_type = service_type_registry.get("local_baserow_aggregate_rows")

    updated_data_source = DashboardDataSourceHandler().update_data_source(
        data_source, service_type=new_service_type
    )

    assert (
        service_type_registry.get_by_model(updated_data_source.data_source.service).type
        == "local_baserow_aggregate_rows"
    )


@pytest.mark.django_db
def test_delete_data_source(data_fixture):
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1"
        )
    )
    service_id = data_source.service_id
    assert DashboardDataSource.objects.count() == 1

    DashboardDataSourceHandler().delete_data_source(data_source)
    assert DashboardDataSource.objects.count() == 0
    assert Service.objects.filter(id=service_id).count() == 0


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

    result = DashboardDataSourceHandler().dispatch_data_source(
        data_source, dispatch_context
    )

    assert result == {"result": 60}


@pytest.mark.django_db
def test_dispatch_data_source_improperly_configured(data_fixture):
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
        integration=integration, table=table, field=None, aggregation_type="sum"
    )
    data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            name="Name 1", user=user, dashboard=dashboard, service=service
        )
    )
    dispatch_context = DashboardDispatchContext(HttpRequest())

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        DashboardDataSourceHandler().dispatch_data_source(data_source, dispatch_context)

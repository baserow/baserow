import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.integrations.local_baserow.models import LocalBaserowGetRow
from baserow.core.services.exceptions import (
    ServiceDoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_create_service(data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    service_type = service_type_registry.get("local_baserow_get_row")

    service = ServiceHandler().create_service(service_type, integration=integration)

    assert service.integration.id == integration.id

    assert Service.objects.count() == 1

    service = ServiceHandler().create_service(service_type)

    assert service.integration is None


@pytest.mark.django_db
def test_get_service(data_fixture):
    service = data_fixture.create_local_baserow_get_row_service()
    assert ServiceHandler().get_service(service.id).id == service.id


@pytest.mark.django_db
def test_get_service_does_not_exist(data_fixture):
    with pytest.raises(ServiceDoesNotExist):
        assert ServiceHandler().get_service(0)


@pytest.mark.django_db
def test_get_services(data_fixture):
    integration = data_fixture.create_local_baserow_integration()
    service1 = data_fixture.create_local_baserow_get_row_service(
        integration=integration
    )
    service2 = data_fixture.create_local_baserow_get_row_service(
        integration=integration
    )
    service3 = data_fixture.create_local_baserow_get_row_service(
        integration=integration
    )

    services = ServiceHandler().get_services(integration=integration)

    assert [e.id for e in services] == [
        service1.id,
        service2.id,
        service3.id,
    ]

    assert isinstance(services[0], LocalBaserowGetRow)


@pytest.mark.django_db
def test_update_service(data_fixture):
    service = data_fixture.create_local_baserow_get_row_service()
    view = data_fixture.create_grid_view()

    service_type = service_type_registry.get("local_baserow_get_row")

    search_query = "cheese"
    service_updated = ServiceHandler().update_service(
        service_type, service, view=view, search_query=search_query
    )

    assert service_updated.service.view.id == view.id
    assert service_updated.service.search_query["formula"] == search_query


@pytest.mark.django_db
def test_update_service_filters(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user,
        database,
        name="Films",
        fields=[
            ("Name", "text", {}),
            ("Rating", "rating", {}),
        ],
    )
    name_field = table.field_set.get(name="Name")
    rating_field = table.field_set.get(name="Rating")
    service = data_fixture.create_local_baserow_list_rows_service(table=table)
    service_type = service_type_registry.get("local_baserow_list_rows")

    # Create our initial 2 filters.
    ServiceHandler().update_service(
        service_type,
        service,
        service_filters=[
            {
                "field": name_field,
                "type": "equal",
                "value": "James Bond",
            },
            {
                "field": rating_field,
                "type": "equal",
                "value": "5",
            },
        ],
    )
    assert service.service_filters.count() == 2
    assert service.service_filters.filter(
        field=name_field, type="equal", value="James Bond"
    ).exists()
    assert service.service_filters.filter(
        field=rating_field, type="equal", value="5"
    ).exists()

    # Replace it with one different one.
    ServiceHandler().update_service(
        service_type,
        service,
        service_filters=[
            {
                "field": name_field,
                "type": "equal",
                "value": "Avengers",
            },
        ],
    )
    assert service.service_filters.count() == 1
    assert service.service_filters.filter(
        field=name_field, type="equal", value="Avengers"
    ).exists()

    # Replace it with none.
    ServiceHandler().update_service(
        service_type,
        service,
        service_filters=[],
    )
    assert service.service_filters.count() == 0


@pytest.mark.django_db
def test_update_service_sortings(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user,
        database,
        name="Films",
        fields=[
            ("Name", "text", {}),
            ("Rating", "rating", {}),
        ],
    )
    name_field = table.field_set.get(name="Name")
    rating_field = table.field_set.get(name="Rating")
    service = data_fixture.create_local_baserow_list_rows_service(table=table)
    service_type = service_type_registry.get("local_baserow_list_rows")

    # Create our initial 2 sortings.
    ServiceHandler().update_service(
        service_type,
        service,
        service_sorts=[
            {
                "field": name_field,
                "order_by": "ASC",
            },
            {
                "field": rating_field,
                "order_by": "DESC",
            },
        ],
    )
    assert service.service_sorts.count() == 2
    assert service.service_sorts.filter(field=name_field, order_by="ASC").exists()
    assert service.service_sorts.filter(field=rating_field, order_by="DESC").exists()

    # Replace it with one different one.
    ServiceHandler().update_service(
        service_type,
        service,
        service_sorts=[
            {
                "field": name_field,
                "order_by": "ASC",
            },
        ],
    )
    assert service.service_sorts.count() == 1
    assert service.service_sorts.filter(field=name_field, order_by="ASC").exists()

    # Replace it with none.
    ServiceHandler().update_service(
        service_type,
        service,
        service_sorts=[],
    )
    assert service.service_sorts.count() == 0


@pytest.mark.django_db
def test_update_service_invalid_values(data_fixture):
    service = data_fixture.create_local_baserow_get_row_service()

    service_type = service_type_registry.get("local_baserow_get_row")

    service_updated = ServiceHandler().update_service(
        service_type, service, nonsense="hello"
    )

    assert not hasattr(service_updated, "nonsense")


@pytest.mark.django_db
def test_delete_service(data_fixture):
    service = data_fixture.create_local_baserow_get_row_service()
    service_type = service_type_registry.get("local_baserow_get_row")

    ServiceHandler().delete_service(service_type, service)

    assert Service.objects.count() == 0


@pytest.mark.django_db
def test_dispatch_local_baserow_get_row_service_missing_integration(data_fixture):
    service = data_fixture.create_local_baserow_get_row_service(integration=None)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, {})

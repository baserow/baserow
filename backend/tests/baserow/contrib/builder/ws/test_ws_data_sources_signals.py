from unittest.mock import patch

import pytest

from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.data_sources.signals.broadcast_to_permitted_users")
def test_data_source_created(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )

    service_type = service_type_registry.get("local_baserow_list_rows")
    data_source = DataSourceService().create_data_source(
        user=user,
        page=page,
        service_type=service_type,
        integration=integration,
        table=table,
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "data_source_created"
    assert args[0][4]["data_source"]["id"] == data_source.id
    assert args[0][4]["data_source"]["page_id"] == page.id
    assert args[0][4]["before_id"] is None


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.data_sources.signals.broadcast_to_permitted_users")
def test_data_source_created_before(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    existing_data_source = data_fixture.create_builder_data_source(page=page)

    service_type = service_type_registry.get("local_baserow_list_rows")
    data_source = DataSourceService().create_data_source(
        user=user,
        page=page,
        service_type=service_type,
        before=existing_data_source,
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args
    assert args[0][4]["type"] == "data_source_created"
    assert args[0][4]["data_source"]["id"] == data_source.id
    assert args[0][4]["before_id"] == existing_data_source.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.data_sources.signals.broadcast_to_permitted_users")
def test_data_source_updated(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )

    service_type = service_type_registry.get("local_baserow_list_rows")
    DataSourceService().update_data_source(
        user=user,
        data_source=data_source,
        service_type=service_type,
        name="Updated name",
    )

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "data_source_updated"
    assert args[0][4]["data_source"]["id"] == data_source.id
    assert args[0][4]["data_source"]["name"] == "Updated name"


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.data_sources.signals.broadcast_to_permitted_users")
def test_data_source_deleted(mock_broadcast_to_permitted_users, data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page
    )
    data_source_id = data_source.id

    DataSourceService().delete_data_source(user=user, data_source=data_source)

    mock_broadcast_to_permitted_users.delay.assert_called_once()
    args = mock_broadcast_to_permitted_users.delay.call_args

    assert args[0][4]["type"] == "data_source_deleted"
    assert args[0][4]["data_source_id"] == data_source_id
    assert args[0][4]["page_id"] == page.id

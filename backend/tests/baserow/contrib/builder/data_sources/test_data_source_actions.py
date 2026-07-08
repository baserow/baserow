import uuid

import pytest

from baserow.contrib.builder.action_scopes import (
    PageActionScopeType,
    SharedPageActionScopeType,
)
from baserow.contrib.builder.data_sources.actions import (
    CreateDataSourceActionType,
    DeleteDataSourceActionType,
    MoveDataSourceActionType,
    UpdateDataSourceActionType,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.core.action.handler import ActionHandler
from baserow.core.services.registries import service_type_registry


def _scope(page):
    return [PageActionScopeType.value(page.id)]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_data_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("local_baserow_get_row")

    data_source = CreateDataSourceActionType.do(
        user, page, service_type=service_type, name="DS"
    )

    assert DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert not DataSource.objects.filter(id=data_source.id).exists()
    assert DataSource.trash.filter(id=data_source.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_data_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, page=page
    )

    DeleteDataSourceActionType.do(user, data_source)
    assert not DataSource.objects.filter(id=data_source.id).exists()
    assert DataSource.trash.filter(id=data_source.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert not DataSource.objects.filter(id=data_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_data_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, page=page, name="Original"
    )
    service_type = service_type_registry.get("local_baserow_get_row")

    ds_for_update = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_for_update, service_type=service_type, name="Updated"
    )

    data_source.refresh_from_db()
    assert data_source.name == "Updated"

    ActionHandler.undo(user, _scope(page), session_id)
    data_source.refresh_from_db()
    assert data_source.name == "Original"

    ActionHandler.redo(user, _scope(page), session_id)
    data_source.refresh_from_db()
    assert data_source.name == "Updated"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_share_data_source_undo_redo(data_fixture):
    """Toggling a data source as shared moves it to the builder's shared page; that
    move must be reverted on undo."""

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    shared_page = PageHandler().get_shared_page(builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page
    )
    service_type = service_type_registry.get("local_baserow_get_row")

    # The editor sends both the content page and shared page scopes.
    scopes = [
        PageActionScopeType.value(page.id),
        SharedPageActionScopeType.value(shared_page.id),
    ]

    ds_for_update = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_for_update, service_type=service_type, page=shared_page
    )

    data_source.refresh_from_db()
    assert data_source.page_id == shared_page.id

    ActionHandler.undo(user, scopes, session_id)
    data_source.refresh_from_db()
    assert data_source.page_id == page.id

    ActionHandler.redo(user, scopes, session_id)
    data_source.refresh_from_db()
    assert data_source.page_id == shared_page.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_data_source_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    ds1 = data_fixture.create_builder_local_baserow_get_row_data_source(page=page)
    ds2 = data_fixture.create_builder_local_baserow_get_row_data_source(page=page)
    ds3 = data_fixture.create_builder_local_baserow_get_row_data_source(page=page)

    def order():
        return list(
            DataSource.objects.filter(page=page)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    assert order() == [ds1.id, ds2.id, ds3.id]

    # Move ds3 before ds2 → [ds1, ds3, ds2]
    ds3_for_update = DataSourceHandler().get_data_source_for_update(ds3.id)
    MoveDataSourceActionType.do(user, ds3_for_update, before=ds2)
    assert order() == [ds1.id, ds3.id, ds2.id]

    ActionHandler.undo(user, _scope(page), session_id)
    assert order() == [ds1.id, ds2.id, ds3.id]

    ActionHandler.redo(user, _scope(page), session_id)
    assert order() == [ds1.id, ds3.id, ds2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_reassign_integration_undo_with_trashed_integration(data_fixture):
    # Reassigning a data source whose current integration is trashed, then undoing
    # that reassignment (which restores the still-trashed integration_id), must not
    # raise.
    from baserow.core.integrations.handler import IntegrationHandler
    from baserow.core.integrations.service import IntegrationService

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, page=page
    )
    integration1 = IntegrationHandler().get_integration(
        data_source.service.integration_id
    )
    integration2 = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    service_type = service_type_registry.get("local_baserow_get_row")

    IntegrationService().delete_integration(user, integration1)

    # Forward reassign to integration2 (current integration is trashed).
    ds_for_update = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_for_update, service_type=service_type, integration_id=integration2.id
    )
    data_source.service.refresh_from_db()
    assert data_source.service.integration_id == integration2.id

    # Undo restores the (still trashed) integration1 without raising; the data
    # source points back at integration1's id and will heal once it's restored.
    ActionHandler.undo(user, [PageActionScopeType.value(page.id)], session_id)
    data_source.service.refresh_from_db()
    assert data_source.service.integration_id == integration1.id

    # Redo re-applies integration2.
    ActionHandler.redo(user, [PageActionScopeType.value(page.id)], session_id)
    data_source.service.refresh_from_db()
    assert data_source.service.integration_id == integration2.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_configure_table_undo_then_redo(data_fixture):
    # Create a data source, configure its table, undo (table cleared), redo
    # (table reapplied). The redo must find the data source.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    table, _, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["A"]]
    )
    service_type = service_type_registry.get("local_baserow_list_rows")

    data_source = CreateDataSourceActionType.do(
        user, page, service_type=service_type, integration_id=integration.id
    )

    ds_for_update = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_for_update, service_type=service_type, table_id=table.id
    )
    data_source.service.refresh_from_db()
    assert data_source.service.table_id == table.id

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()
    data_source.service.refresh_from_db()
    assert data_source.service.table_id is None

    ActionHandler.redo(user, _scope(page), session_id)
    data_source.service.refresh_from_db()
    assert data_source.service.table_id == table.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_and_configure_grouped_undo_then_redo(data_fixture):
    # The frontend batches the create + configuration into one action group.
    # Undoing the group trashes the data source (create undone); redoing it must
    # restore the data source before re-applying the configuration update.
    import uuid as _uuid

    session_id = "session-id"
    action_group = _uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    table, _, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["A"]]
    )
    service_type = service_type_registry.get("local_baserow_list_rows")

    data_source = CreateDataSourceActionType.do(
        user, page, service_type=service_type, integration_id=integration.id
    )
    ds_for_update = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_for_update, service_type=service_type, table_id=table.id
    )

    ActionHandler.undo(user, _scope(page), session_id)
    assert not DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()
    fresh = DataSourceHandler().get_data_source(data_source.id)
    assert fresh.service.table_id == table.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_then_integration_then_table_single_undo_redo(data_fixture):
    # Exact flow: create, choose integration, choose table as three separate
    # actions, then one undo (revert table) and one redo (reapply table).
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    table, _, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["A"]]
    )
    service_type = service_type_registry.get("local_baserow_list_rows")

    data_source = CreateDataSourceActionType.do(user, page, service_type=service_type)
    ds_fu = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_fu, service_type=service_type, integration_id=integration.id
    )
    ds_fu = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_fu, service_type=service_type, table_id=table.id
    )

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()
    DataSourceHandler().get_data_source(data_source.id).service.table_id is None

    ActionHandler.redo(user, _scope(page), session_id)
    fresh = DataSourceHandler().get_data_source(data_source.id)
    assert fresh.service.table_id == table.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_data_source_create_configure_delete_undo_redo(data_fixture):
    # create -> configure (integration + table) -> delete -> undo (restore) ->
    # redo (re-delete) -> undo (restore again).
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    table, _, _ = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[["A"]]
    )
    service_type = service_type_registry.get("local_baserow_list_rows")

    data_source = CreateDataSourceActionType.do(
        user, page, service_type=service_type, integration_id=integration.id
    )
    ds_fu = DataSourceHandler().get_data_source_for_update(data_source.id)
    UpdateDataSourceActionType.do(
        user, ds_fu, service_type=service_type, table_id=table.id
    )

    ds_fu = DataSourceHandler().get_data_source_for_update(data_source.id)
    DeleteDataSourceActionType.do(user, ds_fu)
    assert not DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()
    fresh = DataSourceHandler().get_data_source(data_source.id)
    assert fresh.service.table_id == table.id

    ActionHandler.redo(user, _scope(page), session_id)
    assert not DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_data_source_delete_with_trashed_integration_undo_redo(data_fixture):
    # A data source whose integration is trashed can still be deleted and the
    # delete undone/redone without raising.
    from baserow.core.integrations.service import IntegrationService

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user, page=page
    )
    integration = data_source.service.integration

    IntegrationService().delete_integration(user, integration)

    ds_fu = DataSourceHandler().get_data_source_for_update(data_source.id)
    DeleteDataSourceActionType.do(user, ds_fu)
    assert not DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert DataSource.objects.filter(id=data_source.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert not DataSource.objects.filter(id=data_source.id).exists()

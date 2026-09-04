import uuid

import pytest

from baserow.core.action.handler import ActionHandler
from baserow.core.action.scopes import ApplicationActionScopeType
from baserow.core.integrations.actions import (
    CreateIntegrationActionType,
    DeleteIntegrationActionType,
    MoveIntegrationActionType,
    UpdateIntegrationActionType,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import integration_type_registry


def _scope(application):
    return [ApplicationActionScopeType.value(application.id)]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_integration_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    integration = CreateIntegrationActionType.do(
        user, integration_type, application, name="Integration"
    )

    assert Integration.objects.filter(id=integration.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert not Integration.objects.filter(id=integration.id).exists()
    assert Integration.trash.filter(id=integration.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_integration_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=application
    )

    DeleteIntegrationActionType.do(user, integration)
    assert not Integration.objects.filter(id=integration.id).exists()
    assert Integration.trash.filter(id=integration.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert Integration.objects.filter(id=integration.id).exists()

    ActionHandler.redo(user, _scope(application), session_id)
    assert not Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_integration_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=application, name="Original"
    )

    integration_for_update = IntegrationHandler().get_integration_for_update(
        integration.id
    )
    UpdateIntegrationActionType.do(user, integration_for_update, name="Updated")

    integration.refresh_from_db()
    assert integration.name == "Updated"

    ActionHandler.undo(user, _scope(application), session_id)
    integration.refresh_from_db()
    assert integration.name == "Original"

    ActionHandler.redo(user, _scope(application), session_id)
    integration.refresh_from_db()
    assert integration.name == "Updated"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_move_integration_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    i1 = data_fixture.create_local_baserow_integration(application=application)
    i2 = data_fixture.create_local_baserow_integration(application=application)
    i3 = data_fixture.create_local_baserow_integration(application=application)

    def order():
        return list(
            Integration.objects.filter(application=application)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    assert order() == [i1.id, i2.id, i3.id]

    # Move i3 before i2 → [i1, i3, i2]
    i3_for_update = IntegrationHandler().get_integration_for_update(i3.id)
    MoveIntegrationActionType.do(user, i3_for_update, before=i2)
    assert order() == [i1.id, i3.id, i2.id]

    ActionHandler.undo(user, _scope(application), session_id)
    assert order() == [i1.id, i2.id, i3.id]

    ActionHandler.redo(user, _scope(application), session_id)
    assert order() == [i1.id, i3.id, i2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_integration_create_configure_undo_redo(data_fixture):
    # create -> configure (rename) -> undo (name reverts) -> redo (name reapplied)
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    integration = CreateIntegrationActionType.do(
        user, integration_type, application, name="Original"
    )

    ifu = IntegrationHandler().get_integration_for_update(integration.id)
    UpdateIntegrationActionType.do(user, ifu, name="Configured")
    integration.refresh_from_db()
    assert integration.name == "Configured"

    # Undo the rename.
    ActionHandler.undo(user, _scope(application), session_id)
    integration.refresh_from_db()
    assert integration.name == "Original"

    # Redo the rename.
    ActionHandler.redo(user, _scope(application), session_id)
    integration.refresh_from_db()
    assert integration.name == "Configured"

    # Undo rename, then undo create -> integration trashed.
    ActionHandler.undo(user, _scope(application), session_id)
    ActionHandler.undo(user, _scope(application), session_id)
    assert not Integration.objects.filter(id=integration.id).exists()

    # Redo create (restore), then redo rename.
    ActionHandler.redo(user, _scope(application), session_id)
    assert Integration.objects.filter(id=integration.id).exists()
    ActionHandler.redo(user, _scope(application), session_id)
    integration.refresh_from_db()
    assert integration.name == "Configured"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_integration_create_configure_delete_undo_redo(data_fixture):
    # create -> configure -> delete -> undo (restore) -> redo (re-delete)
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    application = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    integration = CreateIntegrationActionType.do(
        user, integration_type, application, name="A"
    )
    ifu = IntegrationHandler().get_integration_for_update(integration.id)
    UpdateIntegrationActionType.do(user, ifu, name="B")

    ifu = IntegrationHandler().get_integration_for_update(integration.id)
    DeleteIntegrationActionType.do(user, ifu)
    assert not Integration.objects.filter(id=integration.id).exists()

    ActionHandler.undo(user, _scope(application), session_id)
    assert Integration.objects.filter(id=integration.id).exists()
    integration.refresh_from_db()
    assert integration.name == "B"

    ActionHandler.redo(user, _scope(application), session_id)
    assert not Integration.objects.filter(id=integration.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_integration_grouped_create_configure_undo_redo(data_fixture):
    # The frontend may batch create + configure into one action group.
    session_id = "session-id"
    action_group = uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    application = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    integration = CreateIntegrationActionType.do(
        user, integration_type, application, name="Original"
    )
    ifu = IntegrationHandler().get_integration_for_update(integration.id)
    UpdateIntegrationActionType.do(user, ifu, name="Configured")

    # Undo the whole group -> integration removed.
    ActionHandler.undo(user, _scope(application), session_id)
    assert not Integration.objects.filter(id=integration.id).exists()

    # Redo the whole group -> restored and configured.
    ActionHandler.redo(user, _scope(application), session_id)
    assert Integration.objects.filter(id=integration.id).exists()
    integration.refresh_from_db()
    assert integration.name == "Configured"

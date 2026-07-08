import uuid

import pytest

from baserow.contrib.builder.action_scopes import PageActionScopeType
from baserow.contrib.builder.workflow_actions.actions import (
    CreateBuilderWorkflowActionActionType,
    DeleteBuilderWorkflowActionActionType,
    OrderBuilderWorkflowActionsActionType,
    UpdateBuilderWorkflowActionActionType,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    EventTypes,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.action.handler import ActionHandler


def _scope(page):
    return [PageActionScopeType.value(page.id)]


def _notification_type():
    return builder_workflow_action_type_registry.get("notification")


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_create_workflow_action_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action = CreateBuilderWorkflowActionActionType.do(
        user,
        _notification_type(),
        page,
        element_id=element.id,
        event=EventTypes.CLICK.value,
    )

    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()
    assert BuilderWorkflowAction.trash.filter(id=workflow_action.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_delete_workflow_action_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value
    )

    DeleteBuilderWorkflowActionActionType.do(user, workflow_action)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()
    assert BuilderWorkflowAction.trash.filter(id=workflow_action.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_workflow_action_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value, title="'Original'"
    )

    workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
        workflow_action.id
    )
    UpdateBuilderWorkflowActionActionType.do(user, workflow_action, title="'Updated'")

    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Updated'"

    ActionHandler.undo(user, _scope(page), session_id)
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Original'"

    ActionHandler.redo(user, _scope(page), session_id)
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Updated'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_order_workflow_actions_action(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    wa1 = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value, order=1
    )
    wa2 = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value, order=2
    )
    wa3 = data_fixture.create_notification_workflow_action(
        page=page, element=element, event=EventTypes.CLICK.value, order=3
    )

    def order():
        return list(
            BuilderWorkflowAction.objects.filter(page=page, element=element)
            .order_by("order", "id")
            .values_list("id", flat=True)
        )

    assert order() == [wa1.id, wa2.id, wa3.id]

    OrderBuilderWorkflowActionsActionType.do(
        user, page, [wa3.id, wa1.id, wa2.id], element=element
    )
    assert order() == [wa3.id, wa1.id, wa2.id]

    ActionHandler.undo(user, _scope(page), session_id)
    assert order() == [wa1.id, wa2.id, wa3.id]

    ActionHandler.redo(user, _scope(page), session_id)
    assert order() == [wa3.id, wa1.id, wa2.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_workflow_action_create_configure_undo_redo(data_fixture):
    # create -> configure (title) -> undo (title reverts) -> redo -> undo both
    # (trashed) -> redo both (restored & configured).
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action = CreateBuilderWorkflowActionActionType.do(
        user,
        _notification_type(),
        page,
        element_id=element.id,
        event=EventTypes.CLICK.value,
        title="'Original'",
    )

    wa = BuilderWorkflowActionHandler().get_workflow_action(workflow_action.id)
    UpdateBuilderWorkflowActionActionType.do(user, wa, title="'Configured'")
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Configured'"

    ActionHandler.undo(user, _scope(page), session_id)
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Original'"

    ActionHandler.redo(user, _scope(page), session_id)
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Configured'"

    # Undo the rename, then undo the create -> action trashed.
    ActionHandler.undo(user, _scope(page), session_id)
    ActionHandler.undo(user, _scope(page), session_id)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    # Redo the create (restore), then redo the rename.
    ActionHandler.redo(user, _scope(page), session_id)
    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()
    ActionHandler.redo(user, _scope(page), session_id)
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Configured'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_workflow_action_create_configure_delete_undo_redo(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action = CreateBuilderWorkflowActionActionType.do(
        user,
        _notification_type(),
        page,
        element_id=element.id,
        event=EventTypes.CLICK.value,
        title="'A'",
    )
    wa = BuilderWorkflowActionHandler().get_workflow_action(workflow_action.id)
    UpdateBuilderWorkflowActionActionType.do(user, wa, title="'B'")

    wa = BuilderWorkflowActionHandler().get_workflow_action(workflow_action.id)
    DeleteBuilderWorkflowActionActionType.do(user, wa)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'B'"

    ActionHandler.redo(user, _scope(page), session_id)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_workflow_action_grouped_create_configure_undo_redo(data_fixture):
    # The frontend may batch create + configure into one action group.
    session_id = "session-id"
    action_group = uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)

    workflow_action = CreateBuilderWorkflowActionActionType.do(
        user,
        _notification_type(),
        page,
        element_id=element.id,
        event=EventTypes.CLICK.value,
        title="'Original'",
    )
    wa = BuilderWorkflowActionHandler().get_workflow_action(workflow_action.id)
    UpdateBuilderWorkflowActionActionType.do(user, wa, title="'Configured'")

    ActionHandler.undo(user, _scope(page), session_id)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    ActionHandler.redo(user, _scope(page), session_id)
    assert BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()
    workflow_action.refresh_from_db()
    assert workflow_action.title["formula"] == "'Configured'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_service_workflow_action_delete_undo_redo_preserves_service(data_fixture):
    # A service-backed action's underlying service must survive trash + restore.
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    page = data_fixture.create_builder_page(user=user)
    element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        user=user, page=page, element=element, event=EventTypes.CLICK.value
    )
    service_id = workflow_action.service_id
    assert service_id is not None

    wa = BuilderWorkflowActionHandler().get_workflow_action(workflow_action.id)
    DeleteBuilderWorkflowActionActionType.do(user, wa)
    assert not BuilderWorkflowAction.objects.filter(id=workflow_action.id).exists()

    ActionHandler.undo(user, _scope(page), session_id)
    workflow_action = BuilderWorkflowActionHandler().get_workflow_action(
        workflow_action.id
    )
    # The service reference is intact after restore.
    assert workflow_action.service_id == service_id

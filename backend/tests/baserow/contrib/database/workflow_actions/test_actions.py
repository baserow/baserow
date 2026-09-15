import json
import uuid

import pytest

from baserow.api.sessions import set_client_undo_redo_action_group_id
from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.contrib.database.workflow_actions.actions import (
    CreateDatabaseWorkflowActionActionType,
    DeleteDatabaseWorkflowActionActionType,
    OrderDatabaseWorkflowActionsActionType,
    UpdateDatabaseWorkflowActionActionType,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.services.models import Service


def _url(formula):
    return {"mode": "simple", "version": "0.1", "formula": formula}


def _setup(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    return user, session_id, table, button_field


def _scope(table):
    return [TableActionScopeType.value(table.id)]


def _ids(button_field):
    return list(
        DatabaseWorkflowAction.objects.filter(field=button_field)
        .order_by("order", "id")
        .values_list("id", flat=True)
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_create_trashes_the_action_and_redo_restores_it(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)

    action = CreateDatabaseWorkflowActionActionType.do(
        user,
        database_workflow_action_type_registry.get("local_baserow_create_row"),
        button_field,
    )
    service_id = action.service_id

    ActionHandler.undo(user, _scope(table), session_id)
    assert not DatabaseWorkflowAction.objects.filter(id=action.id).exists()
    assert DatabaseWorkflowAction.trash.filter(id=action.id).exists()

    ActionHandler.redo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert restored.service_id == service_id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_delete_restores_the_action_with_its_service(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()

    DeleteDatabaseWorkflowActionActionType.do(user, action)
    assert not DatabaseWorkflowAction.objects.filter(id=action.id).exists()

    ActionHandler.undo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert restored.service_id == service.id
    assert restored.service.specific.table_id == table.id

    ActionHandler.redo(user, _scope(table), session_id)
    assert not DatabaseWorkflowAction.objects.filter(id=action.id).exists()
    assert Service.objects.filter(id=service.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_an_update_puts_the_old_values_back(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url=_url("'https://before'")
    )

    UpdateDatabaseWorkflowActionActionType.do(
        user, action, url=_url("'https://after'"), target="blank"
    )

    ActionHandler.undo(user, _scope(table), session_id)
    action.refresh_from_db()
    assert action.url["formula"] == "'https://before'"
    assert action.target == "self"

    ActionHandler.redo(user, _scope(table), session_id)
    action.refresh_from_db()
    assert action.url["formula"] == "'https://after'"
    assert action.target == "blank"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_type_change_swaps_the_type_and_its_service_back(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()

    UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    assert isinstance(
        DatabaseWorkflowActionHandler().get_workflow_action(action.id),
        LocalBaserowDeleteRowWorkflowAction,
    )

    ActionHandler.undo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert isinstance(restored, LocalBaserowCreateRowWorkflowAction)
    assert restored.service.specific.table_id == table.id
    assert _ids(button_field) == [action.id]

    ActionHandler.redo(user, _scope(table), session_id)
    assert isinstance(
        DatabaseWorkflowActionHandler().get_workflow_action(action.id),
        LocalBaserowDeleteRowWorkflowAction,
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_an_http_actions_headers_never_reach_the_action_log(data_fixture):
    """
    An HTTP action keeps its API keys in its headers, and the logged values are
    copied into the audit log, so they are left out and undo leaves them alone.
    """

    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    action = CoreHTTPRequestWorkflowAction.objects.get(pk=action.pk)
    action.service.specific.headers.create(
        key="Authorization", value=_url("'Bearer old-secret'")
    )

    UpdateDatabaseWorkflowActionActionType.do(
        user,
        action,
        service={
            "url": _url("'https://after'"),
            "headers": [{"key": "Authorization", "value": _url("'Bearer new-secret'")}],
        },
    )

    logged = json.dumps(
        Action.objects.get(type="update_database_workflow_action").params
    )
    assert "secret" not in logged
    assert "headers" not in logged

    ActionHandler.undo(user, _scope(table), session_id)
    service = DatabaseWorkflowActionHandler().get_workflow_action(action.id).service
    service = service.specific
    assert service.url["formula"] == ""
    assert [header.value["formula"] for header in service.headers.all()] == [
        "'Bearer new-secret'"
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_no_sensitive_service_field_reaches_the_action_log(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    action = CoreSMTPEmailWorkflowAction.objects.get(pk=action.pk)
    service_type = action.service.specific.get_type()

    values = action.get_type().export_prepared_values(action)

    assert service_type.sensitive_fields
    assert not set(values["service"]) & set(service_type.sensitive_fields)


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_an_order_puts_the_old_order_back(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    first = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    OrderDatabaseWorkflowActionsActionType.do(user, button_field, [second.id, first.id])
    assert _ids(button_field) == [second.id, first.id]

    ActionHandler.undo(user, _scope(table), session_id)
    assert _ids(button_field) == [first.id, second.id]

    ActionHandler.redo(user, _scope(table), session_id)
    assert _ids(button_field) == [second.id, first.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_save_restores_the_field_and_its_actions_together(data_fixture):
    """
    The editor saves the field and then its actions under one action group, so
    a single undo takes the whole save back (ADR 006 section 8).
    """

    user, session_id, table, button_field = _setup(data_fixture)
    kept = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url=_url("'https://before'")
    )
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))

    UpdateFieldActionType.do(user, button_field, new_type_name="button", label="After")
    UpdateDatabaseWorkflowActionActionType.do(user, kept, url=_url("'https://after'"))
    created = CreateDatabaseWorkflowActionActionType.do(
        user, database_workflow_action_type_registry.get("open_url"), button_field
    )

    ActionHandler.undo(user, _scope(table), session_id)

    button_field.refresh_from_db()
    kept.refresh_from_db()
    assert button_field.label == "Go"
    assert kept.url["formula"] == "'https://before'"
    assert _ids(button_field) == [kept.id]

    ActionHandler.redo(user, _scope(table), session_id)

    button_field.refresh_from_db()
    kept.refresh_from_db()
    assert button_field.label == "After"
    assert kept.url["formula"] == "'https://after'"
    assert _ids(button_field) == [kept.id, created.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_a_save_that_made_a_button_brings_its_actions_back(data_fixture):
    """
    Undo trashes the new action before it turns the field back into text, and
    that type change deletes the button's actions. The field's backup has to
    carry the trashed one, or redo has nothing to restore.
    """

    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Go")
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))

    button_field, _ = UpdateFieldActionType.do(
        user, field, new_type_name="button", label="Go"
    )
    action = CreateDatabaseWorkflowActionActionType.do(
        user,
        database_workflow_action_type_registry.get("open_url"),
        button_field,
        url=_url("'https://kept'"),
    )
    OrderDatabaseWorkflowActionsActionType.do(user, button_field, [action.id])

    ActionHandler.undo(user, _scope(table), session_id)
    assert not DatabaseWorkflowAction.objects_and_trash.filter(id=action.id).exists()

    ActionHandler.redo(user, _scope(table), session_id)

    assert not Action.objects.filter(error__isnull=False).exists()
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert restored.url["formula"] == "'https://kept'"
    assert _ids(restored.field) == [action.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_type_change_keeps_the_ids_older_undo_steps_name(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = CreateDatabaseWorkflowActionActionType.do(
        user, database_workflow_action_type_registry.get("open_url"), button_field
    )
    UpdateFieldActionType.do(user, button_field, new_type_name="text")

    ActionHandler.undo(user, _scope(table), session_id)
    assert DatabaseWorkflowAction.objects.filter(id=action.id).exists()

    ActionHandler.undo(user, _scope(table), session_id)
    assert not DatabaseWorkflowAction.objects.filter(id=action.id).exists()
    assert DatabaseWorkflowAction.trash.filter(id=action.id).exists()

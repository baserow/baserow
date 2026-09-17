import dataclasses
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
from baserow.contrib.database.workflow_actions.trash_types import (
    DatabaseWorkflowActionTrashableItemType,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.signals import action_done
from baserow.core.services.models import Service
from baserow.core.trash.handler import TrashHandler


def _url(formula):
    return {"mode": "simple", "version": "0.1", "formula": formula}


def _setup(data_fixture):
    session_id = str(uuid.uuid4())
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    return user, session_id, table, button_field


def _enable_email(settings):
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "localhost"


def _email_service(workflow_action_id):
    action = DatabaseWorkflowActionHandler().get_workflow_action(workflow_action_id)
    assert isinstance(action, CoreSMTPEmailWorkflowAction)
    return action.service.specific


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


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_type_change_brings_back_the_sensitive_fields(data_fixture, settings):
    """
    The logged values leave the email's recipients and subject out, so the undo
    attaches the service the type change replaced instead of building one.
    """

    _enable_email(settings)
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    service = CoreSMTPEmailWorkflowAction.objects.get(pk=action.pk).service.specific
    service.to_emails = _url("'ada@example.com'")
    service.subject = _url("'Approved'")
    service.save()

    UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_create_row"
    )
    logged = json.dumps(
        Action.objects.get(type="update_database_workflow_action").params
    )
    assert "ada@example.com" not in logged

    ActionHandler.undo(user, _scope(table), session_id)

    restored = _email_service(action.id)
    assert restored.id == service.id
    assert restored.to_emails["formula"] == "'ada@example.com'"
    assert restored.subject["formula"] == "'Approved'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_a_type_change_and_its_config_keeps_the_sensitive_fields(
    data_fixture, settings
):
    """
    The editor sends a type change and its config as two updates in one group.
    Redo attaches the service the config was written to, so nothing is blank.
    """

    _enable_email(settings)
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))
    changed = UpdateDatabaseWorkflowActionActionType.do(user, action, type="smtp_email")
    UpdateDatabaseWorkflowActionActionType.do(
        user,
        changed,
        service={"to_emails": _url("'ada@example.com'"), "body": _url("'Hi'")},
    )

    ActionHandler.undo(user, _scope(table), session_id)
    assert isinstance(
        DatabaseWorkflowActionHandler().get_workflow_action(action.id),
        LocalBaserowCreateRowWorkflowAction,
    )

    ActionHandler.redo(user, _scope(table), session_id)

    assert not Action.objects.filter(error__isnull=False).exists()
    redone = _email_service(action.id)
    assert redone.to_emails["formula"] == "'ada@example.com'"
    assert redone.body["formula"] == "'Hi'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_a_type_change_deletes_only_the_service_left_unattached(
    data_fixture,
):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    replaced_service_id = LocalBaserowCreateRowWorkflowAction.objects.get(
        pk=action.pk
    ).service_id

    changed = UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    assert Service.objects.filter(id=replaced_service_id).exists()

    logged = Action.objects.get(type="update_database_workflow_action")
    UpdateDatabaseWorkflowActionActionType.clean_up_any_extra_action_data(logged)

    assert not Service.objects.filter(id=replaced_service_id).exists()
    assert Service.objects.filter(id=changed.service_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleaning_up_keeps_a_service_a_later_type_change_still_names(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    middle = UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    middle_service_id = middle.service_id
    UpdateDatabaseWorkflowActionActionType.do(user, middle, type="open_url")

    first = Action.objects.filter(type="update_database_workflow_action").order_by(
        "id"
    )[0]
    UpdateDatabaseWorkflowActionActionType.clean_up_any_extra_action_data(first)

    # The second type change undoes back onto it.
    assert Service.objects.filter(id=middle_service_id).exists()
    ActionHandler.undo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert restored.service_id == middle_service_id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_type_change_to_a_type_without_a_service_restores_its_config(
    data_fixture,
):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url=_url("'https://kept'")
    )

    changed = UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_create_row"
    )
    new_service_id = changed.service_id

    ActionHandler.undo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert isinstance(restored, OpenUrlWorkflowAction)
    assert restored.url["formula"] == "'https://kept'"

    ActionHandler.redo(user, _scope(table), session_id)
    redone = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert isinstance(redone, LocalBaserowCreateRowWorkflowAction)
    assert redone.service_id == new_service_id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_button_field_type_change_logs_no_sensitive_action_values(data_fixture):
    """
    The field's backup carries its actions, and it is logged on the undo action
    and copied into the audit log, so an HTTP action's key is left out.
    """

    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    action = CoreHTTPRequestWorkflowAction.objects.get(pk=action.pk)
    action.service.specific.headers.create(
        key="Authorization", value=_url("'Bearer the-secret'")
    )

    UpdateFieldActionType.do(user, button_field, new_type_name="text")

    logged = json.dumps(Action.objects.get(type="update_field").params)
    assert "the-secret" not in logged
    assert "Authorization" in logged

    ActionHandler.undo(user, _scope(table), session_id)
    restored = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert [header.key for header in restored.service.specific.headers.all()] == [
        "Authorization"
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_type_change_survives_the_field_changing_type_and_back(data_fixture):
    """
    Undoing the field type change recreates the action with a copy of its
    service. The type change's undo keeps that copy for its redo, rather than
    looking for the service the field change deleted.
    """

    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    UpdateFieldActionType.do(user, button_field, new_type_name="text")

    ActionHandler.undo(user, _scope(table), session_id)
    copy_id = DatabaseWorkflowActionHandler().get_workflow_action(action.id).service_id
    ActionHandler.undo(user, _scope(table), session_id)
    ActionHandler.redo(user, _scope(table), session_id)

    assert not Action.objects.filter(error__isnull=False).exists()
    redone = DatabaseWorkflowActionHandler().get_workflow_action(action.id)
    assert isinstance(redone, LocalBaserowDeleteRowWorkflowAction)
    assert redone.service_id == copy_id

    # The service the redo left is still named, so the clean up deletes it.
    logged = Action.objects.get(type="update_database_workflow_action")
    kept_id = logged.params["original_service_id"]
    UpdateDatabaseWorkflowActionActionType.clean_up_any_extra_action_data(logged)
    assert not Service.objects.filter(id=kept_id).exists()
    assert Service.objects.filter(id=copy_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_an_edit_to_only_sensitive_fields_adds_no_undo_step(data_fixture, settings):
    """
    Undo leaves sensitive fields as they are, so a step for this edit would
    report an undo that changes nothing.
    """

    _enable_email(settings)
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    # What saving through the API pins, so the update below changes only the
    # subject.
    service = CoreSMTPEmailWorkflowAction.objects.get(pk=action.pk).service.specific
    service.use_instance_smtp_settings = True
    service.save()

    received = []

    def receiver(sender, action_params, **kwargs):
        received.append(action_params)

    action_done.connect(receiver)
    try:
        UpdateDatabaseWorkflowActionActionType.do(
            user,
            CoreSMTPEmailWorkflowAction.objects.get(pk=action.pk),
            service={"subject": _url("'Changed'")},
        )
    finally:
        action_done.disconnect(receiver)

    assert not Action.objects.filter(type="update_database_workflow_action").exists()
    # The audit log still records the update, as JSON it can store.
    assert json.loads(json.dumps(received))[0]["workflow_action_id"] == action.id
    assert _email_service(action.id).subject["formula"] == "'Changed'"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_save_whose_deleted_action_was_restored_since(data_fixture):
    """
    The action came back through the trash modal, so the undo has nothing to
    restore and must not fail the rest of the save's group.
    """

    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))
    UpdateFieldActionType.do(user, button_field, new_type_name="button", label="After")
    DeleteDatabaseWorkflowActionActionType.do(user, action)

    TrashHandler.restore_item(
        user, DatabaseWorkflowActionTrashableItemType.type, action.id
    )
    undone = ActionHandler.undo(user, _scope(table), session_id)

    assert all(entry.error is None for entry in undone)
    button_field.refresh_from_db()
    assert button_field.label == "Go"
    assert _ids(button_field) == [action.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_a_create_whose_action_was_restored_since(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = CreateDatabaseWorkflowActionActionType.do(
        user, database_workflow_action_type_registry.get("open_url"), button_field
    )
    ActionHandler.undo(user, _scope(table), session_id)
    TrashHandler.restore_item(
        user, DatabaseWorkflowActionTrashableItemType.type, action.id
    )

    redone = ActionHandler.redo(user, _scope(table), session_id)

    assert all(entry.error is None for entry in redone)
    assert _ids(button_field) == [action.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_a_delete_whose_action_was_trashed_since(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    DeleteDatabaseWorkflowActionActionType.do(user, action)
    ActionHandler.undo(user, _scope(table), session_id)
    TrashHandler.trash(user, table.database.workspace, table.database, action)

    redone = ActionHandler.redo(user, _scope(table), session_id)

    assert all(entry.error is None for entry in redone)
    assert _ids(button_field) == []


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_a_delete_and_reorder_puts_every_action_back_in_place(data_fixture):
    user, session_id, table, button_field = _setup(data_fixture)
    a = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    b = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    c = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    DatabaseWorkflowActionHandler().order_workflow_actions(
        button_field, [b.id, a.id, c.id]
    )

    # What the editor sends for [B, A, C] saved as [C, A].
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))
    DeleteDatabaseWorkflowActionActionType.do(user, b)
    OrderDatabaseWorkflowActionsActionType.do(user, button_field, [c.id, a.id])

    ActionHandler.undo(user, _scope(table), session_id)

    assert _ids(button_field) == [b.id, a.id, c.id]
    orders = DatabaseWorkflowAction.objects.filter(field=button_field).values_list(
        "order", flat=True
    )
    assert len(set(orders)) == 3

    ActionHandler.redo(user, _scope(table), session_id)
    assert _ids(button_field) == [c.id, a.id]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_service_still_attached_is_found_in_one_query(
    data_fixture, django_assert_num_queries
):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    changed = UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    logged = Action.objects.get(type="update_database_workflow_action")

    with django_assert_num_queries(1):
        assert UpdateDatabaseWorkflowActionActionType._service_is_needed(
            changed.service_id, logged
        )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_a_service_left_unattached_is_found_in_two_queries(
    data_fixture, django_assert_num_queries
):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    replaced_service_id = LocalBaserowCreateRowWorkflowAction.objects.get(
        pk=action.pk
    ).service_id
    UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )
    logged = Action.objects.get(type="update_database_workflow_action")

    with django_assert_num_queries(2):
        assert not UpdateDatabaseWorkflowActionActionType._service_is_needed(
            replaced_service_id, logged
        )


@pytest.mark.parametrize(
    "action_type,expected",
    [
        (
            CreateDatabaseWorkflowActionActionType,
            [
                "database_id",
                "table_id",
                "field_id",
                "workflow_action_id",
                "workflow_action_type",
            ],
        ),
        (
            UpdateDatabaseWorkflowActionActionType,
            [
                "database_id",
                "table_id",
                "field_id",
                "workflow_action_id",
                "workflow_action_type",
                "original_workflow_action_type",
            ],
        ),
        (
            DeleteDatabaseWorkflowActionActionType,
            [
                "database_id",
                "table_id",
                "field_id",
                "workflow_action_id",
                "workflow_action_type",
            ],
        ),
        (
            OrderDatabaseWorkflowActionsActionType,
            ["database_id", "table_id", "field_id"],
        ),
    ],
)
def test_editor_actions_send_their_analytics_params(action_type, expected):
    assert action_type.analytics_params == expected
    param_names = {f.name for f in dataclasses.fields(action_type.Params)}
    assert set(expected) <= param_names


@pytest.fixture
def done_params():
    """The `action_params` of every editor action registration, by type."""

    received = []

    def receiver(sender, action_type, action_params, **kwargs):
        received.append((action_type.type, action_params))

    action_done.connect(receiver)
    yield received
    action_done.disconnect(receiver)


@pytest.mark.django_db
def test_an_update_records_the_type_before_and_after(data_fixture, done_params):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    UpdateDatabaseWorkflowActionActionType.do(
        user, action, type="local_baserow_delete_row"
    )

    params = [
        p for t, p in done_params if t == UpdateDatabaseWorkflowActionActionType.type
    ]
    assert len(params) == 1
    assert params[0]["workflow_action_type"] == "local_baserow_delete_row"
    assert params[0]["original_workflow_action_type"] == "local_baserow_create_row"


@pytest.mark.django_db
def test_an_update_without_a_type_change_records_the_same_type(
    data_fixture, done_params
):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field, url=_url("'https://before'")
    )

    UpdateDatabaseWorkflowActionActionType.do(user, action, target="blank")

    params = [
        p for t, p in done_params if t == UpdateDatabaseWorkflowActionActionType.type
    ]
    assert params[0]["workflow_action_type"] == "open_url"
    assert params[0]["original_workflow_action_type"] == "open_url"


@pytest.mark.django_db
def test_a_delete_records_the_type(data_fixture, done_params):
    user, session_id, table, button_field = _setup(data_fixture)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DeleteDatabaseWorkflowActionActionType.do(user, action)

    params = [
        p for t, p in done_params if t == DeleteDatabaseWorkflowActionActionType.type
    ]
    assert params[0]["workflow_action_type"] == "open_url"


def test_stored_update_and_delete_params_without_a_type_still_load():
    UpdateDatabaseWorkflowActionActionType.Params(
        1, "db", 2, "table", 3, "field", 4, {}, {}
    )
    DeleteDatabaseWorkflowActionActionType.Params(1, "db", 2, "table", 3, "field", 4)

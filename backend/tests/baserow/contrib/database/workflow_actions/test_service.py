import pytest

from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.database.workflow_actions.signals import (
    workflow_action_deleted,
)
from baserow.core.exceptions import PermissionException
from baserow.core.services.models import Service


@pytest.mark.django_db
def test_create_workflow_action(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    action = DatabaseWorkflowActionService().create_workflow_action(
        user, action_type, button_field
    )

    assert action.field_id == button_field.id
    assert action.service is not None


@pytest.mark.django_db
def test_create_is_refused_without_field_permission(data_fixture):
    outsider = data_fixture.create_user()
    owner = data_fixture.create_user()
    table = data_fixture.create_database_table(user=owner)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().create_workflow_action(
            outsider, action_type, button_field
        )


@pytest.mark.django_db
def test_delete_is_refused_without_field_permission(data_fixture):
    outsider = data_fixture.create_user()
    owner = data_fixture.create_user()
    table = data_fixture.create_database_table(user=owner)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().delete_workflow_action(outsider, action)


@pytest.mark.django_db
def test_delete_sends_the_deleted_action_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action_id = action.id
    received = []

    def receiver(sender, **kwargs):
        received.append(kwargs)

    workflow_action_deleted.connect(receiver)
    try:
        DatabaseWorkflowActionService().delete_workflow_action(user, action)
    finally:
        workflow_action_deleted.disconnect(receiver)

    assert len(received) == 1
    assert received[0]["workflow_action_id"] == action_id


@pytest.mark.django_db(transaction=True)
def test_deleting_an_action_deletes_its_service(data_fixture):
    from baserow.core.services.models import Service

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service_id = action.service_id

    DatabaseWorkflowActionService().delete_workflow_action(user, action)

    assert not Service.objects.filter(id=service_id).exists()


@pytest.mark.django_db
def test_changing_the_type_keeps_the_action(data_fixture):
    """A type change is an update, so the caller keeps the action it had."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action_id, order, old_service_id = action.id, action.order, action.service_id

    updated = DatabaseWorkflowActionService().update_workflow_action(
        user, action, type="local_baserow_delete_row"
    )

    assert isinstance(updated, LocalBaserowDeleteRowWorkflowAction)
    assert updated.id == action_id
    assert updated.order == order
    assert updated.field_id == button_field.id
    assert updated.service_id != old_service_id
    assert DatabaseWorkflowAction.objects.filter(field=button_field).count() == 1


@pytest.mark.django_db
def test_changing_the_type_disposes_the_old_service(data_fixture):
    """The swap only deletes the child row, so `pre_delete` never fires."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    old_service_id = action.service_id

    DatabaseWorkflowActionService().update_workflow_action(
        user, action, type="open_url"
    )

    assert not Service.objects.filter(id=old_service_id).exists()


@pytest.mark.django_db
def test_changing_the_type_drops_the_old_type_values(data_fixture):
    """The old type's row goes with it, so its values can't reach the new one."""

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction,
        field=button_field,
        url={"mode": "simple", "version": "0.1", "formula": "'https://baserow.io'"},
    )

    updated = DatabaseWorkflowActionService().update_workflow_action(
        user, action, type="local_baserow_create_row"
    )

    assert isinstance(updated, LocalBaserowCreateRowWorkflowAction)
    assert updated.service_id is not None
    assert not OpenUrlWorkflowAction.objects.filter(id=updated.id).exists()


@pytest.mark.django_db
def test_changing_the_type_holds_its_place_in_the_order(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )
    middle = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    last = data_fixture.create_database_workflow_action(
        OpenUrlWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().update_workflow_action(
        user, middle, type="open_url"
    )

    assert list(
        DatabaseWorkflowAction.objects.filter(field=button_field)
        .order_by("order", "id")
        .values_list("id", flat=True)
    ) == [first.id, middle.id, last.id]


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().order_workflow_actions(
        user, button_field, [second.id, first.id]
    )
    first.refresh_from_db()
    second.refresh_from_db()

    assert second.order < first.order

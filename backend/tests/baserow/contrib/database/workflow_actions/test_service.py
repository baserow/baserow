import pytest

from baserow.contrib.database.workflow_actions.models import CreateRowWorkflowAction
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


@pytest.mark.django_db
def test_create_workflow_action(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action_type = database_workflow_action_type_registry.get("create_row")

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
    action_type = database_workflow_action_type_registry.get("create_row")

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
        CreateRowWorkflowAction, field=button_field
    )

    with pytest.raises(PermissionException):
        DatabaseWorkflowActionService().delete_workflow_action(outsider, action)


@pytest.mark.django_db
def test_delete_sends_the_deleted_action_id(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    action = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
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
        CreateRowWorkflowAction, field=button_field
    )
    service_id = action.service_id

    DatabaseWorkflowActionService().delete_workflow_action(user, action)

    assert not Service.objects.filter(id=service_id).exists()


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    first = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        CreateRowWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionService().order_workflow_actions(
        user, button_field, [second.id, first.id]
    )
    first.refresh_from_db()
    second.refresh_from_db()

    assert second.order < first.order

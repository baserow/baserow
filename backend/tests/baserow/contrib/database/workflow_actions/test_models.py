import pytest

from baserow.contrib.database.workflow_actions.models import (
    CreateRowWorkflowAction,
    DatabaseWorkflowAction,
    DeleteRowWorkflowAction,
    UpdateRowWorkflowAction,
)
from baserow.core.services.models import Service


@pytest.mark.django_db
def test_workflow_action_parent_is_the_field(data_fixture):
    button_field = data_fixture.create_button_field()
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)
    action = CreateRowWorkflowAction.objects.create(
        field=button_field, order=1, service=service
    )

    assert action.get_parent() == button_field
    # `workflow_actions` is defined on the base `DatabaseWorkflowAction`, so
    # it returns base instances; `.specific` resolves the polymorphic type.
    assert [a.specific for a in button_field.workflow_actions.all()] == [action]


@pytest.mark.django_db
def test_actions_are_ordered(data_fixture):
    button_field = data_fixture.create_button_field()
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)
    second = CreateRowWorkflowAction.objects.create(
        field=button_field, order=2, service=service
    )
    first = DeleteRowWorkflowAction.objects.create(
        field=button_field, order=1, service=service
    )

    actions = DatabaseWorkflowAction.objects.filter(field=button_field)

    assert [a.id for a in actions] == [first.id, second.id]


@pytest.mark.django_db
def test_get_last_order(data_fixture):
    button_field = data_fixture.create_button_field()
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)

    assert DatabaseWorkflowAction.get_last_order(button_field) == 1

    UpdateRowWorkflowAction.objects.create(field=button_field, order=1, service=service)

    assert DatabaseWorkflowAction.get_last_order(button_field) == 2


# `transaction=True`: the service is deleted from an `on_commit` receiver,
# which never runs inside the wrapping transaction of a plain `django_db` test.
@pytest.mark.django_db(transaction=True)
def test_actions_are_deleted_when_the_field_stops_being_a_button(data_fixture):
    """ADR 006 section 8: converting away destroys actions and their services."""

    from baserow.contrib.database.fields.handler import FieldHandler

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    button_field = data_fixture.create_button_field(table=table)
    service = data_fixture.create_local_baserow_upsert_row_service(integration=None)
    CreateRowWorkflowAction.objects.create(field=button_field, order=1, service=service)

    FieldHandler().update_field(user, button_field, new_type_name="text")

    assert DatabaseWorkflowAction.objects.count() == 0
    assert not Service.objects.filter(id=service.id).exists()


@pytest.mark.django_db
def test_the_fixture_creates_an_action_with_its_service(data_fixture):
    action = data_fixture.create_database_workflow_action(CreateRowWorkflowAction)

    assert action.field is not None
    assert action.service is not None
    assert action.order == 1

import pytest

from baserow.contrib.database.fields.field_types import ButtonFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
)
from baserow.core.handler import CoreHandler
from baserow.core.trash.handler import TrashHandler


def _requires_reconfiguration(button_field):
    """
    Reads the flag both ways a button field is loaded, and fails if they
    disagree, so every case below also pins the annotation to the fallback.
    """

    annotated = (
        ButtonFieldType()
        .enhance_field_queryset(ButtonField.objects.filter(id=button_field.id), None)
        .get()
        .requires_reconfiguration
    )
    fallback = ButtonField.objects.get(id=button_field.id).requires_reconfiguration
    assert annotated == fallback, "The annotation and the fallback disagree."
    return annotated


def _row_action(data_fixture, model_class, button_field, table):
    action = data_fixture.create_database_workflow_action(
        model_class, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    return action, service


@pytest.fixture
def setup(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        # Two fields, so "Name" isn't the (undeletable) primary field.
        fields=[("Id", "text", {}), ("Name", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    return user, database, table, name_field, button_field


@pytest.mark.django_db
def test_a_button_without_actions_does_not_need_reconfiguring(setup):
    *_, button_field = setup

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [LocalBaserowCreateRowWorkflowAction, LocalBaserowUpdateRowWorkflowAction],
)
def test_a_mapping_on_a_trashed_field_needs_reconfiguring_until_restored(
    data_fixture, setup, model_class
):
    user, _, table, name_field, button_field = setup
    _, service = _row_action(data_fixture, model_class, button_field, table)
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)

    assert _requires_reconfiguration(button_field) is False

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "field", name_field.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_disabled_mapping_on_a_trashed_field_does_not_count(data_fixture, setup):
    user, _, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.field_mappings.create(field=name_field, value="'x'", enabled=False)

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_trashed_mapping_with_an_integration_does_not_count(data_fixture, setup):
    """With an integration the dispatch drops the mapping rather than failing."""

    user, database, table, name_field, button_field = setup
    _, service = _row_action(
        data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, table
    )
    service.integration = data_fixture.create_local_baserow_integration(
        application=database, user=user
    )
    service.save()
    service.field_mappings.create(field=name_field, value="'x'", enabled=True)

    FieldHandler().delete_field(user, name_field)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [
        LocalBaserowCreateRowWorkflowAction,
        LocalBaserowUpdateRowWorkflowAction,
        LocalBaserowDeleteRowWorkflowAction,
    ],
)
def test_a_row_action_without_a_table_needs_reconfiguring(
    data_fixture, setup, model_class
):
    *_, button_field = setup
    _row_action(data_fixture, model_class, button_field, None)

    assert _requires_reconfiguration(button_field) is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class",
    [LocalBaserowCreateRowWorkflowAction, LocalBaserowDeleteRowWorkflowAction],
)
def test_a_trashed_target_table_needs_reconfiguring_until_restored(
    data_fixture, setup, model_class
):
    user, database, _, _, button_field = setup
    target = data_fixture.create_database_table(user=user, database=database)
    _row_action(data_fixture, model_class, button_field, target)

    TableHandler().delete_table(user, target)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "table", target.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
def test_a_target_table_in_a_trashed_database_needs_reconfiguring(data_fixture, setup):
    user, database, _, _, button_field = setup
    other_database = data_fixture.create_database_application(
        user=user, workspace=database.workspace
    )
    target = data_fixture.create_database_table(user=user, database=other_database)
    _row_action(data_fixture, LocalBaserowCreateRowWorkflowAction, button_field, target)

    CoreHandler().delete_application(user, other_database)

    assert _requires_reconfiguration(button_field) is True

    TrashHandler.restore_item(user, "application", other_database.id)

    assert _requires_reconfiguration(button_field) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_class", [OpenUrlWorkflowAction, CoreHTTPRequestWorkflowAction]
)
def test_other_action_types_never_need_reconfiguring(data_fixture, setup, model_class):
    *_, button_field = setup
    data_fixture.create_database_workflow_action(model_class, field=button_field)

    assert _requires_reconfiguration(button_field) is False

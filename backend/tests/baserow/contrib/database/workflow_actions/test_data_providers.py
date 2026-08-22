import pytest

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.data_providers import (
    PreviousActionDataProviderType,
)
from baserow.contrib.database.workflow_actions.dispatch_context import (
    DatabaseDispatchContext,
)
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.core.formula.exceptions import InvalidFormulaContext


def _create_row_action(data_fixture, user, button_field, table, name_field):
    """A `create_row` action writing a literal into `name_field`."""

    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action.service.specific.table = table
    action.service.specific.save()
    action.service.specific.field_mappings.create(
        field=name_field, value="'Ada'", enabled=True
    )
    return action


@pytest.fixture
def chained(data_fixture):
    """A dispatched `create_row` action, and the context it ran in."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = _create_row_action(data_fixture, user, button_field, table, name_field)
    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    created = table.get_model().objects.exclude(id=row.id).get()

    return {
        "action": action,
        "context": dispatch_context,
        "created": created,
        "name_field": name_field,
    }


@pytest.mark.django_db
def test_it_resolves_the_created_row_id(chained):
    provider = PreviousActionDataProviderType()

    value = provider.get_data_chunk(
        chained["context"], [str(chained["action"].id), "id"]
    )

    assert value == chained["created"].id


@pytest.mark.django_db
def test_it_resolves_a_field_of_the_created_row(chained):
    provider = PreviousActionDataProviderType()

    # The path holds `field_<id>`; the service turns it into the field name the
    # result is keyed by.
    value = provider.get_data_chunk(
        chained["context"],
        [str(chained["action"].id), f"field_{chained['name_field'].id}"],
    )

    assert value == "Ada"


@pytest.mark.django_db
def test_an_unknown_action_id_raises(chained):
    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(chained["context"], ["999999", "id"])


@pytest.mark.django_db
def test_an_action_that_has_not_run_raises(data_fixture):
    """A reference pointing forwards, at an action later in the list."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    later = _create_row_action(data_fixture, user, button_field, table, name_field)
    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(dispatch_context, [str(later.id), "id"])


@pytest.mark.django_db
def test_a_field_missing_from_the_result_raises(chained):
    """A field deleted after the reference was written. Resolving it to nothing
    would write a blank over whatever the target row already held."""

    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(
            chained["context"], [str(chained["action"].id), "field_999999"]
        )


@pytest.mark.django_db
def test_a_field_left_empty_still_resolves(data_fixture):
    """An empty cell is a value, not a missing field, so it stays null."""

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user,
        database=database,
        name="People",
        fields=[("Name", "text", {}), ("Note", "text", {})],
    )
    name_field = table.field_set.get(name="Name")
    note_field = table.field_set.get(name="Note")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = _create_row_action(data_fixture, user, button_field, table, name_field)
    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    provider = PreviousActionDataProviderType()

    assert (
        provider.get_data_chunk(
            dispatch_context, [str(action.id), f"field_{note_field.id}"]
        )
        is None
    )


@pytest.mark.django_db
def test_a_non_numeric_action_id_raises(chained):
    """A client id that escaped the editor's substitution must not resolve."""

    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(chained["context"], ["abc-123", "id"])

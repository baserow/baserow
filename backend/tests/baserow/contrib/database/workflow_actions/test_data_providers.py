import pytest

from baserow.contrib.database.rows.runtime_formula_contexts import (
    HumanReadableRowContext,
)
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
from baserow.core.formula.parser.exceptions import BaserowFormulaSyntaxError
from baserow.core.services.dispatch_context import DispatchContext


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
def test_an_action_missing_from_the_instance_cache_raises(chained):
    """Reading a path out of a result the dispatch never recorded the action
    for has to fail the click, not resolve to nothing."""

    provider = PreviousActionDataProviderType()
    action_id = chained["action"].id
    del chained["context"].cache[PreviousActionDataProviderType.ACTIONS_CACHE_KEY][
        action_id
    ]

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(chained["context"], [str(action_id), "id"])


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


@pytest.mark.django_db
def test_a_context_with_no_click_raises(data_fixture):
    """
    An AI prompt resolves its formula through a context that runs no sequence,
    and both providers share a registry, so a `previous_action` path lands here
    against it. It must fail as a formula error, not as an attribute error.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    row = table.get_model().objects.create()
    context = HumanReadableRowContext(row)

    provider = PreviousActionDataProviderType()

    assert not hasattr(context, "cache")
    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(context, ["1", "id"])


def test_a_context_that_runs_no_sequence_says_so():
    """
    A dispatch context always carries a cache, but only a click seeds this
    provider's key in it. Without that key there is no sequence at all, which
    is not the same as a reference pointing at an action that has not run yet.
    """

    class ContextWithoutASequence(DispatchContext):
        pass

    context = ContextWithoutASequence()

    provider = PreviousActionDataProviderType()

    assert PreviousActionDataProviderType.CACHE_KEY not in context.cache
    with pytest.raises(InvalidFormulaContext) as error:
        provider.get_data_chunk(context, ["1", "id"])

    assert "while a button is clicked" in str(error.value)


@pytest.mark.django_db
def test_a_write_only_field_of_the_result_cannot_be_read(data_fixture):
    """
    The row provider refuses a password field, and the explorer never offers
    one. A path typed by hand must not be the one way round that.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    password_field = data_fixture.create_password_field(table=table, name="Secret")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = _create_row_action(data_fixture, user, button_field, table, name_field)
    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext) as error:
        provider.get_data_chunk(
            dispatch_context, [str(action.id), f"field_{password_field.id}"]
        )

    assert "cannot be read by an action" in str(error.value)


@pytest.mark.django_db
def test_a_path_naming_no_action_raises(chained):
    """`get('previous_action')` reaches here when it was saved before the API
    started refusing it. It must fail as a formula error, not as a crash."""

    provider = PreviousActionDataProviderType()

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(chained["context"], [])


def test_a_path_naming_no_action_is_refused():
    provider = PreviousActionDataProviderType()

    with pytest.raises(BaserowFormulaSyntaxError):
        provider.is_valid([])

    assert provider.is_valid(["1", "id"]) is True


def test_importing_a_path_naming_no_action_leaves_it_alone():
    provider = PreviousActionDataProviderType()

    assert provider.import_path([], {"database_workflow_actions": {}}) == []


def test_a_service_that_cannot_name_its_fields_is_left_to_the_later_checks():
    """Only a table service knows what its fields are. Another kind reaching
    here must not raise, which is not a formula error and would 500 the
    click."""

    provider = PreviousActionDataProviderType()

    class ServiceTypeWithoutFields:
        pass

    assert provider._resolve_field_segment(
        ServiceTypeWithoutFields(), None, "field_7"
    ) == (False, None)


@pytest.mark.django_db
def test_importing_a_path_whose_action_is_gone_remaps_neither_half():
    """The id maps but the row does not exist, a trashed action for instance.
    Taking the new action with the old field would name a field that action's
    table does not have, and every click would fail on it."""

    provider = PreviousActionDataProviderType()
    id_mapping = {"database_workflow_actions": {1: 99999}}

    assert provider.import_path(["1", "field_7"], id_mapping) == ["1", "field_7"]


@pytest.mark.django_db
def test_a_deleted_field_does_not_read_one_named_after_it(data_fixture):
    """
    A path names a field as `field_<id>`, and the service turns that into the
    field's name because the result is keyed by names. A field the reference
    outlived cannot be turned into anything, so a field whose name is literally
    `field_<id>` would answer for it and the click would write the wrong value.
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    # An id no field of this table has, and a field named after it.
    missing_id = name_field.id + 1000
    data_fixture.create_text_field(table=table, name=f"field_{missing_id}")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = _create_row_action(data_fixture, user, button_field, table, name_field)
    dispatch_context = DatabaseDispatchContext(user, button_field, row)
    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    provider = PreviousActionDataProviderType()

    # The result really does carry the colliding key, so nothing but the check
    # stops it being read.
    result = dispatch_context.cache[PreviousActionDataProviderType.CACHE_KEY][action.id]
    assert f"field_{missing_id}" in result

    with pytest.raises(InvalidFormulaContext):
        provider.get_data_chunk(
            dispatch_context, [str(action.id), f"field_{missing_id}"]
        )

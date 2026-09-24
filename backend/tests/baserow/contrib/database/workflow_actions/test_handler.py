import pytest

from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)


@pytest.mark.django_db
def test_create_assigns_the_next_order(data_fixture):
    button_field = data_fixture.create_button_field()
    action_type = database_workflow_action_type_registry.get("local_baserow_create_row")
    user = data_fixture.create_user()

    first = DatabaseWorkflowActionHandler().create_workflow_action(
        action_type, field=button_field, **action_type.prepare_values({}, user)
    )
    second = DatabaseWorkflowActionHandler().create_workflow_action(
        action_type, field=button_field, **action_type.prepare_values({}, user)
    )

    assert first.order == 1
    assert second.order == 2


@pytest.mark.django_db
def test_get_workflow_actions_returns_them_in_order(data_fixture):
    button_field = data_fixture.create_button_field()
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    actions = DatabaseWorkflowActionHandler().get_workflow_actions(button_field)

    assert [a.id for a in actions] == [first.id, second.id]


@pytest.mark.django_db
def test_get_workflow_actions_returns_specific_instances(data_fixture):
    button_field = data_fixture.create_button_field()
    data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )

    (action,) = DatabaseWorkflowActionHandler().get_workflow_actions(button_field)

    assert isinstance(action, LocalBaserowCreateRowWorkflowAction)


@pytest.mark.django_db
def test_order_workflow_actions(data_fixture):
    button_field = data_fixture.create_button_field()
    first = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    second = data_fixture.create_database_workflow_action(
        LocalBaserowDeleteRowWorkflowAction, field=button_field
    )

    DatabaseWorkflowActionHandler().order_workflow_actions(
        button_field, [second.id, first.id]
    )
    first.refresh_from_db()
    second.refresh_from_db()

    assert second.order < first.order


@pytest.mark.django_db
def test_ordering_an_action_from_another_field_raises(data_fixture):
    from baserow.contrib.database.workflow_actions.exceptions import (
        WorkflowActionNotInField,
    )

    button_field = data_fixture.create_button_field()
    other_field = data_fixture.create_button_field()
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    foreign = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=other_field
    )

    with pytest.raises(WorkflowActionNotInField):
        DatabaseWorkflowActionHandler().order_workflow_actions(
            button_field, [foreign.id, action.id]
        )


@pytest.mark.django_db
def test_dispatch_a_create_row_action(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action.service.specific.table = table
    action.service.specific.save()
    action.service.specific.field_mappings.create(
        field=name_field, value="'Ada'", enabled=True
    )

    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    created = table.get_model().objects.exclude(id=row.id).get()
    assert getattr(created, f"field_{name_field.id}") == "Ada"


def test_base_action_type_dispatch_refuses():
    from baserow.contrib.database.workflow_actions.models import (
        DatabaseWorkflowAction,
    )
    from baserow.contrib.database.workflow_actions.registries import (
        DatabaseWorkflowActionType,
    )
    from baserow.core.services.exceptions import InvalidServiceTypeDispatchSource

    # A frontend-only type extends the base directly rather than the
    # service-backed subclass, and must never be dispatchable server side.
    class FrontendOnlyWorkflowActionType(DatabaseWorkflowActionType):
        type = "frontend_only_test"
        model_class = DatabaseWorkflowAction

    with pytest.raises(InvalidServiceTypeDispatchSource):
        FrontendOnlyWorkflowActionType().dispatch(None, None)


@pytest.mark.django_db
def test_dispatching_stores_the_result_for_later_actions(data_fixture):
    from baserow.contrib.database.table.handler import TableHandler
    from baserow.contrib.database.workflow_actions.data_providers import (
        PreviousActionDataProviderType,
    )
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    name_field = table.field_set.get(name="Name")
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()

    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    action.service.specific.table = table
    action.service.specific.save()
    action.service.specific.field_mappings.create(
        field=name_field, value="'Ada'", enabled=True
    )

    dispatch_context = DatabaseDispatchContext(user, button_field, row)

    DatabaseWorkflowActionHandler().dispatch_workflow_action(action, dispatch_context)

    results = dispatch_context.cache[PreviousActionDataProviderType.CACHE_KEY]
    created = table.get_model().objects.exclude(id=row.id).get()

    # Keyed by action id, so a later action can name this one.
    assert results[action.id]["id"] == created.id
    assert results[action.id]["Name"] == "Ada"

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.data_providers.data_provider_types import (
    CurrentIterationDataProviderType,
    PreviousNodeProviderType,
)
from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.services.types import DispatchResult


@pytest.mark.django_db
def test_previous_node_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    first_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    dispatch_context = AutomationDispatchContext(workflow)

    dispatch_context.after_dispatch(
        trigger, DispatchResult(data={"results": [{"field_1": "Horse"}]})
    )
    dispatch_context.after_dispatch(
        first_action, DispatchResult(data={"field_2": "Badger"})
    )

    # `first_action` referencing the trigger input data.
    assert (
        PreviousNodeProviderType().get_data_chunk(
            dispatch_context, [str(trigger.id), "0", "field_1"]
        )
        == "Horse"
    )

    # `second_action` referencing the `first_action` dispatch data.
    assert (
        PreviousNodeProviderType().get_data_chunk(
            dispatch_context, [str(first_action.id), "field_2"]
        )
        == "Badger"
    )

    # If a formula path references a non-existent node, it should raise an exception.
    with pytest.raises(InvalidFormulaContext) as exc:
        PreviousNodeProviderType().get_data_chunk(dispatch_context, ["999", "field_3"])
    assert exc.value.args[0] == "The previous node doesn't exist"

    dispatch_context = AutomationDispatchContext(workflow)

    dispatch_context.after_dispatch(
        trigger, DispatchResult(data={"results": [{"field_1": "Horse"}]})
    )
    # Existing node but after
    with pytest.raises(InvalidFormulaContext) as exc:
        PreviousNodeProviderType().get_data_chunk(
            dispatch_context, [str(first_action.id), "field_2"]
        )
    assert (
        exc.value.args[0]
        == "The previous node id is not present in the dispatch context results"
    )


@pytest.mark.django_db
def test_previous_node_data_provider_import_path(data_fixture):
    data_provider = PreviousNodeProviderType()

    node = data_fixture.create_local_baserow_create_row_action_node()

    valid_id_mapping = {"automation_workflow_nodes": {1: node.id}}
    invalid_id_mapping = {"automation_workflow_nodes": {3: 4}}

    path = ["1", "0", "field_1"]

    assert data_provider.import_path(path, {}) == ["1", "0", "field_1"]
    assert data_provider.import_path(path, invalid_id_mapping) == ["1", "0", "field_1"]
    assert data_provider.import_path(path, valid_id_mapping) == [
        str(node.id),
        "0",
        "field_1",
    ]


@pytest.mark.django_db
def test_current_iteration_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = workflow.get_trigger()
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow,
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    dispatch_context = AutomationDispatchContext(workflow)

    dispatch_context.after_dispatch(
        trigger,
        DispatchResult(data={"results": [{"field_1": "Horse"}, {"field_1": "Duck"}]}),
    )

    dispatch_context.after_dispatch(
        iterator,
        DispatchResult(data={"results": [{"field_1": "Horse"}, {"field_1": "Duck"}]}),
    )

    dispatch_context.set_current_iteration(iterator, 0)

    assert (
        CurrentIterationDataProviderType().get_data_chunk(
            dispatch_context, [str(iterator.id), "item", "field_1"]
        )
        == "Horse"
    )

    dispatch_context.set_current_iteration(iterator, 1)

    assert (
        CurrentIterationDataProviderType().get_data_chunk(
            dispatch_context, [str(iterator.id), "item", "field_1"]
        )
        == "Duck"
    )


@pytest.mark.django_db
def test_current_iteration_data_provider_import_path(data_fixture):
    data_provider = CurrentIterationDataProviderType()

    node = data_fixture.create_core_iterator_action_node()

    valid_id_mapping = {"automation_workflow_nodes": {1: node.id}}
    invalid_id_mapping = {"automation_workflow_nodes": {3: 4}}

    path = ["1", "item", "field_1"]

    assert data_provider.import_path(path, {}) == ["1", "item", "field_1"]
    assert data_provider.import_path(path, invalid_id_mapping) == [
        "1",
        "item",
        "field_1",
    ]
    assert data_provider.import_path(path, valid_id_mapping) == [
        str(node.id),
        "item",
        "field_1",
    ]

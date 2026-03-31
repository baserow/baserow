from django.utils import timezone

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.data_providers.data_provider_types import (
    CurrentIterationDataProviderType,
    PreviousNodeProviderType,
)
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.core.formula.exceptions import InvalidFormulaContext


@pytest.mark.django_db
def test_previous_node_data_provider_get_data_chunk(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    workflow_history = AutomationHistoryHandler().create_workflow_history(
        workflow,
        timezone.now(),
        False,
    )

    trigger = workflow.get_trigger()
    trigger_node_history = AutomationHistoryHandler().create_node_history(
        workflow_history=workflow_history,
        node=trigger,
        started_on=timezone.now(),
    )
    AutomationHistoryHandler().create_node_result(
        node_history=trigger_node_history,
        result={"results": [{"field_1": "Horse"}]},
    )

    first_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    first_action_node_history = AutomationHistoryHandler().create_node_history(
        workflow_history=workflow_history,
        node=first_action,
        started_on=timezone.now(),
    )
    AutomationHistoryHandler().create_node_result(
        node_history=first_action_node_history,
        result={"field_2": "Badger"},
    )

    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )

    dispatch_context = AutomationDispatchContext(
        workflow,
        workflow_history,
        event_payload=workflow_history.event_payload,
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

    workflow_history_2 = AutomationHistoryHandler().create_workflow_history(
        workflow,
        timezone.now(),
        False,
    )
    trigger_node_history_2 = AutomationHistoryHandler().create_node_history(
        workflow_history=workflow_history_2,
        node=trigger,
        started_on=timezone.now(),
    )
    AutomationHistoryHandler().create_node_result(
        node_history=trigger_node_history_2,
        result={"results": [{"field_1": "Horse"}]},
    )

    dispatch_context = AutomationDispatchContext(
        workflow,
        workflow_history_2,
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
    workflow = data_fixture.create_automation_workflow()
    workflow_history = AutomationHistoryHandler().create_workflow_history(
        workflow,
        timezone.now(),
        False,
    )
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow,
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
    )
    node_history = AutomationHistoryHandler().create_node_history(
        workflow_history=workflow_history,
        node=iterator,
        started_on=timezone.now(),
    )
    AutomationHistoryHandler().create_node_result(
        node_history=node_history,
        result={"results": [{"field_1": "Horse"}, {"field_1": "Duck"}]},
    )

    dispatch_context = AutomationDispatchContext(
        workflow,
        workflow_history,
        event_payload=workflow_history.event_payload,
        current_iterations={iterator.id: 0},
    )

    assert (
        CurrentIterationDataProviderType().get_data_chunk(
            dispatch_context, [str(iterator.id), "item", "field_1"]
        )
        == "Horse"
    )

    dispatch_context.current_iterations[iterator.id] = 1

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

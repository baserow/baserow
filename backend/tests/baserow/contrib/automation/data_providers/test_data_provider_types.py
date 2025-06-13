import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.data_providers.data_provider_types import (
    PreviousNodeProviderType,
)
from baserow.contrib.builder.data_providers.exceptions import (
    DataProviderChunkInvalidException,
)


@pytest.mark.django_db
def test_previous_node_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user)
    trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow
    )
    first_action = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, previous_node=trigger
    )
    data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow, previous_node=trigger
    )
    dispatch_context = AutomationDispatchContext(workflow, [{"field_1": "Horse"}])
    dispatch_context.register_node_result(first_action, {"field_2": "Badger"})

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
    with pytest.raises(DataProviderChunkInvalidException) as exc:
        PreviousNodeProviderType().get_data_chunk(dispatch_context, ["999", "field_3"])
    assert (
        exc.value.args[0]
        == "The previous node id is not present in the dispatch context results"
    )

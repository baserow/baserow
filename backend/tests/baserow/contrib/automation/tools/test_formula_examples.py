import pytest

from baserow.contrib.automation.application_types import AutomationApplicationType
from baserow.contrib.automation.tools import formula_examples


@pytest.mark.django_db
def test_formula_examples_read_a_schema_inferred_from_sample_data(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow,
        service_kwargs={
            "sample_data": {
                "data": {
                    # Rows as a Local Baserow node returns them.
                    "results": [
                        {
                            "id": 5,
                            "order": "1.00",
                            "Active": True,
                            "Hotel": [{"id": 1, "value": "Grand", "order": "1.00"}],
                        }
                    ]
                }
            }
        },
    )
    node = data_fixture.create_local_baserow_get_row_action_node(
        workflow=workflow, reference_node=iterator, position="south"
    )

    examples = AutomationApplicationType().get_formula_examples(user, node)

    assert examples.get_formula_context()["previous_node"][str(iterator.id)] == [
        {
            "id": 1,
            "order": "1",
            "Active": True,
            "Hotel": [{"id": 1, "value": "1", "order": "1"}],
        }
    ]


@pytest.mark.django_db
def test_formula_examples_read_a_wait_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    wait = data_fixture.create_core_wait_action_node(workflow=workflow)
    node = data_fixture.create_local_baserow_get_row_action_node(workflow=workflow)

    examples = AutomationApplicationType().get_formula_examples(user, node)

    assert examples.get_formula_context()["previous_node"][str(wait.id)]["seconds"] == 1


@pytest.mark.django_db
def test_formula_examples_leave_out_a_node_whose_schema_is_not_of_objects(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user)
    wait = data_fixture.create_core_wait_action_node(workflow=workflow)
    iterator = data_fixture.create_core_iterator_action_node(
        workflow=workflow,
        service_kwargs={"sample_data": {"data": {"results": ["Grand", "Royal"]}}},
    )
    node = data_fixture.create_local_baserow_get_row_action_node(
        workflow=workflow, reference_node=iterator, position="south"
    )

    examples = AutomationApplicationType().get_formula_examples(user, node)

    # The iterator is left out, and the nodes before it are still read.
    assert set(examples.get_formula_context()["previous_node"]) == {str(wait.id)}
    assert formula_examples.WorkflowExamples(user).previous(node) is None

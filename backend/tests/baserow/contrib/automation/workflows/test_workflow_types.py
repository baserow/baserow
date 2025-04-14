import pytest

from baserow.contrib.automation.workflows.workflow_types import AutomationWorkflowType


@pytest.mark.django_db
def test_workflow_type_export_prepared_values(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowType().export_prepared_values(workflow)

    assert result == {"name": "test"}

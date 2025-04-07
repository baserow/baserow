from decimal import Decimal

import pytest

from baserow.contrib.automation.workflows.workflow_types import AutomationWorkflowType


@pytest.mark.django_db
def test_workflow_type_before_create(data_fixture):
    automation = data_fixture.create_automation_application()

    result = AutomationWorkflowType().before_create(automation)

    assert result is None


@pytest.mark.django_db
def test_workflow_type_prepare_value_for_db(data_fixture):
    workflow = data_fixture.create_automation_workflow()

    values = {"name": "test"}
    result = AutomationWorkflowType().prepare_value_for_db(values, workflow)

    assert result == values


@pytest.mark.django_db
def test_workflow_type_export_prepared_values(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowType().export_prepared_values(workflow)

    assert result == {"name": "test"}


@pytest.mark.django_db
def test_workflow_type_after_delete(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowType().after_delete(workflow)

    assert result is None


@pytest.mark.django_db
def test_workflow_type_before_trashed(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowType().before_trashed(workflow)

    assert result is None


@pytest.mark.django_db
def test_workflow_type_before_restore(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    result = AutomationWorkflowType().before_restore(workflow)

    assert result is None


@pytest.mark.parametrize(
    "prop_name,value",
    [
        ("name", "test"),
        ("order", 10),
    ],
)
def test_workflow_type_deserialize_property(prop_name, value):
    result = AutomationWorkflowType().deserialize_property(prop_name, value, {})

    if isinstance(value, str):
        assert result is value
    else:
        assert result == Decimal(value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prop_name,value",
    [
        ("name", "test"),
        ("order", 10),
    ],
)
def test_workflow_type_serialize_property(data_fixture, prop_name, value):
    workflow = data_fixture.create_automation_workflow(name="test", order=10)
    result = AutomationWorkflowType().serialize_property(workflow, prop_name, value, {})

    assert result == str(value)

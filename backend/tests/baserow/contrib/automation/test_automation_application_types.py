import json

import pytest

from baserow.contrib.automation.application_types import AutomationApplicationType
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_automation_export_serialized(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(
        name="Automation 1", user=user
    )
    serialized = AutomationApplicationType().export_serialized(
        automation, ImportExportConfig(include_permission_data=True)
    )
    serialized = json.loads(json.dumps(serialized))

    assert serialized == {
        "id": automation.id,
        "name": automation.name,
        "order": automation.order,
        "type": "automation",
        "workflows": [],
    }


@pytest.mark.django_db
def test_automation_init_application(data_fixture):
    user = data_fixture.create_user()
    automation = data_fixture.create_automation_application(
        name="Automation", user=user
    )

    assert automation.workflows.count() == 0

    AutomationApplicationType().init_application(user, automation)

    assert automation.workflows.count() == 1


@pytest.mark.django_db
def test_automation_import_serialized_without_workflows(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    id_mapping = {}
    serialized = {
        "id": "999",
        "name": "Automation 1",
        "order": 99,
        "type": "automation",
        "workflows": [],
    }

    automation = AutomationApplicationType().import_serialized(
        workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
    )

    assert automation.name == "Automation 1"
    assert automation.order == 99


@pytest.mark.django_db
def test_automation_import_serialized_with_workflows(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")
    serialized_workflow = AutomationWorkflowHandler().export_workflow(workflow)

    id_mapping = {}
    serialized = {
        "id": "999",
        "name": "Automation 1",
        "order": 99,
        "type": "automation",
        "workflows": [serialized_workflow],
    }

    automation = AutomationApplicationType().import_serialized(
        workflow.automation.workspace,
        serialized,
        ImportExportConfig(include_permission_data=True),
        id_mapping,
    )

    assert automation.name == "Automation 1"
    assert automation.order == 99
    assert automation.workflows.all()[0].name == "test"


@pytest.mark.django_db
def test_fetch_workflows_to_serialize_without_user(data_fixture):
    workflow = data_fixture.create_automation_workflow(name="test")

    workflows = AutomationApplicationType().fetch_workflows_to_serialize(
        workflow.automation,
        None,
    )

    assert workflows == [workflow]


@pytest.mark.django_db
def test_fetch_workflows_to_serialize_with_user(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(name="test", user=user)

    workflows = AutomationApplicationType().fetch_workflows_to_serialize(
        workflow.automation,
        user,
    )

    assert workflows == [workflow]


@pytest.mark.django_db
def test_enhance_queryset(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()

    # Create two automations with 2 workflows each
    workflow_1 = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_automation_workflow(automation=workflow_1.automation, user=user)

    workflow_3 = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_automation_workflow(automation=workflow_3.automation, user=user)

    # query 1: fetch all automations
    # query 2: fetch all workflows for automation 1
    # query 3: fetch all workflows for automation 2
    expected_queries = 3
    with django_assert_num_queries(expected_queries):
        [
            workflow.name
            for automation in Automation.objects.all()
            for workflow in automation.workflows.all()
        ]

    queryset = AutomationApplicationType().enhance_queryset(Automation.objects.all())

    # query 1: fetch all automations
    # query 2: fetch all workflows for automation 2
    expected_queries = 2
    with django_assert_num_queries(expected_queries):
        [
            workflow.name
            for automation in queryset
            for workflow in automation.workflows.all()
        ]

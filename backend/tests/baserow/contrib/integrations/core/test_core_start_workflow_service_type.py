from unittest.mock import patch

import pytest
from rest_framework import serializers

from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.node_types import (
    CoreManualTriggerNodeType,
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.core.constants import RESPONSE_BODY_TYPE
from baserow.contrib.integrations.core.models import CoreResponseHeader
from baserow.contrib.integrations.core.service_types import CoreStartWorkflowServiceType
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.pytest_conftest import FakeDispatchContext


def fake_dispatch_context():
    return FakeDispatchContext(
        count=None,
        is_publicly_searchable=False,
        searchable_fields=None,
        is_publicly_filterable=False,
        is_publicly_sortable=False,
    )


@pytest.mark.django_db
def test_start_workflow_service_generate_schema_returns_response_schema(data_fixture):
    service = data_fixture.create_core_start_workflow_service()

    assert CoreStartWorkflowServiceType().generate_schema(service) == {
        "title": f"StartWorkflow{service.id}Schema",
        "type": "object",
        "properties": {
            "status_code": {"type": "integer", "title": "Status code"},
            "headers": {
                "type": "object",
                "title": "Headers",
                "additionalProperties": {"type": "string"},
            },
            "body": {"title": "Body"},
            "body_type": {
                "type": "string",
                "title": "Body type",
                "enum": ["empty", "json", "text"],
            },
        },
    }


@pytest.mark.django_db
def test_start_workflow_service_import_serialized_remaps_workflow_id(data_fixture):
    user = data_fixture.create_user()
    original_workflow = data_fixture.create_automation_workflow(user=user)
    imported_workflow = data_fixture.create_automation_workflow(user=user)
    service = data_fixture.create_core_start_workflow_service(
        workflow=original_workflow
    )

    exported_service = CoreStartWorkflowServiceType().export_serialized(service)
    imported_service = CoreStartWorkflowServiceType().import_serialized(
        None,
        exported_service,
        {"automation_workflows": {original_workflow.id: imported_workflow.id}},
    )

    assert imported_service.workflow_id == imported_workflow.id


@pytest.mark.django_db
def test_start_workflow_service_dispatch_starts_configured_workflow(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with patch(
        "baserow.contrib.automation.workflows.handler."
        "AutomationWorkflowHandler.async_start_workflow"
    ) as async_start_workflow:
        result = ServiceHandler().dispatch_service(service, fake_dispatch_context())

    async_start_workflow.assert_called_once_with(published_workflow)
    assert result.data is None


@pytest.mark.django_db
def test_start_workflow_service_waits_for_response_node(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    response_node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "201", mode=BASEROW_FORMULA_MODE_RAW
            ),
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": BaserowFormulaObject.create("'Created'"),
        },
    )
    CoreResponseHeader.objects.create(
        service=response_node.service.specific,
        key="X-Workflow",
        value=BaserowFormulaObject.create("'done'"),
    )
    AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    result = ServiceHandler().dispatch_service(service, fake_dispatch_context())

    assert result.data == {
        "status_code": 201,
        "headers": {"X-Workflow": "done"},
        "body": "Created",
        "body_type": RESPONSE_BODY_TYPE.TEXT,
    }


@pytest.mark.django_db
def test_start_workflow_automation_node_waits_for_response_node(data_fixture):
    user = data_fixture.create_user()
    child_workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    data_fixture.create_core_response_action_node(
        workflow=child_workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "200", mode=BASEROW_FORMULA_MODE_RAW
            ),
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": BaserowFormulaObject.create("'Child response'"),
        },
    )
    AutomationWorkflowHandler().publish(child_workflow)

    parent_workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    data_fixture.create_automation_node(
        workflow=parent_workflow,
        type="start_workflow",
        service_kwargs={"workflow": child_workflow},
    )
    published_parent = AutomationWorkflowHandler().publish(parent_workflow)

    history = AutomationWorkflowHandler().async_start_workflow(
        published_parent,
        defer_scheduling=True,
    )
    start_node = published_parent.automation_workflow_nodes.get(
        service__content_type__model="corestartworkflowservice"
    )
    canvas = AutomationNodeHandler().dispatch_node(start_node.id, history.id)
    child_history = AutomationWorkflowHistory.objects.filter(
        original_workflow=child_workflow
    ).latest("id")
    AutomationHistoryHandler().create_workflow_history_response(
        child_history,
        status_code=200,
        body="Child response",
        body_type=RESPONSE_BODY_TYPE.TEXT,
    )
    node_history = AutomationNodeHistory.objects.get(
        workflow_history=history,
        node=start_node,
    )

    assert canvas is not None
    assert (
        AutomationNodeHandler().complete_deferred_node(
            node_history.id,
            child_history.id,
            "",
        )
        is None
    )
    assert AutomationHistoryHandler().get_node_result(history, start_node, "") == {
        "status_code": 200,
        "headers": {},
        "body": "Child response",
        "body_type": RESPONSE_BODY_TYPE.TEXT,
    }


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_allows_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CorePeriodicTriggerNodeType.type
    )
    AutomationWorkflowHandler().publish(workflow)

    values = CoreStartWorkflowServiceType().prepare_values(
        {"workflow_id": workflow.id}, user
    )

    assert values["workflow"] == workflow


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_rejects_workflow_without_trigger(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(user=user, create_trigger=False)
    AutomationWorkflowHandler().publish(workflow)

    with pytest.raises(serializers.ValidationError) as exc:
        CoreStartWorkflowServiceType().prepare_values(
            {"workflow_id": workflow.id}, user
        )

    assert (
        exc.value.detail[0]
        == "Only workflows with an immediate dispatch trigger can be started."
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_starts_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CorePeriodicTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with patch(
        "baserow.contrib.automation.workflows.handler."
        "AutomationWorkflowHandler.async_start_workflow"
    ) as async_start_workflow:
        result = ServiceHandler().dispatch_service(service, fake_dispatch_context())

    async_start_workflow.assert_called_once_with(published_workflow)
    assert result.data is None


@pytest.mark.django_db
def test_start_workflow_service_prepare_values_rejects_non_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    table, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )
    AutomationWorkflowHandler().publish(workflow)

    with pytest.raises(serializers.ValidationError) as exc:
        CoreStartWorkflowServiceType().prepare_values(
            {"workflow_id": workflow.id}, user
        )

    assert (
        exc.value.detail[0]
        == "Only workflows with an immediate dispatch trigger can be started."
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_non_immediate_dispatch_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    table, _, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[["Blueberry Muffin"]],
    )
    workflow = data_fixture.create_automation_workflow(
        user=user,
        trigger_type=LocalBaserowRowsCreatedNodeTriggerType.type,
        trigger_service_kwargs={"table": table},
    )
    AutomationWorkflowHandler().publish(workflow)
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, fake_dispatch_context())

    assert (
        str(exc.value)
        == "Only workflows with an immediate dispatch trigger can be started."
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_unpublished_workflow(data_fixture):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        ServiceHandler().dispatch_service(service, fake_dispatch_context())

    assert (
        str(exc.value)
        == "The selected workflow must be published before it can be started."
    )


@pytest.mark.django_db
def test_start_workflow_service_dispatch_rejects_disabled_published_workflow(
    data_fixture,
):
    user = data_fixture.create_user()
    workflow = data_fixture.create_automation_workflow(
        user=user, trigger_type=CoreManualTriggerNodeType.type
    )
    published_workflow = AutomationWorkflowHandler().publish(workflow)
    published_workflow.state = WorkflowState.DISABLED
    published_workflow.save(update_fields=["state"])
    service = data_fixture.create_core_start_workflow_service(workflow=workflow)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, fake_dispatch_context())


@pytest.mark.django_db
def test_start_workflow_service_dispatch_without_workflow_raises(data_fixture):
    service = data_fixture.create_core_start_workflow_service(workflow=None)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        ServiceHandler().dispatch_service(service, fake_dispatch_context())

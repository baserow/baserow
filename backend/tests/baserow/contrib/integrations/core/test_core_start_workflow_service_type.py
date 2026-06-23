from unittest.mock import patch

import pytest
from rest_framework import serializers

from baserow.contrib.automation.nodes.node_types import (
    CoreManualTriggerNodeType,
    CorePeriodicTriggerNodeType,
    LocalBaserowRowsCreatedNodeTriggerType,
)
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.core.service_types import CoreStartWorkflowServiceType
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
def test_start_workflow_service_generate_schema_returns_none(data_fixture):
    service = data_fixture.create_core_start_workflow_service()

    assert CoreStartWorkflowServiceType().generate_schema(service) is None


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

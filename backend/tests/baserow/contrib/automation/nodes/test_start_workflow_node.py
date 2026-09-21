from io import BytesIO

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import CoreStartWorkflowActionNode
from baserow.contrib.automation.nodes.node_types import CoreManualTriggerNodeType
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.integrations.core.models import CoreStartWorkflowService
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from tests.baserow.contrib.automation.api.utils import get_api_kwargs


def _workflow(data_fixture, user, workspace, **kwargs):
    automation = kwargs.pop("automation", None) or (
        data_fixture.create_automation_application(user=user, workspace=workspace)
    )
    kwargs.setdefault("trigger_type", CoreManualTriggerNodeType.type)
    return data_fixture.create_automation_workflow(
        user=user, automation=automation, **kwargs
    )


def _node_starting(data_fixture, workflow, target):
    """A start workflow node at the end of `workflow`, pointed at `target`."""

    return data_fixture.create_automation_node(
        type="start_workflow",
        workflow=workflow,
        service=data_fixture.create_core_start_workflow_service(workflow=target),
    )


def _started_workflow_id(node):
    return CoreStartWorkflowService.objects.get(id=node.service_id).workflow_id


@pytest.mark.django_db
def test_a_workflow_from_another_workspace_is_refused(api_client, data_fixture):
    """
    The shared service type only checks that the person configuring the node
    may read the workflow, and a user is often in more than one workspace.
    Without this, workspace B's workflow ends up behind workspace A's
    workflow, where every editor of A can fire it.
    """

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    caller = _workflow(data_fixture, user, workspace)
    node = _node_starting(data_fixture, caller, None)
    elsewhere = data_fixture.create_workspace(user=user)
    callee = _workflow(data_fixture, user, elsewhere)

    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": node.id}),
        {"service": {"workflow_id": callee.id}},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert _started_workflow_id(node) is None


@pytest.mark.django_db
def test_a_workflow_in_the_same_workspace_is_kept(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    caller = _workflow(data_fixture, user, workspace)
    callee = _workflow(data_fixture, user, workspace)
    node = _node_starting(data_fixture, caller, None)

    response = api_client.patch(
        reverse("api:automation:nodes:item", kwargs={"node_id": node.id}),
        {"service": {"workflow_id": callee.id}},
        **get_api_kwargs(token),
    )

    assert response.status_code == HTTP_200_OK
    assert _started_workflow_id(node) == callee.id


@pytest.mark.django_db(transaction=True)
def test_a_workspace_import_points_the_node_at_the_imported_workflow(data_fixture):
    """
    Automations are imported one at a time, in the order they are exported,
    so a workflow of the first one starting a workflow of the second names an
    id that has no copy yet when its node is imported. The reference used to
    keep the exported id: another workspace's workflow when that id exists,
    and a foreign key failure at commit when it does not.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    # `order` decides the import order, so the caller's automation goes first.
    first = data_fixture.create_automation_application(
        user=user, workspace=workspace, name="First", order=1
    )
    second = data_fixture.create_automation_application(
        user=user, workspace=workspace, name="Second", order=2
    )
    caller = _workflow(data_fixture, user, workspace, automation=first)
    callee = _workflow(data_fixture, user, workspace, automation=second)
    _node_starting(data_fixture, caller, callee)

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_node = CoreStartWorkflowActionNode.objects.get(
        workflow__automation__workspace=imported_workspace
    )
    started = CoreStartWorkflowService.objects.get(id=imported_node.service_id).workflow
    assert started.id != callee.id
    assert started.automation.workspace_id == imported_workspace.id
    assert started.automation.name == "Second"


@pytest.mark.django_db
def test_a_publication_keeps_the_workflow(data_fixture):
    """
    The published workflow starts the same workflow as the draft: the run
    looks up the published copy of that workflow when the node dispatches.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    caller = _workflow(data_fixture, user, workspace)
    callee = _workflow(data_fixture, user, workspace)
    _node_starting(data_fixture, caller, callee)

    published = AutomationWorkflowHandler().publish(caller)

    published_node = CoreStartWorkflowActionNode.objects.get(workflow=published)
    assert _started_workflow_id(published_node) == callee.id


@pytest.mark.django_db
def test_a_duplicated_node_keeps_the_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    caller = _workflow(data_fixture, user, workspace)
    callee = _workflow(data_fixture, user, workspace)
    node = _node_starting(data_fixture, caller, callee)

    duplicated_node = AutomationNodeHandler().duplicate_node(node)

    assert duplicated_node.id != node.id
    assert _started_workflow_id(duplicated_node) == callee.id


@pytest.mark.django_db
def test_a_duplicated_workflow_keeps_the_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    caller = _workflow(data_fixture, user, workspace)
    callee = _workflow(data_fixture, user, workspace)
    _node_starting(data_fixture, caller, callee)

    duplicated_workflow = AutomationWorkflowHandler().duplicate_workflow(caller)

    duplicated_node = CoreStartWorkflowActionNode.objects.get(
        workflow=duplicated_workflow
    )
    assert _started_workflow_id(duplicated_node) == callee.id

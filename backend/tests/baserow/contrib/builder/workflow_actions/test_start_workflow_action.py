from io import BytesIO

from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.contrib.automation.nodes.node_types import CoreManualTriggerNodeType
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    CoreStartWorkflowWorkflowAction,
    EventTypes,
)
from baserow.contrib.integrations.core.models import CoreStartWorkflowService
from baserow.core.handler import CoreHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.utils import Progress


def _workflow(data_fixture, user, workspace, **kwargs):
    automation = data_fixture.create_automation_application(
        user=user, workspace=workspace
    )
    kwargs.setdefault("trigger_type", CoreManualTriggerNodeType.type)
    return data_fixture.create_automation_workflow(
        user=user, automation=automation, **kwargs
    )


def _button(data_fixture, user, workspace):
    """A button on a page of a new builder in `workspace`."""

    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    return data_fixture.create_builder_button_element(page=page)


def _action_starting(data_fixture, element, workflow):
    """A start workflow action on `element`, already pointed at `workflow`."""

    return data_fixture.create_workflow_action(
        CoreStartWorkflowWorkflowAction,
        page=element.page,
        element=element,
        event=EventTypes.CLICK,
        service=data_fixture.create_core_start_workflow_service(workflow=workflow),
    )


def _started_workflow_id(action):
    return CoreStartWorkflowService.objects.get(id=action.service_id).workflow_id


@pytest.mark.django_db
def test_a_workflow_from_another_workspace_is_refused(api_client, data_fixture):
    """
    The shared service type only checks that the person configuring the
    action may read the workflow, and a user is often in more than one
    workspace. Without this, workspace B's workflow ends up behind workspace
    A's button, where every visitor of A's application can fire it.
    """

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    action = _action_starting(data_fixture, element, None)
    elsewhere = data_fixture.create_workspace(user=user)
    workflow = _workflow(data_fixture, user, elsewhere)

    response = api_client.patch(
        reverse(
            "api:builder:workflow_action:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {"service": {"workflow_id": workflow.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert _started_workflow_id(action) is None


@pytest.mark.django_db
def test_creating_with_a_workflow_from_another_workspace_is_refused(
    api_client, data_fixture
):
    """The page is known on creation too, before any action row exists."""

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    elsewhere = data_fixture.create_workspace(user=user)
    workflow = _workflow(data_fixture, user, elsewhere)

    response = api_client.post(
        reverse(
            "api:builder:workflow_action:list", kwargs={"page_id": element.page_id}
        ),
        {
            "type": "start_workflow",
            "event": "click",
            "element_id": element.id,
            "service": {"workflow_id": workflow.id},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert not BuilderWorkflowAction.objects.filter(page=element.page).exists()


@pytest.mark.django_db
def test_a_workflow_in_the_same_workspace_is_kept(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    action = _action_starting(data_fixture, element, None)
    workflow = _workflow(data_fixture, user, workspace)

    response = api_client.patch(
        reverse(
            "api:builder:workflow_action:item",
            kwargs={"workflow_action_id": action.id},
        ),
        {"service": {"workflow_id": workflow.id}},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert _started_workflow_id(action) == workflow.id


@pytest.mark.django_db(transaction=True)
def test_a_workspace_import_points_the_action_at_the_imported_workflow(data_fixture):
    """
    The builder is imported before the automation, so when the action's
    service is imported the workflow it names has no copy yet. The reference
    used to keep the exported id: another workspace's workflow when that id
    exists, and a foreign key failure at commit when it does not.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    imported_workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    workflow = _workflow(data_fixture, user, workspace)
    _action_starting(data_fixture, element, workflow)

    config = ImportExportConfig(include_permission_data=False)
    core_handler = CoreHandler()
    exported = core_handler.export_workspace_applications(workspace, BytesIO(), config)
    core_handler.import_applications_to_workspace(
        imported_workspace, exported, BytesIO(), config, None
    )

    imported_builder = Builder.objects.get(workspace=imported_workspace)
    imported_action = CoreStartWorkflowWorkflowAction.objects.get(
        page__builder=imported_builder
    )
    started = CoreStartWorkflowService.objects.get(
        id=imported_action.service_id
    ).workflow
    assert started.id != workflow.id
    assert started.automation.workspace_id == imported_workspace.id


@pytest.mark.django_db
def test_a_duplicated_page_keeps_the_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    workflow = _workflow(data_fixture, user, workspace)
    _action_starting(data_fixture, element, workflow)

    duplicated_page = PageHandler().duplicate_page(element.page)

    duplicated_action = CoreStartWorkflowWorkflowAction.objects.get(
        page=duplicated_page
    )
    assert _started_workflow_id(duplicated_action) == workflow.id


@pytest.mark.django_db
def test_a_duplicated_element_keeps_the_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    workflow = _workflow(data_fixture, user, workspace)
    action = _action_starting(data_fixture, element, workflow)

    duplicated = ElementHandler().duplicate_element(element)

    (duplicated_action,) = duplicated["workflow_actions"]
    assert duplicated_action.id != action.id
    assert _started_workflow_id(duplicated_action) == workflow.id


@pytest.mark.django_db
def test_a_duplicated_application_keeps_the_workflow(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    workflow = _workflow(data_fixture, user, workspace)
    _action_starting(data_fixture, element, workflow)

    duplicated_builder = CoreHandler().duplicate_application(user, element.page.builder)

    duplicated_action = CoreStartWorkflowWorkflowAction.objects.get(
        page__builder=duplicated_builder
    )
    assert _started_workflow_id(duplicated_action) == workflow.id


@pytest.mark.django_db
def test_a_publication_keeps_the_workflow(data_fixture):
    """
    The published application starts the same workflow as the editor: the
    run looks up the published copy of that workflow when the button is
    clicked.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    element = _button(data_fixture, user, workspace)
    workflow = _workflow(data_fixture, user, workspace)
    _action_starting(data_fixture, element, workflow)
    domain = data_fixture.create_builder_custom_domain(builder=element.page.builder)

    domain = DomainHandler().publish(domain, Progress(100))

    published_action = CoreStartWorkflowWorkflowAction.objects.get(
        page__builder=domain.published_to
    )
    assert _started_workflow_id(published_action) == workflow.id

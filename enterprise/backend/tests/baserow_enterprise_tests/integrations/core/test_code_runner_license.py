from django.http import HttpRequest

import pytest

from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.automation.nodes.node_types import CoreCodeNodeType
from baserow_enterprise.builder.workflow_actions.models import CoreCodeWorkflowAction
from baserow_enterprise.builder.workflow_actions.workflow_action_types import (
    CoreCodeActionType,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.mark.django_db
def test_core_code_workflow_action_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    workflow_action_type = CoreCodeActionType()

    enterprise_data_fixture.delete_all_licenses()

    assert workflow_action_type.is_deactivated(page.builder.workspace)

    with pytest.raises(FeaturesNotAvailableError):
        BuilderWorkflowActionService().create_workflow_action(
            user,
            workflow_action_type,
            page=page,
            element=element,
            event=EventTypes.CLICK,
        )

    enterprise_data_fixture.enable_enterprise()

    assert not workflow_action_type.is_deactivated(page.builder.workspace)


@pytest.mark.django_db
def test_core_code_automation_node_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    node_type = CoreCodeNodeType()

    enterprise_data_fixture.delete_all_licenses()

    assert node_type.is_deactivated(workflow.automation.workspace)

    with pytest.raises(FeaturesNotAvailableError):
        AutomationNodeService().create_node(
            user,
            node_type,
            workflow,
            reference_node_id=workflow.get_trigger().id,
            position="south",
            output="",
        )

    enterprise_data_fixture.enable_enterprise()

    assert not node_type.is_deactivated(workflow.automation.workspace)


@pytest.mark.django_db
def test_core_code_workflow_action_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    service = enterprise_data_fixture.create_enterprise_core_code_service()
    workflow_action = CoreCodeWorkflowAction.objects.create(
        page=page,
        element=element,
        event=EventTypes.CLICK,
        service=service,
        order=0,
    )

    enterprise_data_fixture.delete_all_licenses()

    dispatch_context = BuilderDispatchContext(HttpRequest(), page)
    with pytest.raises(FeaturesNotAvailableError):
        BuilderWorkflowActionService().dispatch_action(
            user, workflow_action, dispatch_context
        )


@pytest.mark.django_db
def test_core_code_automation_node_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    service = enterprise_data_fixture.create_enterprise_core_code_service()
    node = enterprise_data_fixture.create_automation_node(
        workflow=workflow,
        type=CoreCodeNodeType.type,
        service=service,
    )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, FakeDispatchContext())

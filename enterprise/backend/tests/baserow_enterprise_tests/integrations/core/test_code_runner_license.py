from django.http import HttpRequest
from django.test import override_settings

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
from baserow_enterprise.apps import register_code_runner_features
from baserow_enterprise.automation.nodes.node_types import CoreCodeNodeType
from baserow_enterprise.builder.workflow_actions.models import CoreCodeWorkflowAction
from baserow_enterprise.builder.workflow_actions.workflow_action_types import (
    CoreCodeActionType,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError


def unregister_code_runner_features(
    builder_workflow_action_registry,
    automation_node_type_registry,
    service_type_registry,
    code_runner_type_registry,
):
    builder_workflow_action_registry.registry.pop("code", None)
    automation_node_type_registry.registry.pop("code", None)
    service_type_registry.registry.pop("code", None)
    code_runner_type_registry.registry.pop("wasmtime_quickjs", None)


@pytest.fixture
def code_runner_registered(
    mutable_builder_workflow_action_registry,
    mutable_automation_node_type_registry,
    mutable_service_type_registry,
    mutable_code_runner_type_registry,
):
    unregister_code_runner_features(
        mutable_builder_workflow_action_registry,
        mutable_automation_node_type_registry,
        mutable_service_type_registry,
        mutable_code_runner_type_registry,
    )

    with override_settings(ENTERPRISE_CODE_RUNNER_DEFAULT_TYPE="wasmtime_quickjs"):
        register_code_runner_features()
        yield


@pytest.mark.django_db
def test_core_code_workflow_action_requires_enterprise_license(
    enterprise_data_fixture, code_runner_registered
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

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        assert not workflow_action_type.is_deactivated(page.builder.workspace)


@pytest.mark.django_db
def test_core_code_automation_node_requires_enterprise_license(
    enterprise_data_fixture, code_runner_registered
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

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        assert not node_type.is_deactivated(workflow.automation.workspace)


@pytest.mark.django_db
def test_core_code_workflow_action_dispatch_requires_enterprise_license(
    enterprise_data_fixture, code_runner_registered
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
    enterprise_data_fixture, code_runner_registered
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

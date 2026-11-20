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
from baserow.contrib.integrations.oauth_account.exceptions import (
    ServiceTypeNotAllowed,
)
from baserow.contrib.integrations.oauth_account.service import OAuthAccountService
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.automation.nodes.node_types import (
    MicrosoftTeamsWriteMessageActionNodeType,
)
from baserow_enterprise.builder.workflow_actions.models import (
    MicrosoftTeamsWriteMessageWorkflowAction,
)
from baserow_enterprise.builder.workflow_actions.workflow_action_types import (
    MicrosoftTeamsWriteMessageActionType,
)
from baserow_enterprise.features import MICROSOFT_TEAMS, TEAMS
from baserow_enterprise.license_types import (
    AdvancedLicenseType,
    EnterpriseLicenseType,
    EnterpriseWithoutSupportLicenseType,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError

TYPE = "microsoft_teams_write_message"


def test_microsoft_teams_feature_is_advanced_and_enterprise():
    assert MICROSOFT_TEAMS != TEAMS
    assert MICROSOFT_TEAMS in AdvancedLicenseType.features
    assert MICROSOFT_TEAMS in EnterpriseWithoutSupportLicenseType.features
    assert MICROSOFT_TEAMS in EnterpriseLicenseType.features


@pytest.mark.django_db
def test_microsoft_teams_service_type_requires_license(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()
    service_type = service_type_registry.get(TYPE)

    enterprise_data_fixture.delete_all_licenses()
    assert service_type.is_deactivated(workspace)
    with pytest.raises(FeaturesNotAvailableError):
        service_type.raise_if_deactivated(workspace)

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        assert not service_type.is_deactivated(workspace)


@pytest.mark.django_db
def test_signing_in_for_teams_requires_license(enterprise_data_fixture):
    workspace = enterprise_data_fixture.create_workspace()

    service = OAuthAccountService(integration_type_registry.get("microsoft"))

    enterprise_data_fixture.delete_all_licenses()
    with pytest.raises(ServiceTypeNotAllowed):
        service.get_scopes_for_service_types([TYPE], workspace)

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        scopes = service.get_scopes_for_service_types([TYPE], workspace)
    assert "ChannelMessage.Send" in scopes
    assert "ChatMessage.Send" in scopes


@pytest.mark.django_db
def test_microsoft_teams_workflow_action_requires_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    workflow_action_type = MicrosoftTeamsWriteMessageActionType()

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
def test_microsoft_teams_workflow_action_dispatch_requires_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    service = enterprise_data_fixture.create_microsoft_teams_write_message_service()
    workflow_action = MicrosoftTeamsWriteMessageWorkflowAction.objects.create(
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
def test_microsoft_teams_automation_node_requires_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    node_type = MicrosoftTeamsWriteMessageActionNodeType()

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
def test_microsoft_teams_automation_node_dispatch_requires_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    service = enterprise_data_fixture.create_microsoft_teams_write_message_service()
    node = enterprise_data_fixture.create_automation_node(
        workflow=workflow,
        type=MicrosoftTeamsWriteMessageActionNodeType.type,
        service=service,
    )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, FakeDispatchContext())

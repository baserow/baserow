from django.http import HttpRequest
from django.test import override_settings

import pytest

from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.automation.nodes.node_types import CoreXLSFileReaderNodeType
from baserow_enterprise.builder.workflow_actions.models import (
    CoreXLSFileReaderWorkflowAction,
)
from baserow_enterprise.builder.workflow_actions.workflow_action_types import (
    CoreXLSFileReaderActionType,
)
from baserow_enterprise.features import XLS_FILE_READER
from baserow_enterprise.license_types import (
    AdvancedLicenseType,
    EnterpriseLicenseType,
    EnterpriseWithoutSupportLicenseType,
)
from baserow_premium.license.exceptions import FeaturesNotAvailableError


def test_core_xls_file_reader_feature_is_enterprise_only():
    assert XLS_FILE_READER not in AdvancedLicenseType.features
    assert XLS_FILE_READER in EnterpriseWithoutSupportLicenseType.features
    assert XLS_FILE_READER in EnterpriseLicenseType.features


@pytest.mark.django_db
def test_core_xls_file_reader_data_source_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("xls_file_reader")

    enterprise_data_fixture.delete_all_licenses()

    assert service_type.is_deactivated(page.builder.workspace)

    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().create_data_source(
            user, page=page, service_type=service_type
        )

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        assert not service_type.is_deactivated(page.builder.workspace)


@pytest.mark.django_db
def test_core_xls_file_reader_data_source_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("xls_file_reader")

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        data_source = DataSourceService().create_data_source(
            user, page=page, service_type=service_type
        )

    enterprise_data_fixture.delete_all_licenses()

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )
    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().dispatch_data_source(user, data_source, dispatch_context)


@pytest.mark.django_db
def test_core_xls_file_reader_data_source_update_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    service_type = service_type_registry.get("xls_file_reader")

    with override_settings(DEBUG=True):
        enterprise_data_fixture.enable_enterprise()
        data_source = DataSourceService().create_data_source(
            user, page=page, service_type=service_type
        )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().update_data_source(
            user, data_source, service_type=service_type
        )


@pytest.mark.django_db
def test_core_xls_file_reader_workflow_action_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    workflow_action_type = CoreXLSFileReaderActionType()

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
def test_core_xls_file_reader_workflow_action_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service()
    workflow_action = CoreXLSFileReaderWorkflowAction.objects.create(
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
def test_core_xls_file_reader_automation_node_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    node_type = CoreXLSFileReaderNodeType()

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
def test_core_xls_file_reader_automation_node_dispatch_requires_enterprise_license(
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    workflow = enterprise_data_fixture.create_automation_workflow(user)
    service = enterprise_data_fixture.create_enterprise_core_xls_file_reader_service()
    node = enterprise_data_fixture.create_automation_node(
        workflow=workflow,
        type=CoreXLSFileReaderNodeType.type,
        service=service,
    )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, FakeDispatchContext())

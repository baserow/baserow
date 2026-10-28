import json
from datetime import datetime

from django.test import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    NotificationWorkflowActionType,
)
from baserow.core.code_runner.exceptions import (
    CodeRunnerExecutionError,
    CodeRunnerResultError,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.test_utils.pytest_conftest import FakeDispatchContext
from baserow_enterprise.apps import register_code_runner_features
from baserow_enterprise.builder.workflow_actions.models import CoreCodeWorkflowAction

pytestmark = pytest.mark.django_db


class FakeCodeRunnerType:
    def __init__(self, result=None, exception=None):
        self.result = result or {"newValue": 4}
        self.exception = exception
        self.calls = []

    def run(self, context_data, code):
        self.calls.append((context_data, code))
        if self.exception:
            raise self.exception
        return self.result


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


def test_core_code_service_type_dispatch_resolves_injections(
    enterprise_data_fixture, monkeypatch, code_runner_registered
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(
        code="function main(context) { return { newValue: 4 } }"
    )
    service.injections.create(name="value", formula="get('value')")

    code_runner = FakeCodeRunnerType()
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    dispatch_result = service.get_type().dispatch(
        service,
        FakeDispatchContext(context={"value": 2}),
    )

    assert dispatch_result.data == {"newValue": 4}
    assert code_runner.calls == [
        (
            {"value": 2},
            "function main(context) { return { newValue: 4 } }",
        )
    ]


def test_core_code_service_type_dispatch_converts_injections_to_json_values(
    enterprise_data_fixture, monkeypatch, code_runner_registered
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(
        code="function main(context) { return { value: context.value } }"
    )
    service.injections.create(name="value", formula="get('value')")

    code_runner = FakeCodeRunnerType()
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    service.get_type().dispatch(
        service,
        FakeDispatchContext(context={"value": datetime(2024, 12, 17, 12, 0, 0)}),
    )

    assert code_runner.calls == [
        (
            {"value": "2024-12-17T12:00:00"},
            "function main(context) { return { value: context.value } }",
        )
    ]


def test_core_code_service_type_dispatch_maps_execution_errors(
    enterprise_data_fixture, monkeypatch, code_runner_registered
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(code="")
    code_runner = FakeCodeRunnerType(exception=CodeRunnerExecutionError("boom"))
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    with pytest.raises(UnexpectedDispatchException, match="boom"):
        service.get_type().dispatch(service, FakeDispatchContext())


def test_core_code_service_type_dispatch_maps_result_errors(
    enterprise_data_fixture, monkeypatch, code_runner_registered
):
    service = enterprise_data_fixture.create_enterprise_core_code_service(code="")
    code_runner = FakeCodeRunnerType(exception=CodeRunnerResultError("object required"))
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    with pytest.raises(
        ServiceImproperlyConfiguredDispatchException, match="object required"
    ):
        service.get_type().dispatch(service, FakeDispatchContext())


def test_core_code_workflow_action_dispatch_returns_formula_used_public_result(
    api_client, enterprise_data_fixture, monkeypatch, code_runner_registered
):
    user, token = enterprise_data_fixture.create_user_and_token()
    enterprise_data_fixture.enable_enterprise()
    monkeypatch.setattr(
        "baserow_enterprise.builder.workflow_actions.workflow_action_types."
        "LicenseHandler.raise_if_workspace_doesnt_have_feature",
        lambda *args, **kwargs: None,
    )

    builder = enterprise_data_fixture.create_builder_application(user=user)
    page = enterprise_data_fixture.create_builder_page(user=user, builder=builder)
    element = enterprise_data_fixture.create_builder_button_element(page=page)
    service = enterprise_data_fixture.create_enterprise_core_code_service(
        code="function main() { return { publicValue: 42, hiddenValue: 7 } }"
    )
    workflow_action = CoreCodeWorkflowAction.objects.create(
        page=page,
        element=element,
        event=EventTypes.CLICK,
        service=service,
        order=0,
    )

    BuilderWorkflowActionService().create_workflow_action(
        user,
        NotificationWorkflowActionType(),
        page=page,
        element=element,
        event=EventTypes.CLICK,
        title=f"get('previous_action.{workflow_action.id}.publicValue')",
    )

    code_runner = FakeCodeRunnerType(
        result={"publicValue": 42, "hiddenValue": 7},
    )
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: code_runner,
    )

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )
    response = api_client.post(
        url,
        {
            "metadata": json.dumps(
                {
                    "previous_action": {
                        "current_dispatch_id": "test-dispatch-id",
                    }
                }
            )
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"publicValue": 42}
    assert code_runner.calls == [
        (
            {},
            "function main() { return { publicValue: 42, hiddenValue: 7 } }",
        )
    ]


@pytest.mark.parametrize("state", [None, "test_clone", "live"])
def test_untrusted_automation_code_nodes_require_consent(
    enterprise_data_fixture,
    enable_enterprise,
    monkeypatch,
    code_runner_registered,
    state,
):
    """Draft, test, and live nodes cannot reach the runner until explicitly trusted."""

    from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler

    automation = enterprise_data_fixture.create_automation_application()
    workflow = enterprise_data_fixture.create_automation_workflow(
        automation=automation, untrusted_content=True
    )
    service = enterprise_data_fixture.create_enterprise_core_code_service(
        code="function main(context) { return { newValue: 4 } }"
    )
    original_node = enterprise_data_fixture.create_automation_node(
        workflow=workflow, type="code", service=service
    )
    node = original_node
    handler = AutomationWorkflowHandler()
    if state:
        clone, mapping = handler._clone_workflow(workflow, state)
        node = type(node).objects.get(
            id=mapping["automation_workflow_nodes"][original_node.id]
        )
        assert clone.workflows.get().untrusted_content is True

    runner = FakeCodeRunnerType()
    monkeypatch.setattr(
        "baserow_enterprise.integrations.core.service_types.get_code_runner",
        lambda: runner,
    )
    with pytest.raises(ServiceImproperlyConfiguredDispatchException, match="trusted"):
        node.get_type().dispatch(node, FakeDispatchContext())
    assert runner.calls == []

    workflow.untrusted_content = False
    workflow.save(update_fields=["untrusted_content"])
    if state:
        clone, mapping = handler._clone_workflow(workflow, state)
        node = type(node).objects.get(
            id=mapping["automation_workflow_nodes"][original_node.id]
        )
        assert clone.workflows.get().untrusted_content is False
    else:
        node = type(node).objects.get(id=original_node.id)
    result = node.get_type().dispatch(node, FakeDispatchContext())
    assert result.data == {"newValue": 4}
    assert runner.calls == [({}, service.code)]


@pytest.mark.parametrize("application_kind", ["builder", "automation"])
@pytest.mark.parametrize(
    "config_values,external",
    [
        ({}, True),
        ({"is_duplicate": True}, False),
        ({"is_publishing": True}, False),
        ({"is_template": True}, False),
    ],
)
def test_code_action_and_node_detect_untrusted_content_during_copy(
    enterprise_data_fixture,
    code_runner_registered,
    application_kind,
    config_values,
    external,
):
    """Code actions/nodes mark their application's cache without trusting file metadata."""

    from baserow.core.registries import ImportExportConfig

    fixture = enterprise_data_fixture
    application = getattr(fixture, f"create_{application_kind}_application")()
    service = fixture.create_enterprise_core_code_service(
        code="function main(context) { return { value: 1 } }"
    )
    if application_kind == "builder":
        page = fixture.create_builder_page(builder=application)
        element = fixture.create_builder_button_element(page=page)
        CoreCodeWorkflowAction.objects.create(
            page=page, element=element, service=service, event=EventTypes.CLICK, order=0
        )
    else:
        workflow = fixture.create_automation_workflow(automation=application)
        fixture.create_automation_node(workflow=workflow, type="code", service=service)

    application_type = application.get_type()
    config = ImportExportConfig(include_permission_data=False, **config_values)
    serialized = application_type.export_serialized(application, config)
    serialized_owner = (
        serialized if application_kind == "builder" else serialized["workflows"][0]
    )
    assert serialized_owner["untrusted_content"] is external
    assert "import_report" not in serialized_owner
    serialized_owner["import_report"] = [{"type": "invalid", "id": -1}]
    serialized_owner["untrusted_content"] = False
    imported = application_type.import_serialized(
        application.workspace, serialized, config, {}
    )
    imported.refresh_from_db()
    owner = imported if application_kind == "builder" else imported.workflows.get()
    assert owner.untrusted_content is external

    assert len(owner.import_report) == 1
    entry = owner.import_report[0]
    if application_kind == "builder":
        action = CoreCodeWorkflowAction.objects.get(page__builder=imported)
        assert entry == {
            "type": "builder_code_action",
            "id": action.id,
            "page_id": action.page_id,
            "page_name": action.page.name,
            "element_id": action.element_id,
        }
    else:
        from baserow_enterprise.automation.nodes.models import CoreCodeActionNode

        node = CoreCodeActionNode.objects.get(workflow=owner)
        assert entry == {
            "type": "automation_code_node",
            "id": node.id,
            "label": node.label,
            "workflow_id": owner.id,
        }


def test_workflow_content_detection_does_not_leak_to_siblings(
    enterprise_data_fixture, code_runner_registered
):
    """One Automation can contain a blocked code workflow and a trusted clean one."""

    from baserow.core.deferred_callbacks import deferred_callback_context
    from baserow.core.registries import ImportExportConfig

    fixture = enterprise_data_fixture
    automation = fixture.create_automation_application()
    unsafe = fixture.create_automation_workflow(automation=automation, name="Code")
    safe = fixture.create_automation_workflow(automation=automation, name="Clean")
    fixture.create_automation_node(workflow=unsafe, type="code")
    config = ImportExportConfig(include_permission_data=False)
    application_type = automation.get_type()
    serialized = application_type.export_serialized(automation, config)
    assert "untrusted_content" not in serialized
    assert {w["name"]: w["untrusted_content"] for w in serialized["workflows"]} == {
        "Code": True,
        "Clean": False,
    }
    for workflow in serialized["workflows"]:
        workflow["untrusted_content"] = False
    with deferred_callback_context():
        imported = application_type.import_serialized(
            automation.workspace, serialized, config, {}
        )
    assert dict(imported.workflows.values_list("name", "untrusted_content")) == {
        "Code": True,
        "Clean": False,
    }

    imported_code = imported.workflows.get(name="Code")
    imported_clean = imported.workflows.get(name="Clean")
    assert len(imported_code.import_report) == 1
    assert imported_code.import_report[0]["workflow_id"] == imported_code.id
    assert imported_clean.import_report == []

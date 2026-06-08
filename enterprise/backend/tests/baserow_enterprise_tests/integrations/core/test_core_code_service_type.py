import json

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

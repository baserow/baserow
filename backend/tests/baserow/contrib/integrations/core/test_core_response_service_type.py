from django.core.exceptions import ValidationError

import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.history.models import (
    AutomationWorkflowHistoryResponse,
)
from baserow.contrib.integrations.core.api.serializers import (
    CoreResponseHeaderSerializer,
)
from baserow.contrib.integrations.core.constants import RESPONSE_BODY_TYPE
from baserow.contrib.integrations.core.models import CoreResponseHeader
from baserow.contrib.integrations.core.service_types import (
    CoreResponseServiceType,
    ensure_http_header_value,
    ensure_http_status_code,
)
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW, BaserowFormulaObject
from baserow.core.services.exceptions import InvalidContextContentDispatchException


@pytest.mark.parametrize(
    "header_name",
    [
        "Set-Cookie",
        "clear-site-data",
        "CoNtEnT-SeCuRiTy-PoLiCy",
        "StRiCt-TrAnSpOrT-SeCuRiTy",
    ],
)
def test_response_header_serializer_rejects_shared_origin_state_headers(header_name):
    serializer = CoreResponseHeaderSerializer(
        data={"key": header_name, "value": "'value'"}
    )

    assert not serializer.is_valid()
    assert "shared Baserow origin" in str(serializer.errors["key"][0])


@pytest.mark.django_db
def test_response_service_dispatch_writes_workflow_response(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "201", mode=BASEROW_FORMULA_MODE_RAW
            ),
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": "'Created'",
        },
    )
    CoreResponseHeader.objects.create(
        service=node.service.specific,
        key="X-Test",
        value="'yes'",
    )
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    dispatch_context = AutomationDispatchContext(workflow, history)

    result = node.get_type().dispatch(node, dispatch_context)

    response = AutomationWorkflowHistoryResponse.objects.get(workflow_history=history)
    assert result.data == {
        "response_written": True,
        "ignored": False,
        "status_code": 201,
        "headers": {"X-Test": "yes"},
        "body": "Created",
        "body_type": RESPONSE_BODY_TYPE.TEXT,
    }
    assert response.status_code == 201
    assert response.body_type == RESPONSE_BODY_TYPE.TEXT
    assert response.body == "Created"
    assert response.headers == {"X-Test": "yes"}
    assert response.source_node_id == node.id
    assert response.is_default is False


@pytest.mark.django_db
def test_response_service_dispatch_drops_body_for_204(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "204", mode=BASEROW_FORMULA_MODE_RAW
            ),
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": "'Not returned'",
        },
    )
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    dispatch_context = AutomationDispatchContext(workflow, history)

    result = node.get_type().dispatch(node, dispatch_context)

    response = AutomationWorkflowHistoryResponse.objects.get(workflow_history=history)
    assert result.data["body"] is None
    assert result.data["body_type"] == RESPONSE_BODY_TYPE.EMPTY
    assert response.body is None
    assert response.body_type == RESPONSE_BODY_TYPE.EMPTY


@pytest.mark.django_db
def test_response_service_does_not_resolve_body_for_204(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "204", mode=BASEROW_FORMULA_MODE_RAW
            ),
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": "get('unavailable.value')",
        },
    )
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    dispatch_context = AutomationDispatchContext(workflow, history)

    result = node.get_type().dispatch(node, dispatch_context)

    response = AutomationWorkflowHistoryResponse.objects.get(workflow_history=history)
    assert result.data["body"] is None
    assert result.data["body_type"] == RESPONSE_BODY_TYPE.EMPTY
    assert response.body is None
    assert response.body_type == RESPONSE_BODY_TYPE.EMPTY


@pytest.mark.parametrize("value", [99, 600, "not-a-status-code"])
def test_ensure_http_status_code_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        ensure_http_status_code(value)


def test_ensure_http_header_value_accepts_valid_value():
    assert ensure_http_header_value("text/plain; charset=utf-8") == (
        "text/plain; charset=utf-8"
    )


@pytest.mark.parametrize("value", ["bad\rvalue", "bad\nvalue"])
def test_ensure_http_header_value_rejects_newlines(value):
    with pytest.raises(ValidationError, match="cannot contain"):
        ensure_http_header_value(value)


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["bad\rvalue", "bad\nvalue"])
def test_response_service_rejects_dynamic_header_newlines(data_fixture, value):
    """Invalid resolved headers use the normal dispatch validation error path."""

    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": BaserowFormulaObject.create(
                "204", mode=BASEROW_FORMULA_MODE_RAW
            )
        },
    )
    CoreResponseHeader.objects.create(
        service=node.service.specific,
        key="X-Test",
        value=BaserowFormulaObject.create(value, mode=BASEROW_FORMULA_MODE_RAW),
    )
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    dispatch_context = AutomationDispatchContext(workflow, history)

    with pytest.raises(InvalidContextContentDispatchException, match="cannot contain"):
        node.get_type().dispatch(node, dispatch_context)

    assert not AutomationWorkflowHistoryResponse.objects.filter(
        workflow_history=history
    ).exists()


def test_response_service_status_code_serializer_defaults_to_raw_204():
    status_code_field = CoreResponseServiceType().serializer_field_overrides[
        "status_code"
    ]

    assert status_code_field.default == BaserowFormulaObject.create(
        "204", mode=BASEROW_FORMULA_MODE_RAW
    )


@pytest.mark.django_db
def test_response_service_dispatch_first_response_wins(data_fixture):
    workflow = data_fixture.create_automation_workflow()
    node = data_fixture.create_core_response_action_node(
        workflow=workflow,
        service_kwargs={
            "status_code": 202,
            "body_type": RESPONSE_BODY_TYPE.TEXT,
            "body": "'First'",
        },
    )
    history = data_fixture.create_automation_workflow_history(workflow=workflow)
    dispatch_context = AutomationDispatchContext(workflow, history)

    first_result = node.get_type().dispatch(node, dispatch_context)
    second_result = node.get_type().dispatch(node, dispatch_context)

    response = AutomationWorkflowHistoryResponse.objects.get(workflow_history=history)
    assert first_result.data["response_written"] is True
    assert second_result.data["response_written"] is False
    assert second_result.data["ignored"] is True
    assert response.status_code == 202
    assert response.body == "First"

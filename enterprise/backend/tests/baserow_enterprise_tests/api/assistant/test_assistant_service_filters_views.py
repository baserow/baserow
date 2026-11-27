from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
    FilterState,
)
from baserow_enterprise.assistant.exceptions import (
    AssistantModelDisabledError,
    ServiceFilterGenerationFailed,
)
from baserow_enterprise.assistant.service_filters import ServiceFilterRequestResult
from baserow_enterprise.assistant.service_filters.agent import ServiceFilterChanges

VIEWS = "baserow_enterprise.api.assistant.views"


def _data_source(data_fixture, user):
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    return data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table
    )


def _post(api_client, token, chat_uuid=None, **data):
    return api_client.post(
        reverse("assistant:actions"),
        data={
            "action": "update_service_filters",
            "prompt": data.pop("prompt"),
            "parameters": data,
            **({"chat_uuid": str(chat_uuid)} if chat_uuid else {}),
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(f"{VIEWS}.check_lm_ready_or_raise")
@patch(f"{VIEWS}.resolve_assistant_model")
@patch("baserow_enterprise.assistant.actions.run_service_filter_request")
def test_service_filters_runs_the_request(
    mock_run, mock_resolve, mock_check, api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    data_source = _data_source(enterprise_data_fixture, user)
    mock_run.return_value = ServiceFilterRequestResult(
        target_kind="builder_data_source",
        target_id=data_source.id,
        target_name=data_source.name,
        changed=True,
        summary="Added a filter.",
        state=FilterState("AND", (), ()),
    )

    response = _post(
        api_client,
        token,
        kind="builder_data_source",
        id=data_source.id,
        prompt="Name is the ID page parameter",
    )

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "changed": True,
        "summary": "Added a filter.",
        "result": {},
    }
    args, kwargs = mock_run.call_args
    assert args[1:] == (
        "builder_data_source",
        data_source.id,
        "Name is the ID page parameter",
    )
    # The realtime update must also reach the tab that made the request.
    assert args[0].user.web_socket_id is None
    assert args[0].workspace.id == data_source.page.builder.workspace_id
    assert kwargs["model_profile"] is mock_resolve.return_value
    assert kwargs["table_id"] is None
    mock_check.assert_called_once_with(model_profile=mock_resolve.return_value)

    # The table picked in the editor, not saved yet, is passed on.
    response = _post(
        api_client,
        token,
        kind="builder_data_source",
        id=data_source.id,
        prompt="Only done tasks",
        table_id=42,
    )
    assert response.status_code == 200, response.json()
    assert mock_run.call_args.kwargs["table_id"] == 42


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(f"{VIEWS}.check_lm_ready_or_raise")
@patch(f"{VIEWS}.resolve_assistant_model")
@patch("baserow_enterprise.assistant.actions.run_service_filter_request")
def test_service_filters_errors(
    mock_run, mock_resolve, mock_check, api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    data_source = _data_source(enterprise_data_fixture, user)

    response = _post(api_client, token, kind="builder_data_source", id=0, prompt="x")
    assert response.status_code == 404
    assert (
        response.json()["error"]
        == "ERROR_ASSISTANT_SERVICE_FILTER_TARGET_DOES_NOT_EXIST"
    )

    other_user, other_token = enterprise_data_fixture.create_user_and_token()
    response = _post(
        api_client,
        other_token,
        kind="builder_data_source",
        id=data_source.id,
        prompt="x",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    mock_check.side_effect = AssistantModelDisabledError()
    response = _post(
        api_client, token, kind="builder_data_source", id=data_source.id, prompt="x"
    )
    assert response.json()["error"] == "ERROR_ASSISTANT_MODEL_DISABLED"

    mock_check.side_effect = None
    mock_run.side_effect = ServiceFilterGenerationFailed()
    response = _post(
        api_client, token, kind="builder_data_source", id=data_source.id, prompt="x"
    )
    assert response.status_code == 400
    assert (
        response.json()["error"] == "ERROR_ASSISTANT_SERVICE_FILTER_GENERATION_FAILED"
    )

    response = _post(api_client, token, kind="nope", id=data_source.id, prompt="x")
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body",
    [
        {"action": "unknown", "prompt": "x", "parameters": {}},
        {"action": "update_service_filters", "prompt": "x", "parameters": {}},
        {
            "action": "update_service_filters",
            "prompt": "",
            "parameters": {"kind": "builder_data_source", "id": 1},
        },
    ],
)
@patch("baserow_enterprise.assistant.actions.run_service_filter_request")
def test_assistant_action_rejects_invalid_requests(
    mock_run, api_client, enterprise_data_fixture, body
):
    """Reject unsupported actions and malformed parameters before executing an agent."""
    _, token = enterprise_data_fixture.create_user_and_token()
    response = api_client.post(
        reverse("assistant:actions"),
        data=body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    mock_run.assert_not_called()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(f"{VIEWS}.check_lm_ready_or_raise")
@patch(f"{VIEWS}.resolve_assistant_model")
@patch("baserow_enterprise.assistant.service_filters.handler.run_service_filter_agent")
def test_follow_up_after_the_selected_table_is_saved(
    generate, mock_resolve, mock_check, api_client, enterprise_data_fixture
):
    user, token = enterprise_data_fixture.create_user_and_token()
    source = _data_source(enterprise_data_fixture, user)
    service = source.service.specific
    table = service.table
    field = enterprise_data_fixture.create_text_field(table=table, name="Name")
    service.table = None
    service.save(update_fields=["table"])
    generate.side_effect = [
        ServiceFilterChanges(
            operations=[
                FilterOperation(
                    op="add_filter", field_id=field.id, type="contains", value="Davide"
                )
            ],
            summary="Filtered by name.",
        ),
        ServiceFilterChanges(operations=[], summary="Already set."),
    ]
    params = dict(
        kind="builder_data_source",
        id=source.id,
        chat_uuid=uuid4(),
        prompt="Name contains Davide",
    )
    first = _post(api_client, token, **params, table_id=table.id)
    assert first.status_code == 200, first.data
    assert first.data["changed"]
    service.refresh_from_db()
    assert service.table_id == table.id
    follow_up = _post(api_client, token, **params)
    assert follow_up.status_code == 200, follow_up.data
    assert not follow_up.data["changed"]
    assert service.service_filters.get().field_id == field.id
    assert _post(api_client, token, **params, table_id=table.id + 1).status_code == 404
    assert generate.call_count == 2

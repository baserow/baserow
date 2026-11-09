from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

import pytest

from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterState,
)
from baserow_enterprise.assistant.exceptions import (
    AssistantModelDisabledError,
    ServiceFilterGenerationFailed,
)
from baserow_enterprise.assistant.service_filters import ServiceFilterRequestResult

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


def _post(api_client, token, **data):
    return api_client.post(
        reverse("assistant:service_filters"),
        data=data,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch(f"{VIEWS}.check_lm_ready_or_raise")
@patch(f"{VIEWS}.resolve_assistant_model")
@patch(f"{VIEWS}.run_service_filter_request")
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
    assert response.json() == {"changed": True, "summary": "Added a filter."}
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
@patch(f"{VIEWS}.run_service_filter_request")
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

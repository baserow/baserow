from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from requests import exceptions as request_exceptions

from baserow.contrib.database.fields.operations import UpdateFieldOperationType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)


@contextmanager
def mock_advocate_request(body=None, status_code=200, raise_exception=None):
    """
    Answers the outbound call the HTTP service makes, the way the service's own
    tests do, so nothing here reaches the network.
    """

    mock_response = Mock()
    mock_response.json.return_value = body
    mock_response.text = str(body)
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.status_code = status_code

    with patch("advocate.request") as mock_request:

        def side_effect(*args, **kwargs):
            if raise_exception is not None:
                raise raise_exception
            return mock_response

        mock_request.side_effect = side_effect
        yield mock_request


def _table_with_name(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    return table, table.field_set.get(name="Name")


def _http_action(data_fixture, button_field, url="'http://example.notexist/'"):
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.url = url
    service.save()
    return action


@pytest.mark.django_db
def test_a_click_remembers_what_the_endpoint_answered(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    with mock_advocate_request({"title": "Sample Slide Show"}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    action.service.refresh_from_db()
    assert action.service.sample_data["data"]["body"] == {"title": "Sample Slide Show"}
    assert action.service.sample_data["data"]["status_code"] == 200


@pytest.mark.django_db
def test_the_remembered_answer_describes_the_action_to_the_editor(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    service = action.service.specific
    assert service.get_type().generate_schema(service)["properties"].get("body") is None

    with mock_advocate_request({"title": "Sample Slide Show"}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    service.refresh_from_db()
    schema = service.get_type().generate_schema(service)
    assert "title" in schema["properties"]["body"]["properties"]


@pytest.mark.django_db
def test_a_click_by_someone_who_cannot_configure_remembers_nothing(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    def only_clicking(self, actor, operation_name, *args, **kwargs):
        # Clicking is allowed, configuring the field is not (ADR 006 section 7).
        if operation_name == UpdateFieldOperationType.type:
            return False
        return True

    with mock_advocate_request({"title": "Sample Slide Show"}):
        with patch("baserow.core.handler.CoreHandler.check_permissions", only_clicking):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_a_failed_request_is_not_remembered(data_fixture):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    with mock_advocate_request(
        raise_exception=request_exceptions.RequestException("nope")
    ):
        with pytest.raises(WorkflowActionDispatchError):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_an_oversized_answer_is_not_remembered(data_fixture, settings):
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)
    settings.DATABASE_BUTTON_SAMPLE_DATA_MAX_BYTES = 32

    with mock_advocate_request({"title": "x" * 200}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_a_row_action_never_remembers_a_row(data_fixture):
    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'Jane'", enabled=True)

    DatabaseWorkflowActionService().dispatch_workflow_actions(user, button_field, row)

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_remembering_one_answer_does_not_simulate_the_rest(data_fixture):
    """
    Guards the trap in `ServiceType.dispatch`: `use_sample_data` makes a service
    that is not being updated answer from its stored sample data instead of
    running. Capturing here must never put a dispatch into that mode, or a row
    action after an HTTP one would quietly stop writing.
    """

    user = data_fixture.create_user()
    table, name_field = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(data_fixture, button_field)
    row_action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = row_action.service.specific
    service.table = table
    service.save()
    service.field_mappings.create(field=name_field, value="'Jane'", enabled=True)

    model = table.get_model()
    with mock_advocate_request({"title": "Sample Slide Show"}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    written = [getattr(r, f"field_{name_field.id}") for r in model.objects.all()]
    assert written.count("Jane") == 2


@pytest.mark.django_db
def test_a_click_cannot_reach_an_internal_address(data_fixture, settings):
    """
    The button field is a new way to make this installation send a request, so
    the guard that stops one reaching Baserow's own network has to hold on this
    path too. Nothing is mocked here: `advocate` refuses the address itself.
    """

    settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS = False
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(
        data_fixture, button_field, url="'http://127.0.0.1:8000/api/settings/'"
    )

    with pytest.raises(WorkflowActionDispatchError):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    # A refused address is a failure like any other, so it leaves no trace in
    # the button's configuration either.
    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_a_failed_request_is_reported_without_naming_the_url(data_fixture):
    """
    A URL that cannot be reached is a misconfiguration, not a server error, so
    the clicker is told which action failed. The service's own message names
    the URL and its query string, which is where an API key would be, so it
    does not travel.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(
        data_fixture, button_field, url="'http://example.notexist/p?token=shhh'"
    )

    with mock_advocate_request(
        raise_exception=request_exceptions.ConnectionError("nope")
    ):
        with pytest.raises(WorkflowActionDispatchError) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert raised.value.position == 1
    assert "token=shhh" not in raised.value.message
    assert "example.notexist" not in raised.value.message


@pytest.mark.django_db
def test_an_unsuccessful_answer_does_not_replace_what_was_learned(data_fixture):
    """
    An endpoint that answers 404 with an error page, or times out, is still a
    successful dispatch as far as the service is concerned. Remembering it
    would drop the shape an earlier click learned, and with it every explorer
    node the actions after this one point at.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    with mock_advocate_request({"title": "Sample Slide Show"}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    with mock_advocate_request({"error": "not found"}, status_code=404):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    action.service.refresh_from_db()
    assert action.service.sample_data["data"]["body"] == {"title": "Sample Slide Show"}

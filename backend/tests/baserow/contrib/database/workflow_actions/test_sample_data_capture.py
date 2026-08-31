from contextlib import contextmanager
from smtplib import SMTPNotSupportedError
from unittest.mock import Mock, patch

import pytest
from loguru import logger
from requests import exceptions as request_exceptions

from baserow.contrib.database.fields.operations import UpdateFieldOperationType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.service import (
    EXTERNAL_DISPATCH_FAILED_MESSAGE,
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
    # The service streams the body in so it can stop an endpoint that
    # sends more than this installation accepts.
    mock_response.iter_content.return_value = iter(
        [str(mock_response.text or "").encode()]
    )

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

    # The reason is kept rather than a shape, so the editor stops asking for a
    # click that has already happened. It describes nothing, so the schema is
    # not built from it.
    action.service.refresh_from_db()
    assert "32 bytes" in action.service.sample_data["_error"]
    service = action.service.specific
    assert service.get_type().generate_schema(service)["properties"].get("body") is None


@pytest.mark.django_db
def test_the_editor_is_told_when_a_click_answered_with_an_error(data_fixture):
    """
    A 404, or a timeout, is a successful dispatch that describes nothing. The
    note asking for a click would otherwise stay exactly as it was, so nobody
    could tell the click had happened.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(
        data_fixture, button_field, url="'http://example.notexist/p?token=shhh'"
    )

    with mock_advocate_request({"error": "not found"}, status_code=404):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    action.service.refresh_from_db()
    reason = action.service.sample_data["_error"]
    assert "404" in reason
    # Whoever clicks may not be allowed to see how the button was set up.
    assert "token=shhh" not in reason
    assert "example.notexist" not in reason


@pytest.mark.django_db
def test_a_failed_click_does_not_replace_an_answer_already_learned(data_fixture):
    """
    A shape an earlier click learned is worth more than an explanation of the
    latest one: every action pointing at that shape would break with it.
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
    assert "_error" not in action.service.sample_data
    assert action.service.sample_data["data"]["body"] == {"title": "Sample Slide Show"}


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


@pytest.mark.django_db
def test_what_the_action_was_given_is_still_reported(data_fixture):
    """
    Only a message about the address is withheld. One about the values the
    action was handed says nothing about where the request was going, and it
    is the only thing telling the clicker what to fix.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field, url="'http://example.notexist/'")

    # Configured rather than raised by hand, so the failure is the one the
    # service really produces. Nothing is mocked: the body is refused before
    # the request is built, so no call leaves the process.
    service = action.service.specific
    service.http_method = "POST"
    service.body_type = "json"
    service.body_content = "'not json{'"
    service.save()

    with pytest.raises(WorkflowActionDispatchError) as raised:
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert raised.value.message == "The body is not a valid JSON"


@pytest.mark.django_db
def test_the_lock_outlives_every_request_the_click_may_wait_for(data_fixture):
    """
    A button may chain requests that are each allowed to wait as long as the
    default TTL. A lock that expires mid sequence lets a second click run the
    same actions concurrently, which is what it is there to stop.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    actions = []
    for _ in range(2):
        action = _http_action(data_fixture, button_field)
        service = action.service.specific
        service.timeout = 120
        service.save()
        actions.append(action)

    ttl = DatabaseWorkflowActionService()._lock_ttl_for(actions)

    assert ttl >= 240


@pytest.mark.django_db
def test_pointing_the_action_somewhere_else_forgets_the_old_answer(data_fixture):
    """
    The editor offers the actions after this one the paths it learned from the
    last click. Left in place after the URL changed, those paths describe an
    endpoint the button no longer calls, and an action using one writes an
    empty value into the row without saying anything.
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
    action.service.refresh_from_db()
    assert action.service.sample_data is not None

    action = CoreHTTPRequestWorkflowAction.objects.get(pk=action.pk)
    DatabaseWorkflowActionService().update_workflow_action(
        user, action, service={"url": {"formula": "'http://example.notexist/uuid'"}}
    )

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_changing_a_header_forgets_the_old_answer(data_fixture):
    """
    Not only the URL decides what comes back. A header, a query parameter, the
    method and the body all shape the answer, and a related row changing counts
    the same as the URL changing.
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
    action.service.refresh_from_db()
    assert action.service.sample_data is not None

    action = CoreHTTPRequestWorkflowAction.objects.get(pk=action.pk)
    DatabaseWorkflowActionService().update_workflow_action(
        user,
        action,
        service={
            "headers": [{"key": "Accept", "value": {"formula": "'text/csv'"}}],
        },
    )

    action.service.refresh_from_db()
    assert action.service.sample_data is None


@pytest.mark.django_db
def test_a_change_that_does_not_reshape_the_request_keeps_the_answer(data_fixture):
    """
    The timeout says how long the answer may take, not what it contains, so it
    does not cost the editor the schema it has.
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

    action = CoreHTTPRequestWorkflowAction.objects.get(pk=action.pk)
    DatabaseWorkflowActionService().update_workflow_action(
        user, action, service={"timeout": 45}
    )

    action.service.refresh_from_db()
    assert action.service.sample_data["data"]["body"] == {"title": "Sample Slide Show"}


@pytest.mark.django_db
def test_an_unchanged_answer_is_not_written_again(data_fixture):
    """
    Clicking is a manual path and the blob is big enough for Postgres to TOAST
    it, so rewriting the same answer on every click is a real write for
    nothing. The editor only reads it to build a schema.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(data_fixture, button_field)

    with mock_advocate_request({"title": "Sample Slide Show"}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

        with patch("baserow.core.services.models.Service.save", autospec=True) as saved:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert saved.call_count == 0

    # Nor when only the values change. Every response header comes back with
    # the answer, and `Date` alone moves every second, so comparing values
    # would rewrite the blob on nearly every click.
    with mock_advocate_request({"title": "Something else"}):
        with patch("baserow.core.services.models.Service.save", autospec=True) as again:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert again.call_count == 0

    # A differently shaped answer is written: that is the part the editor
    # describes to the actions after this one.
    with mock_advocate_request({"title": "Something else", "extra": 1}):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    service = CoreHTTPRequestWorkflowAction.objects.get(
        field=button_field
    ).service.specific
    assert service.sample_data["data"]["body"] == {
        "title": "Something else",
        "extra": 1,
    }


@pytest.mark.django_db
def test_a_failed_request_is_not_logged_with_the_address_it_used(data_fixture):
    """
    The clicker is told nothing about the address, but the log line was written
    before that and carried the failure itself. Loguru prints the frame locals
    beside it, so the URL's query string and the request headers went with it,
    which is exactly where an API key sits.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(
        data_fixture,
        button_field,
        url="'http://example.notexist/p?token=sk-SUPERSECRET'",
    )

    written = []
    sink_id = logger.add(written.append, level="DEBUG", diagnose=True, backtrace=True)
    try:
        with mock_advocate_request(
            raise_exception=request_exceptions.ConnectionError(
                "Failed to reach http://example.notexist/p?token=sk-SUPERSECRET"
            )
        ):
            with pytest.raises(WorkflowActionDispatchError):
                DatabaseWorkflowActionService().dispatch_workflow_actions(
                    user, button_field, row
                )
    finally:
        logger.remove(sink_id)

    logged = "".join(written)
    assert "sk-SUPERSECRET" not in logged
    assert "example.notexist" not in logged
    # It still says which action failed, which is what an operator needs.
    assert str(button_field.id) in logged


@pytest.mark.django_db
def test_a_transport_failure_of_no_known_kind_is_not_logged_either(data_fixture):
    """
    The service logs its own unknown failures, inside the frame that holds the
    URL, the resolved headers and the body, and that log line runs before the
    caller's protection can apply. A transport that fails with something other
    than a `RequestException` reaches it.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(
        data_fixture,
        button_field,
        url="'http://example.notexist/p?token=sk-SUPERSECRET'",
    )
    action.service.specific.headers.create(
        key="Authorization", value="'Bearer sk-HEADERSECRET'"
    )

    written = []
    sink_id = logger.add(written.append, level="DEBUG", diagnose=True, backtrace=True)
    try:
        with mock_advocate_request(raise_exception=OSError("socket gave up")):
            with pytest.raises(WorkflowActionDispatchError):
                DatabaseWorkflowActionService().dispatch_workflow_actions(
                    user, button_field, row
                )
    finally:
        logger.remove(sink_id)

    logged = "".join(written)
    assert "sk-SUPERSECRET" not in logged
    assert "sk-HEADERSECRET" not in logged
    assert "example.notexist" not in logged
    # It still says which action failed, which is what an operator needs.
    assert str(button_field.id) in logged


@pytest.mark.django_db
def test_an_answer_that_cannot_be_kept_is_not_logged_with_the_answer(data_fixture):
    """
    Keeping the shape can fail on what the endpoint answered with: a NUL byte
    encodes here and is then refused by the column it is written to. The frame
    holds the whole answer, response headers included, so the failure itself
    cannot be logged.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    written = []
    sink_id = logger.add(written.append, level="DEBUG", diagnose=True, backtrace=True)
    try:
        # The NUL is what the column refuses; the secret is what must
        # not be logged when it does.
        with mock_advocate_request({"secret": "sk-ANSWERSECRET", "nul": "a\u0000b"}):
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )
    finally:
        logger.remove(sink_id)

    # The click succeeded; only its shape was lost.
    action.service.refresh_from_db()
    assert action.service.sample_data is None

    logged = "".join(written)
    assert "sk-ANSWERSECRET" not in logged
    # The action is still named, so an operator can find what failed.
    assert str(action.id) in logged


@pytest.mark.django_db
def test_the_reason_the_last_click_left_is_replaced_by_the_next_one(data_fixture):
    """
    A shape is worth keeping, an explanation is not: a 404 followed by a
    timeout has to stop describing the 404 as the last click.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = _http_action(data_fixture, button_field)

    with mock_advocate_request({"error": "not found"}, status_code=404):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )
    action.service.refresh_from_db()
    assert "404" in action.service.sample_data["_error"]

    with mock_advocate_request(raise_exception=request_exceptions.Timeout()):
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    action.service.refresh_from_db()
    reason = action.service.sample_data["_error"]
    assert "timed out" in reason
    assert "404" not in reason


@pytest.mark.django_db
def test_a_refused_email_does_not_name_the_instance_mail_server(data_fixture, settings):
    """
    The service says which host refused it, and for an email action that host
    is this installation's own mail server. A clicker only needs to know which
    action could not be completed.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.internal.example"
    settings.EMAIL_PORT = 2525
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.use_instance_smtp_settings = True
    service.from_email = "'sender@example.com'"
    service.to_emails = "'someone@example.com'"
    service.subject = "'Hello'"
    service.body = "'Hi'"
    service.save()

    # Patched where the service really fails: `get_connection` only builds the
    # backend, and the refusal happens when the message is sent. Anywhere else
    # and the service's own message, which names the host, is never produced.
    with patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=ConnectionRefusedError(),
    ):
        with pytest.raises(WorkflowActionDispatchError) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert raised.value.message == EXTERNAL_DISPATCH_FAILED_MESSAGE
    # The message the service wrote, which the clicker must not be handed.
    assert "smtp.internal.example:2525" in str(raised.value.__cause__)


@pytest.mark.django_db
def test_a_mail_server_that_refuses_the_message_is_still_reported(
    data_fixture, settings
):
    """
    Only a failure that names the address is withheld. One about the server's
    own answer, such as a refused encryption, names nothing about this
    installation and is the only thing telling the clicker what happened.
    """

    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    settings.EMAIL_HOST = "smtp.internal.example"
    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    action = data_fixture.create_database_workflow_action(
        CoreSMTPEmailWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.use_instance_smtp_settings = True
    service.to_emails = "'someone@example.com'"
    service.subject = "'Hello'"
    service.body = "'Hi'"
    service.save()

    with patch(
        "django.core.mail.EmailMultiAlternatives.send",
        side_effect=SMTPNotSupportedError(),
    ):
        with pytest.raises(WorkflowActionDispatchError) as raised:
            DatabaseWorkflowActionService().dispatch_workflow_actions(
                user, button_field, row
            )

    assert raised.value.message == "TLS not supported by server"

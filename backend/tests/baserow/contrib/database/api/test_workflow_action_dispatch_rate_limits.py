from smtplib import SMTPAuthenticationError, SMTPNotSupportedError
from unittest.mock import Mock, patch

from django.urls import reverse

import pytest
from requests import exceptions as request_exceptions
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    SlackWriteMessageWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.integrations.slack.models import SlackBotIntegration
from baserow.core.exceptions import PermissionException
from baserow.throttling.types import RateLimit
from tests.baserow.contrib.database.workflow_actions.test_sample_data_capture import (
    mock_advocate_request,
)

ONE_PER_MINUTE = (RateLimit(period_in_seconds=60, number_of_calls=1),)


def _button(data_fixture, user):
    database = data_fixture.create_database_application(user=user)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    return table, button_field, row


def _add_http_action(data_fixture, button_field):
    action = data_fixture.create_database_workflow_action(
        CoreHTTPRequestWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.url = "'http://example.notexist/'"
    service.save()
    return action


def _add_row_action(data_fixture, button_field, table):
    action = data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = table
    service.save()
    name_field = table.field_set.get(name="Name")
    service.field_mappings.create(field=name_field, value="'Ada'", enabled=True)
    return action


def _add_email_action(data_fixture, user, button_field):
    """
    Created through the service so the type pins the instance server on it,
    the way a real editor does.
    """

    action = DatabaseWorkflowActionService().create_workflow_action(
        user,
        database_workflow_action_type_registry.get("smtp_email"),
        button_field,
    )
    service = action.service.specific
    service.to_emails = "'someone@example.com'"
    service.subject = "'Hello'"
    service.body = "'Hi'"
    service.save()
    return action


def _add_slack_action(data_fixture, button_field):
    bot = data_fixture.create_integration(
        SlackBotIntegration,
        application=button_field.table.database,
        name="Bot",
        token="xoxb-secret",
    )
    action = data_fixture.create_database_workflow_action(
        SlackWriteMessageWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.integration = bot
    service.channel = "general"
    service.text = "'hi'"
    service.save()
    return action


def _click(api_client, token, button_field, row):
    return api_client.post(
        reverse(
            "api:database:workflow_actions:dispatch",
            kwargs={"field_id": button_field.id},
        ),
        {"row_id": row.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_a_click_that_reaches_outside_spends_the_budget(
    api_client, data_fixture, settings
):
    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}):
        first = _click(api_client, token, button_field, row)
        second = _click(api_client, token, button_field, row)

    assert first.status_code == HTTP_200_OK
    assert second.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_a_click_that_stays_inside_spends_nothing(api_client, data_fixture, settings):
    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_row_action(data_fixture, button_field, table)

    for _ in range(3):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_the_workspace_budget_is_shared_between_its_members(
    api_client, data_fixture, settings
):
    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ()
    settings.DATABASE_BUTTON_DISPATCH_WORKSPACE_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    other_user, other_token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[user, other_user])
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    table = TableHandler().create_table_and_fields(
        user=user, database=database, name="People", fields=[("Name", "text", {})]
    )
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}):
        first = _click(api_client, token, button_field, row)
        second = _click(api_client, other_token, button_field, row)

    assert first.status_code == HTTP_200_OK
    # The second user never clicked before, so only the workspace's own budget
    # can be what stopped them.
    assert second.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_a_refused_click_does_not_charge_the_other_limit(
    api_client, data_fixture, settings
):
    """
    The user limit is reserved before the workspace limit is consulted. A click
    the workspace refuses must give that reservation back, or a busy workspace
    would eat its members' personal budgets too.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = (
        RateLimit(period_in_seconds=60, number_of_calls=2),
    )
    settings.DATABASE_BUTTON_DISPATCH_WORKSPACE_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}):
        first = _click(api_client, token, button_field, row)
        refused = _click(api_client, token, button_field, row)

    assert first.status_code == HTTP_200_OK
    assert refused.status_code == HTTP_429_TOO_MANY_REQUESTS

    # One call of the user's two was spent by the click that ran, and the
    # refused one gave its reservation back, so the workspace limit is the only
    # thing still standing in the way.
    settings.DATABASE_BUTTON_DISPATCH_WORKSPACE_RATE_LIMITS = ()
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_local_click_that_fails_spends_nothing(api_client, data_fixture, settings):
    """
    A budget is for reaching outside Baserow. A button that only touches rows
    here must not spend one when an action of it fails either, or a
    misconfigured local button would lock its clicker out of every button.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    action = _add_row_action(data_fixture, button_field, table)
    # A create row action with no table cannot run.
    service = action.service.specific
    service.table = None
    service.save()

    for _ in range(3):
        assert _click(api_client, token, button_field, row).status_code == (
            HTTP_400_BAD_REQUEST
        )

    _add_http_action(data_fixture, button_field)
    service.table = table
    service.save()

    # Nothing was spent above, so the one external click is still available.
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_failed_external_click_still_spends_its_budget(
    api_client, data_fixture, settings
):
    """
    Otherwise a button pointed at an endpoint that refuses every request could
    be clicked without limit, which is the traffic the budget exists to cap.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request(
        raise_exception=request_exceptions.ConnectionError("nope")
    ):
        failed = _click(api_client, token, button_field, row)
        second = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_400_BAD_REQUEST
    assert second.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_a_click_refused_by_the_lock_spends_nothing(api_client, data_fixture, settings):
    """
    A second click while the first is still running is refused before anything
    of it runs, so it reached nothing outside and owes nothing.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    from django.core.cache import cache

    held = cache.lock(
        f"button_dispatch_{button_field.id}_{row.id}",
        timeout=60,
    )
    assert held.acquire(blocking=False)
    try:
        refused = _click(api_client, token, button_field, row)
    finally:
        held.release()

    assert refused.status_code == HTTP_409_CONFLICT

    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_click_refused_by_permissions_spends_nothing(
    api_client, data_fixture, settings
):
    """
    Otherwise a member who may not dispatch could spend the whole workspace's
    budget on refusals, and lock out the members who may.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    def only_reading(self, checks, **kwargs):
        raise PermissionException()

    with patch(
        "baserow.core.handler.CoreHandler.check_multiple_permissions", only_reading
    ):
        refused = _click(api_client, token, button_field, row)

    assert refused.status_code == HTTP_401_UNAUTHORIZED

    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_every_request_on_a_button_spends_its_own_slot(
    api_client, data_fixture, settings
):
    """
    A slot per click would let one button carrying ten requests send ten for
    the price of one, so a `30/m` limit would really allow three hundred.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = (
        RateLimit(period_in_seconds=60, number_of_calls=2),
    )
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}):
        first = _click(api_client, token, button_field, row)
        second = _click(api_client, token, button_field, row)

    assert first.status_code == HTTP_200_OK
    # The two requests of the first click used the whole budget.
    assert second.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_a_button_carrying_more_requests_than_the_budget_is_refused(
    api_client, data_fixture, settings
):
    """
    Capping the reservation at what the limit holds would let the click send
    every one of its requests for the price of the limit, which is the burst
    the limit exists to stop. Such a button cannot be clicked inside the budget
    at all, so it is refused rather than undercharged, and the answer says
    waiting will not help.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}) as request:
        refused = _click(api_client, token, button_field, row)

    assert refused.status_code == HTTP_429_TOO_MANY_REQUESTS
    # Nothing was sent, so the burst never happened.
    assert request.call_count == 0
    assert "fewer" in refused.json()["detail"]

    # And the refusal spent nothing, so a button the budget can hold still
    # works for the same clicker.
    smaller = data_fixture.create_button_field(table=table, label="Go")
    _add_http_action(data_fixture, smaller)
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, smaller, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_an_address_refused_before_the_send_gives_the_slot_back(
    api_client, data_fixture, settings
):
    """
    Advocate rejects an address without sending anything, so no traffic left
    the instance. Charging for it would let one button pointed at a private
    address lock its clicker out of every other one.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request(
        raise_exception=UnacceptableAddressException("127.0.0.1")
    ) as request:
        refused = _click(api_client, token, button_field, row)

    assert refused.status_code == HTTP_400_BAD_REQUEST
    assert request.call_count == 1

    # Nothing was sent, so the one external click is still there.
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_request_that_was_never_built_is_not_charged(
    api_client, data_fixture, settings
):
    """
    The formulas are resolved inside the dispatch, so a body that is not valid
    JSON fails before anything is sent. Charging for it would let one
    misconfigured button lock its clicker out of every external button they
    have.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    action = _add_http_action(data_fixture, button_field)
    service = action.service.specific
    service.http_method = "POST"
    service.body_type = "json"
    service.body_content = "'not json{'"
    service.save()

    with mock_advocate_request({"ok": True}) as request:
        failed = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_400_BAD_REQUEST
    assert request.call_count == 0

    # Nothing left the instance, so the budget is untouched.
    service.body_type = "none"
    service.save()
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_click_that_stopped_before_its_request_gives_the_slot_back(
    api_client, data_fixture, settings
):
    """
    A local action failing first means no request left the instance, so there
    is nothing to charge for. Charging anyway would let one broken row action
    lock the clicker out of every button they have.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    broken = _add_row_action(data_fixture, button_field, table)
    service = broken.service.specific
    service.table = None
    service.save()
    _add_http_action(data_fixture, button_field)

    with mock_advocate_request({"ok": True}) as request:
        failed = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_400_BAD_REQUEST
    assert request.call_count == 0

    # Nothing was spent, so the one external click is still there.
    service.table = table
    service.save()
    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
def test_a_click_that_failed_after_its_request_still_spends_it(
    api_client, data_fixture, settings
):
    """
    The request already left the instance, so repeating the click repeats the
    traffic. Giving the slot back would make that traffic free.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_http_action(data_fixture, button_field)
    _add_row_action(data_fixture, button_field, table)

    with patch(
        "baserow.contrib.integrations.local_baserow.service_types."
        "LocalBaserowUpsertRowServiceType.dispatch_data",
        side_effect=PermissionException(),
    ):
        with mock_advocate_request({"ok": True}) as request:
            failed = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_401_UNAUTHORIZED
    assert request.call_count == 1

    with mock_advocate_request({"ok": True}):
        assert _click(api_client, token, button_field, row).status_code == (
            HTTP_429_TOO_MANY_REQUESTS
        )


@pytest.mark.django_db
def test_a_click_refused_by_a_deactivated_type_spends_nothing(
    api_client, data_fixture, settings
):
    """
    Nothing ran, so nothing reached outside. An instance that stopped being
    able to send must not also cost its members their budget on every click.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_email_action(data_fixture, user, button_field)

    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    refused = _click(api_client, token, button_field, row)
    assert refused.status_code == HTTP_403_FORBIDDEN
    assert refused.json()["error"] == "ERROR_WORKFLOW_ACTION_TYPE_DEACTIVATED"

    # The budget is intact, so the one external click it allows is still there.
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    with patch("django.core.mail.EmailMultiAlternatives.send", return_value=1):
        assert _click(api_client, token, button_field, row).status_code == HTTP_200_OK


@pytest.mark.django_db
@pytest.mark.parametrize(
    "refusal",
    [
        SMTPAuthenticationError(535, b"authentication failed"),
        SMTPNotSupportedError("STARTTLS extension not supported by server"),
    ],
)
def test_a_server_that_refused_after_answering_still_spends_the_slot(
    api_client, data_fixture, settings, refusal
):
    """
    A rejected login, or a server that will not start TLS, is a configuration
    problem the sender can fix, but the instance had already opened the
    connection and held a conversation with the server. Giving the slot back
    would make that traffic free to repeat.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    settings.INTEGRATION_ALLOW_SMTP_SERVICE_TO_USE_INSTANCE_SETTINGS = True
    settings.CELERY_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_email_action(data_fixture, user, button_field)

    with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=refusal):
        failed = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_400_BAD_REQUEST

    # The server was reached, so the click keeps what it spent.
    with patch("django.core.mail.EmailMultiAlternatives.send", return_value=1):
        assert _click(api_client, token, button_field, row).status_code == (
            HTTP_429_TOO_MANY_REQUESTS
        )


@pytest.mark.django_db
def test_a_click_slack_refused_after_answering_still_spends_it(
    api_client, data_fixture, settings
):
    """
    Slack answers `ok: false` only after the post has been made, so the
    traffic happened. Giving the slot back would let one row drive unbounded
    requests at Slack.
    """

    settings.DATABASE_BUTTON_DISPATCH_USER_RATE_LIMITS = ONE_PER_MINUTE
    user, token = data_fixture.create_user_and_token()
    table, button_field, row = _button(data_fixture, user)
    _add_slack_action(data_fixture, button_field)

    refusal = Mock()
    refusal.json.return_value = {"ok": False, "error": "not_in_channel"}
    posted = Mock(return_value=refusal)

    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=posted,
    ):
        failed = _click(api_client, token, button_field, row)

    assert failed.status_code == HTTP_400_BAD_REQUEST
    assert posted.call_count == 1

    # The budget is spent, so the next click is refused rather than repeating
    # the post.
    with patch(
        "baserow.contrib.integrations.slack.service_types.get_http_request_function",
        return_value=posted,
    ):
        again = _click(api_client, token, button_field, row)

    assert again.status_code == HTTP_429_TOO_MANY_REQUESTS
    assert posted.call_count == 1

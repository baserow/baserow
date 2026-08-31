from unittest.mock import patch

from django.urls import reverse

import pytest
from requests import exceptions as request_exceptions
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_409_CONFLICT,
    HTTP_429_TOO_MANY_REQUESTS,
)

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
)
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

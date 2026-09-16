from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction

import pytest

from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.contrib.integrations.core.service_types import CoreHTTPRequestServiceType
from baserow.core.services.exceptions import UnexpectedDispatchException
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext

from .test_sample_data_capture import (
    _http_action,
    _table_with_name,
    mock_advocate_request,
)


def _recording_transaction_state(request, seen):
    """
    Wraps the mocked outbound call so it notes whether a transaction was open
    at the moment the request would have left.
    """

    answer = request.side_effect

    def record(*args, **kwargs):
        seen.append(transaction.get_connection().in_atomic_block)
        return answer(*args, **kwargs)

    request.side_effect = record


# `transaction=True` throughout: the plain `db` fixture wraps every test in a
# transaction, so `in_atomic_block` would be true whatever the code did.


@pytest.mark.django_db(transaction=True)
def test_a_click_sends_its_request_with_no_transaction_open(data_fixture):
    """
    An HTTP request inside the dispatch savepoint held a connection and an open
    transaction for its whole network wait.
    """

    user = data_fixture.create_user()
    table, _ = _table_with_name(data_fixture, user)
    button_field = data_fixture.create_button_field(table=table, label="Go")
    row = table.get_model().objects.create()
    _http_action(data_fixture, button_field)

    seen = []
    with mock_advocate_request({"ok": True}) as request:
        _recording_transaction_state(request, seen)
        DatabaseWorkflowActionService().dispatch_workflow_actions(
            user, button_field, row
        )

    assert seen == [False]


@pytest.mark.django_db(transaction=True)
def test_a_service_that_stays_inside_still_runs_in_the_savepoint(data_fixture):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15
    )

    seen = []
    with mock_advocate_request({"ok": True}) as request:
        _recording_transaction_state(request, seen)
        with patch.object(CoreHTTPRequestServiceType, "is_external", False):
            service.get_type().dispatch(service, FakeDispatchContext())

    assert seen == [True]


@pytest.mark.django_db(transaction=True)
def test_inside_a_callers_transaction_the_request_keeps_its_savepoint(
    data_fixture,
):
    """
    Builder and automation dispatch inside their own transaction. Leaving the
    savepoint there gains nothing and would lose what it protects.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15
    )

    seen = []
    savepoints_open = []
    with transaction.atomic():
        with mock_advocate_request({"ok": True}) as request:
            answer = request.side_effect

            def record(*args, **kwargs):
                seen.append(transaction.get_connection().in_atomic_block)
                savepoints_open.append(len(connection.savepoint_ids))
                return answer(*args, **kwargs)

            request.side_effect = record
            service.get_type().dispatch(service, FakeDispatchContext())

    assert seen == [True]
    assert savepoints_open == [1]


@pytest.mark.django_db(transaction=True)
def test_a_database_error_in_an_outbound_dispatch_leaves_the_callers_transaction_usable(
    data_fixture,
):
    """
    The guarantee the savepoint was added for (#5621), for a service that
    reaches outside.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15
    )

    def broken(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM table_that_does_not_exist_xyz")

    with transaction.atomic():
        with patch(
            "baserow.contrib.integrations.core.service_types.send_http_request",
            side_effect=broken,
        ):
            with pytest.raises(UnexpectedDispatchException):
                service.get_type().dispatch(service, FakeDispatchContext())

        # Raises `TransactionManagementError` if the failed query was not
        # rolled back to a savepoint.
        get_user_model().objects.count()


def test_only_services_that_reach_outside_are_external():
    external = {
        service_type.type
        for service_type in service_type_registry.get_all()
        if service_type.is_external
    }

    assert external == {
        "http_request",
        "smtp_email",
        "slack_write_message",
        "ai_agent",
    }

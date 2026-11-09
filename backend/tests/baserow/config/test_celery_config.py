from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection, transaction

import pytest
from celery import signals

from baserow.config.celery import app, recover_from_open_db_transaction


@pytest.mark.django_db
def test_celery_task_time_limits_are_configured():
    """
    Verify that Celery task time limits are correctly configured.

    Using the wrong names (e.g. without 'TASK_') causes the settings to be
    silently ignored.
    """

    # Both values would be None if the settings were not configured correctly
    assert app.conf.task_soft_time_limit > 0
    assert app.conf.task_time_limit > app.conf.task_soft_time_limit


class FakeTask:
    name = "baserow.example.leaky_task"

    def __init__(self, is_eager=False):
        self.request = SimpleNamespace(
            is_eager=is_eager, delivery_info={"routing_key": "export"}
        )


def _send_task_postrun(task):
    signals.task_postrun.send(sender=task, task_id="task-1", task=task, state="SUCCESS")


def _leak_atomic_block():
    """
    Enter an atomic block and never exit it, like a task that loses track of its
    transaction.
    """

    transaction.atomic().__enter__()


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.telemetry.celery.task_open_transaction_counter")
@patch("sentry_sdk.capture_message")
def test_task_left_in_open_transaction_does_not_break_next_task(
    mock_capture_message, mock_counter, data_fixture
):
    _leak_atomic_block()
    data_fixture.create_user(email="uncommitted@example.com")

    _send_task_postrun(FakeTask())

    # The next task can use the database, and the leaked transaction was rolled
    # back instead of committed.
    assert not get_user_model().objects.filter(email="uncommitted@example.com").exists()
    assert not connection.in_atomic_block
    assert not connection.closed_in_transaction

    mock_capture_message.assert_called_once_with(
        "Celery task baserow.example.leaky_task finished with an open database "
        "transaction",
        level="error",
    )
    mock_counter.add.assert_called_once_with(
        1, {"task_name": "baserow.example.leaky_task", "queue": "export"}
    )


@pytest.fixture
def sentry_events():
    """
    Initialise Sentry with the Loguru integration, which production gets
    automatically, and collect the events instead of sending them.
    """

    import sentry_sdk
    from sentry_sdk.integrations.loguru import LoguruIntegration

    events = []

    def collect_event(event, hint):
        events.append(event)
        return None

    sentry_sdk.init(
        dsn="https://key@o0.ingest.sentry.io/0",
        default_integrations=False,
        integrations=[LoguruIntegration()],
        before_send=collect_event,
        # Dropped events are otherwise reported to the DSN when the client closes.
        send_client_reports=False,
    )
    try:
        yield events
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.get_global_scope().set_client(None)


@pytest.mark.django_db(transaction=True)
def test_task_left_in_open_transaction_sends_one_sentry_event(sentry_events):
    _leak_atomic_block()
    _leak_atomic_block()

    _send_task_postrun(FakeTask())

    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["level"] == "error"
    assert event["fingerprint"] == [
        "celery-task-open-database-transaction",
        "baserow.example.leaky_task",
    ]
    assert event["tags"] == {
        "task_name": "baserow.example.leaky_task",
        "queue": "export",
    }
    # The open atomic blocks are described before the connection is reset.
    assert event["contexts"]["open_database_transaction"]["transactions"] == {
        "default": {
            "autocommit": False,
            "atomic_block_depth": 2,
            "atomic_blocks": [
                {"savepoint": True, "durable": False},
                {"savepoint": True, "durable": False},
            ],
            "needs_rollback": False,
            "rollback_exception": None,
            "closed_in_transaction": False,
        }
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.telemetry.celery.task_open_transaction_counter")
@patch("sentry_sdk.capture_message")
def test_task_left_with_autocommit_off_is_reported(mock_capture_message, mock_counter):
    connection.set_autocommit(False)
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE uncommitted_table (id integer)")

    _send_task_postrun(FakeTask())

    assert "uncommitted_table" not in connection.introspection.table_names()
    assert connection.get_autocommit()
    mock_capture_message.assert_called_once()
    mock_counter.add.assert_called_once()


@pytest.mark.django_db(transaction=True)
@patch("sentry_sdk.capture_message")
def test_task_connection_closed_in_open_transaction_is_recovered(
    mock_capture_message,
):
    _leak_atomic_block()
    # Another receiver, such as Celery's Django fixup, may already have closed the
    # connection, leaving it flagged as closed in a transaction.
    connection.close()
    assert connection.closed_in_transaction

    _send_task_postrun(FakeTask())

    assert get_user_model().objects.count() == 0
    mock_capture_message.assert_called_once()


@pytest.mark.django_db(transaction=True)
@patch("sentry_sdk.capture_message")
def test_task_without_open_transaction_is_not_reported(mock_capture_message):
    with transaction.atomic():
        pass
    # A closed connection keeps the autocommit flag of its last session until it
    # reconnects, which doesn't mean a transaction is open.
    connection.set_autocommit(False)
    connection.close()

    recover_from_open_db_transaction(sender=FakeTask(is_eager=False))

    mock_capture_message.assert_not_called()


@pytest.mark.django_db
@patch("sentry_sdk.capture_message")
def test_eager_task_keeps_callers_transaction(mock_capture_message):
    # Eager tasks run inside the caller's transaction, like the test's own.
    assert connection.in_atomic_block

    recover_from_open_db_transaction(sender=FakeTask(is_eager=True))

    assert connection.in_atomic_block
    mock_capture_message.assert_not_called()

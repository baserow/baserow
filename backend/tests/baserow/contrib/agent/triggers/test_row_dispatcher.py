from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from django.db import connection
from django.test import TestCase

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentTrigger,
)
from baserow.contrib.agent.triggers.handler import AgentTriggerHandler
from baserow.contrib.agent.triggers.tasks import start_trigger_conversations
from baserow.contrib.agent.triggers.trash_types import AgentTriggerTrashableItemType
from baserow.contrib.agent.types import AgentMessageCreated
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
)
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun
from baserow.core.models import Agent as Identity
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.trash.handler import TrashHandler


@pytest.fixture(autouse=True)
def queued_runs_stay_queued(mocker) -> None:
    # Eager Celery would otherwise run each reply the triggers start.
    mocker.patch.object(ChatRunHandler, "_enqueue")


@pytest.fixture
def orders(data_fixture, configured_agent) -> SimpleNamespace:
    """A ready agent acting as a member identity, and an Orders table it reads."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    identity = Identity.objects.create(workspace=agent.workspace, name="Reader")
    AgentApplication.objects.filter(id=agent.id).update(
        run_as_subject_type="core.Agent", run_as_subject_id=identity.id
    )
    database = data_fixture.create_database_application(workspace=agent.workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    return SimpleNamespace(
        user=user, agent=agent, identity=identity, table=table, name=name
    )


def row_trigger(
    data_fixture, orders: SimpleNamespace, kind: str = "created", **kwargs
) -> AgentTrigger:
    """A trigger on the Orders table whose message is its batch's row count."""

    create_service = getattr(data_fixture, f"create_local_baserow_rows_{kind}_service")
    kwargs.setdefault("message", "get('trigger.count')")
    return data_fixture.create_agent_trigger(
        agent=orders.agent,
        service=create_service(table=orders.table, integration=None),
        **kwargs,
    )


def create_orders(orders: SimpleNamespace, count: int) -> None:
    """Create the rows in one request and run what their event queues."""

    rows = [{orders.name.db_column: f"Order {index}"} for index in range(count)]
    with TestCase.captureOnCommitCallbacks(execute=True):
        RowHandler().force_create_rows(orders.user, orders.table, rows)


def opening_messages() -> list[str]:
    return list(
        AgentMessage.objects.filter(role="trigger")
        .order_by("id")
        .values_list("content", flat=True)
    )


def reply_statuses() -> list[str]:
    return list(
        AgentMessage.objects.filter(role="assistant")
        .order_by("id")
        .values_list("status", flat=True)
    )


@pytest.mark.django_db
def test_a_waiting_trigger_starts_one_conversation_per_batch_in_order(
    data_fixture, orders
):
    trigger = row_trigger(data_fixture, orders, on_overlap="wait")

    create_orders(orders, 45)

    trigger.refresh_from_db()
    assert opening_messages() == ["20", "20", "5"]
    assert reply_statuses() == ["running", "queued", "queued"]
    assert ChatRun.objects.count() == 1
    assert trigger.last_fired_on is not None
    assert trigger.last_skipped_reason == ""


@pytest.mark.django_db
def test_a_skipping_trigger_starts_the_first_batch_and_shows_the_others_skipped(
    data_fixture, orders
):
    trigger = row_trigger(data_fixture, orders, on_overlap="skip")

    with freeze_time("2026-11-11 10:00:00", auto_tick_seconds=1):
        create_orders(orders, 45)

    trigger.refresh_from_db()
    assert opening_messages() == ["20"]
    assert trigger.last_skipped_reason == "previous_running"
    assert trigger.last_skipped_on > trigger.last_fired_on


@pytest.mark.django_db
def test_an_event_starts_at_most_the_capped_batches_and_shows_the_rest_was_left_out(
    data_fixture, orders, settings
):
    settings.AGENT_TRIGGER_MAX_BATCHES_PER_EVENT = 2
    trigger = row_trigger(data_fixture, orders, on_overlap="wait", batch_size=1)

    create_orders(orders, 5)

    trigger.refresh_from_db()
    assert opening_messages() == ["1", "1"]
    assert trigger.last_skipped_reason == "event_too_large"
    assert trigger.last_skipped_on >= trigger.last_fired_on


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stored,rows,batches", [(0, 2, ["1", "1"]), (101, 101, ["100", "1"])]
)
def test_a_stored_batch_size_out_of_bounds_reads_as_the_nearest_bound(
    data_fixture, orders, stored, rows, batches
):
    row_trigger(data_fixture, orders, on_overlap="wait", batch_size=stored)

    create_orders(orders, rows)

    assert opening_messages() == batches


@pytest.mark.django_db
def test_each_batch_counts_towards_the_rate_limits(data_fixture, orders, settings):
    settings.AGENT_TRIGGER_RATE_LIMITS = ((2, 60),)
    trigger = row_trigger(data_fixture, orders, on_overlap="wait", batch_size=1)

    create_orders(orders, 5)

    trigger.refresh_from_db()
    assert opening_messages() == ["1", "1"]
    assert trigger.last_skipped_reason == "rate_limited"


@pytest.mark.django_db
def test_a_failing_batch_is_rolled_back_and_logged_while_the_next_ones_apply(
    data_fixture, orders, mocker, logs
):
    trigger = row_trigger(data_fixture, orders, on_overlap="wait", batch_size=1)
    original = AgentHandler.start_trigger_conversation
    started = []

    def fail_the_second(
        handler: AgentHandler, *args: Any, **kwargs: Any
    ) -> AgentMessageCreated:
        started.append(original(handler, *args, **kwargs))
        if len(started) == 2:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM agent_trigger_missing_table")
        return started[-1]

    mocker.patch.object(AgentHandler, "start_trigger_conversation", fail_the_second)
    mocker.patch("baserow.contrib.agent.triggers.dispatcher.exception_capturer")

    create_orders(orders, 3)

    assert opening_messages() == ["1", "1"]
    assert reply_statuses() == ["running", "queued"]
    assert [log.record["message"] for log in logs] == [
        f"Could not start agent trigger {trigger.id}."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("lost", ["removed", "trashed", "revoked"])
def test_a_trigger_whose_run_identity_cannot_read_the_table_starts_nothing(
    data_fixture, orders, mocker, lost
):
    trigger = row_trigger(data_fixture, orders)
    if lost == "removed":
        AgentApplication.objects.filter(id=orders.agent.id).update(
            run_as_subject_type=None, run_as_subject_id=None
        )
    elif lost == "trashed":
        Identity.objects.filter(id=orders.identity.id).update(trashed=True)
    else:
        mocker.patch.object(
            LocalBaserowRowsCreatedTriggerServiceType,
            "can_subject_read",
            return_value=False,
        )

    create_orders(orders, 3)

    trigger.refresh_from_db()
    assert not AgentConversation.objects.exists()
    assert (trigger.last_skipped_reason, trigger.last_fired_on) == ("no_access", None)


@pytest.mark.django_db
def test_rows_of_a_table_the_identity_cannot_read_never_start_after_a_table_switch(
    data_fixture, orders, mocker
):
    trigger = row_trigger(data_fixture, orders)
    readable = data_fixture.create_database_table(database=orders.table.database)
    mocker.patch.object(
        LocalBaserowRowsCreatedTriggerServiceType,
        "can_subject_read",
        side_effect=lambda service, *args: service.table_id == readable.id,
    )

    queued = mocker.patch(
        "baserow.contrib.agent.triggers.dispatcher.start_trigger_conversations.delay"
    )

    create_orders(orders, 1)
    trigger.service.specific_class.objects.filter(id=trigger.service_id).update(
        table=readable
    )
    start_trigger_conversations(*queued.call_args.args)

    trigger.refresh_from_db()
    assert not AgentConversation.objects.exists()
    assert trigger.last_skipped_reason == "no_access"


@pytest.mark.django_db
def test_a_trigger_restored_without_access_is_skipped_when_it_fires(
    data_fixture, orders, mocker
):
    trigger = row_trigger(data_fixture, orders)
    AgentTriggerHandler().delete_trigger(orders.user, trigger)
    mocker.patch.object(
        LocalBaserowRowsCreatedTriggerServiceType,
        "can_subject_read",
        return_value=False,
    )

    TrashHandler.restore_item(
        orders.user, AgentTriggerTrashableItemType.type, trigger.id
    )
    create_orders(orders, 3)

    trigger.refresh_from_db()
    assert not AgentConversation.objects.exists()
    assert trigger.last_skipped_reason == "no_access"


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["created", "updated", "deleted"])
@pytest.mark.parametrize(
    "by_identity,conversations", [(True, 0), (False, 1)], ids=["identity", "user"]
)
def test_rows_the_agent_itself_changes_start_nothing(
    data_fixture, orders, kind, by_identity, conversations
):
    row_trigger(data_fixture, orders, kind=kind)
    row = orders.table.get_model().objects.create(**{orders.name.db_column: "Before"})
    subject = orders.identity if by_identity else orders.user
    handler, column = RowHandler(), orders.name.db_column
    changes = {
        "created": lambda: handler.force_create_rows(
            subject, orders.table, [{column: "New"}]
        ),
        "updated": lambda: handler.update_rows(
            subject, orders.table, [{"id": row.id, column: "After"}]
        ),
        "deleted": lambda: handler.delete_rows(subject, orders.table, [row.id]),
    }

    with TestCase.captureOnCommitCallbacks(execute=True):
        changes[kind]()

    assert AgentConversation.objects.count() == conversations


@pytest.mark.django_db
@pytest.mark.parametrize("way", ["batch", "single", "for_good"])
def test_deleted_rows_reach_the_message_with_their_values(data_fixture, orders, way):
    people = data_fixture.create_database_table(
        database=orders.table.database, name="People"
    )
    person = data_fixture.create_text_field(table=people, name="Name", primary=True)
    friends = data_fixture.create_link_row_field(
        table=orders.table, link_row_table=people, name="Friends"
    )
    handler = RowHandler()
    [paula] = handler.force_create_rows(
        orders.user, people, [{person.db_column: "Paula"}]
    ).created_rows
    [row] = handler.force_create_rows(
        orders.user,
        orders.table,
        [{orders.name.db_column: "Horse", friends.db_column: [paula.id]}],
    ).created_rows
    row_trigger(data_fixture, orders, kind="deleted", message="get('trigger.rows')")
    deletes = {
        "batch": lambda: handler.delete_rows(orders.user, orders.table, [row.id]),
        "single": lambda: handler.delete_row(orders.user, orders.table, row),
        "for_good": lambda: handler.delete_rows(
            orders.user, orders.table, [row.id], permanently_delete=True
        ),
    }

    with TestCase.captureOnCommitCallbacks(execute=True):
        deletes[way]()

    [message] = opening_messages()
    assert '"Name": "Horse"' in message
    assert "Paula" in message


@pytest.mark.django_db
def test_other_listeners_still_receive_every_row_of_the_event_at_once(
    data_fixture, orders
):
    row_trigger(data_fixture, orders, on_overlap="wait")
    service_type = service_type_registry.get(
        LocalBaserowRowsCreatedTriggerServiceType.type
    )
    received = []

    def other_listener(
        services: list[Service],
        event_payload: Callable[[Service], dict[str, Any]],
        **kwargs: Any,
    ) -> None:
        received.extend(len(event_payload(service)["results"]) for service in services)

    service_type.start_listening(other_listener)
    try:
        create_orders(orders, 45)
    finally:
        service_type.stop_listening(other_listener)

    assert received == [45]
    assert opening_messages() == ["20", "20", "5"]

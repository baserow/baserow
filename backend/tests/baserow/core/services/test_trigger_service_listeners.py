from contextlib import contextmanager
from unittest.mock import Mock

from django.db import transaction

import pytest
from freezegun import freeze_time

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.integrations.core.service_types import CorePeriodicServiceType
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedServiceType,
)
from baserow.core.services.registries import (
    TriggerServiceTypeMixin,
    service_type_registry,
)


class FakeTriggerServiceType(TriggerServiceTypeMixin):
    pass


@contextmanager
def extra_listeners(service_type, *callbacks):
    """
    Temporarily registers extra listeners on a registry singleton, restoring
    any instance-level `on_event` shadow other tests may have left behind.
    """

    shadow = service_type.__dict__.pop("on_event", None)
    for callback in callbacks:
        service_type.start_listening(callback)
    try:
        yield
    finally:
        for callback in callbacks:
            service_type.stop_listening(callback)
        if shadow is not None:
            service_type.on_event = shadow


def test_trigger_service_type_notifies_all_listeners():
    service_type = FakeTriggerServiceType()
    first, second = Mock(), Mock()
    service_type.start_listening(first)
    service_type.start_listening(second)

    services = [Mock()]
    payload = {"key": "value"}
    service_type.on_event(services, payload, user="user")

    first.assert_called_once_with(services, payload, user="user")
    second.assert_called_once_with(services, payload, user="user")


def test_trigger_service_type_deduplicates_listeners():
    service_type = FakeTriggerServiceType()
    listener = Mock()
    service_type.start_listening(listener)
    service_type.start_listening(listener)

    service_type.on_event([], None)

    listener.assert_called_once()


def test_trigger_service_type_deduplicates_bound_methods():
    class Consumer:
        def on_event(self, services, event_payload=None, user=None):
            pass

    consumer = Consumer()
    service_type = FakeTriggerServiceType()
    service_type.start_listening(consumer.on_event)
    service_type.start_listening(consumer.on_event)

    assert len(service_type.listeners) == 1


def test_trigger_service_type_stop_listening_removes_single_listener():
    service_type = FakeTriggerServiceType()
    first, second = Mock(), Mock()
    service_type.start_listening(first)
    service_type.start_listening(second)

    service_type.stop_listening(first)
    service_type.on_event([], None)

    first.assert_not_called()
    second.assert_called_once()


def test_trigger_service_type_stop_listening_without_argument_clears_all():
    service_type = FakeTriggerServiceType()
    service_type.start_listening(Mock())
    service_type.start_listening(Mock())

    service_type.stop_listening()

    assert service_type.listeners == []
    service_type.on_event([], None)  # No listeners, should be a no-op.


def test_trigger_service_type_listeners_are_not_shared_between_instances():
    first_instance = FakeTriggerServiceType()
    second_instance = FakeTriggerServiceType()
    first_instance.start_listening(Mock())

    assert second_instance.listeners == []


@pytest.mark.django_db(transaction=True)
def test_rows_created_signal_notifies_multiple_listeners(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user, table=table)
    data_fixture.create_local_baserow_rows_created_service(table=table)

    service_type = service_type_registry.get(LocalBaserowRowsCreatedServiceType.type)
    first, second = Mock(), Mock()

    with extra_listeners(service_type, first, second):
        RowHandler().create_rows(
            user=user,
            table=table,
            model=table.get_model(),
            rows_values=[{f"field_{field.id}": "Value"}],
            skip_search_update=True,
        )

    first.assert_called_once()
    second.assert_called_once()
    assert [s.id for s in first.call_args.args[0]] == [
        s.id for s in second.call_args.args[0]
    ]


@pytest.mark.django_db(transaction=True)
def test_periodic_service_payload_advances_run_dates_once_for_multiple_listeners(
    data_fixture,
):
    frozen_time = "2026-01-01T10:00:00"
    with freeze_time(frozen_time):
        service = data_fixture.create_core_periodic_service(interval="MINUTE")

    service_type = service_type_registry.get(CorePeriodicServiceType.type)
    payloads = []

    def make_listener():
        def listener(services, event_payload=None, user=None):
            for due_service in services:
                payloads.append(event_payload(due_service))

        return listener

    with extra_listeners(service_type, make_listener(), make_listener()):
        with freeze_time("2026-01-01T10:05:00"):
            with transaction.atomic():
                service_type.call_periodic_services_that_are_due()

    # Both listeners received a payload for the same service, but the run
    # dates must only have been advanced once.
    assert len(payloads) == 2
    assert payloads[0] == payloads[1]

    service.refresh_from_db()
    assert service.next_run_at.isoformat() == payloads[0]["next_run_at"]

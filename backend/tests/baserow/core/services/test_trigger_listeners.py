from typing import Any, Callable, Iterable
from unittest.mock import Mock, patch

from django.dispatch import Signal

import pytest

from baserow.contrib.automation.nodes.node_types import CorePeriodicTriggerNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
)
from baserow.core.services.models import Service
from baserow.core.services.registries import (
    ServiceType,
    ServiceTypeRegistry,
    TriggerServiceTypeMixin,
    service_type_registry,
)


class FakeTriggerServiceType(TriggerServiceTypeMixin):
    def __init__(self) -> None:
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1

    def disconnect(self) -> None:
        self.disconnect_calls += 1


def test_start_listening_connects_on_first_and_stop_listening_disconnects_on_last():
    service_type = FakeTriggerServiceType()
    first, second = Mock(), Mock()

    service_type.start_listening(first)
    service_type.start_listening(second)
    service_type.start_listening(first)

    assert service_type.listeners == [first, second]
    assert service_type.connect_calls == 1

    service_type.stop_listening(first)
    service_type.stop_listening(Mock())

    assert service_type.listeners == [second]
    assert service_type.disconnect_calls == 0

    service_type.stop_listening(second)
    service_type.start_listening(first)

    assert service_type.listeners == [first]
    assert service_type.disconnect_calls == 1
    assert service_type.connect_calls == 2


def test_on_event_materializes_services_once_and_concatenates_listener_results():
    service_type = FakeTriggerServiceType()
    services = [object(), object()]
    payload = {"triggered_at": "2026-11-09T10:00:00+00:00"}
    user = object()
    calls = []

    def listener_returning(result):
        def listener(services, event_payload, user, isolate_failures):
            calls.append((services, event_payload, user, isolate_failures))
            return result

        return listener

    service_type.start_listening(listener_returning(["first"]))
    service_type.start_listening(listener_returning(None))
    service_type.start_listening(listener_returning(["second", "third"]))

    result = service_type.on_event(
        iter(services), payload, user=user, isolate_failures=True
    )

    assert result == ["first", "second", "third"]
    assert calls == [(services, payload, user, True)] * 3


def test_listeners_are_per_instance_and_on_event_without_listeners_returns_nothing():
    first, second = FakeTriggerServiceType(), FakeTriggerServiceType()

    first.start_listening(Mock())

    assert second.listeners == []
    assert second.on_event([object()], {"method": "GET"}) == []


@patch("baserow.contrib.integrations.core.service_types.celery_app")
def test_periodic_connect_and_disconnect_manage_the_beat_task(mock_celery_app):
    service_type = CorePeriodicTriggerServiceType()
    listener = Mock(return_value=[])

    service_type.start_listening(listener)
    service_type.stop_listening(listener)

    mock_celery_app.on_after_finalize.connect.assert_called_once_with(
        service_type._setup_periodic_task
    )
    mock_celery_app.on_after_finalize.disconnect.assert_called_once_with(
        service_type._setup_periodic_task
    )

    sender = Mock()
    service_type.start_listening(listener)
    service_type._setup_periodic_task(sender)
    service_type.stop_listening(listener)
    service_type.start_listening(listener)
    service_type.stop_listening(listener)

    sender.control.revoke.assert_called_once_with(
        "periodic-service-type-task", terminate=True
    )


def test_rows_signal_connect_and_disconnect_toggle_the_signal_receiver():
    signal = Signal()
    listener = Mock(return_value=[])

    with patch.object(LocalBaserowRowsCreatedTriggerServiceType, "signal", signal):
        service_type = LocalBaserowRowsCreatedTriggerServiceType()

        service_type.start_listening(listener)
        assert signal.has_listeners()

        service_type.stop_listening(listener)
        assert not signal.has_listeners()


def test_unregistering_a_trigger_node_type_removes_only_its_own_listener():
    service_type = service_type_registry.get(CorePeriodicTriggerServiceType.type)
    node_type = automation_node_type_registry.get(CorePeriodicTriggerNodeType.type)
    other_listener = Mock(return_value=[])
    before = list(service_type.listeners)
    assert node_type.on_event in before

    service_type.start_listening(other_listener)
    try:
        node_type.before_unregister()

        assert node_type.on_event not in service_type.listeners
        assert other_listener in service_type.listeners
    finally:
        node_type.after_register()
        service_type.stop_listening(other_listener)

    assert set(service_type.listeners) == set(before)


class RegistryFakeTriggerServiceType(TriggerServiceTypeMixin, ServiceType):
    type = "registry_fake_trigger"
    model_class = Service

    def __init__(self) -> None:
        super().__init__()
        self.connect_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1


def recording_listener(received: list) -> Callable:
    """
    Builds a registry listener with the `start_listening` call shape that appends
    `(services, event_payload)` to `received` and reports no histories.

    :param received: The list the listener appends to.
    :return: The listener.
    """

    def listener(
        services: Iterable[Service],
        event_payload: Any = None,
        user: Any = None,
        isolate_failures: bool = False,
    ) -> list:
        received.append((list(services), event_payload))
        return []

    return listener


@pytest.fixture
def registry_trigger_listeners(
    mutable_service_type_registry: ServiceTypeRegistry,
) -> Iterable[ServiceTypeRegistry]:
    """
    Yields the service type registry with every pre-existing registry listener
    detached (the agent dispatcher on the stacked branch), so a test only fans
    out to its own listeners, then removes the test's listeners and restores the
    detached ones so nothing leaks into the process-wide trigger types.

    :param mutable_service_type_registry: The registry fixture that restores
        the registered types afterwards.
    :return: The registry to add listeners to.
    """

    registry = mutable_service_type_registry
    before = list(registry.trigger_listeners)
    for listener in before:
        registry.remove_trigger_listener(listener)
    yield registry
    for listener in list(registry.trigger_listeners):
        registry.remove_trigger_listener(listener)
    for listener in before:
        registry.add_trigger_listener(listener)


def registered_trigger_types(
    registry: ServiceTypeRegistry,
) -> list[TriggerServiceTypeMixin]:
    """
    :param registry: The service type registry to read.
    :return: The registered types that respond to events.
    """

    return [
        service_type
        for service_type in registry.get_all()
        if isinstance(service_type, TriggerServiceTypeMixin)
    ]


def test_registry_add_trigger_listener_subscribes_every_trigger_type(
    registry_trigger_listeners,
):
    registry = registry_trigger_listeners
    listener = recording_listener([])

    registry.add_trigger_listener(listener)
    registry.add_trigger_listener(listener)

    trigger_types = registered_trigger_types(registry)
    assert trigger_types
    assert all(
        service_type.listeners.count(listener) == 1 for service_type in trigger_types
    )
    assert registry.trigger_listeners.count(listener) == 1


def test_registry_after_register_subscribes_a_trigger_type_registered_later(
    registry_trigger_listeners,
):
    registry = registry_trigger_listeners
    listener = recording_listener([])
    registry.add_trigger_listener(listener)

    service_type = RegistryFakeTriggerServiceType()
    registry.register(service_type)

    assert service_type.listeners == [listener]
    assert service_type.connect_calls == 1


def test_registry_listener_receives_the_events_of_a_trigger_type(
    registry_trigger_listeners,
):
    registry = registry_trigger_listeners
    received = []
    registry.add_trigger_listener(recording_listener(received))
    service_type = RegistryFakeTriggerServiceType()
    registry.register(service_type)
    service = Mock(spec=Service)

    histories = service_type.on_event([service], event_payload={"a": 1})

    assert received == [([service], {"a": 1})]
    assert histories == []


def test_registry_remove_trigger_listener_unsubscribes_now_and_later(
    registry_trigger_listeners,
):
    registry = registry_trigger_listeners
    listener = recording_listener([])
    registry.add_trigger_listener(listener)

    registry.remove_trigger_listener(listener)
    registry.remove_trigger_listener(listener)
    service_type = RegistryFakeTriggerServiceType()
    registry.register(service_type)

    assert listener not in registry.trigger_listeners
    assert all(
        listener not in service_type.listeners
        for service_type in registered_trigger_types(registry)
    )
    assert service_type.listeners == []

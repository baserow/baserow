from unittest.mock import Mock, patch

from django.dispatch import Signal

from baserow.contrib.automation.nodes.node_types import CorePeriodicTriggerNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
)
from baserow.core.services.registries import (
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

    def listener(result):
        def on_event(services, event_payload, user, isolate_failures):
            calls.append((services, event_payload, user, isolate_failures))
            return result

        return on_event

    service_type.start_listening(listener(["first"]))
    service_type.start_listening(listener(None))
    service_type.start_listening(listener(["second", "third"]))

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

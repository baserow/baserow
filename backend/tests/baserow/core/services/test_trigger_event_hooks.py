import pytest

from baserow.contrib.integrations.core.service_types import (
    CoreHTTPTriggerServiceType,
    CoreInboundEmailTriggerServiceType,
    CoreManualTriggerServiceType,
    CorePeriodicTriggerServiceType,
)
from baserow.core.services.registries import service_type_registry


@pytest.mark.django_db
def test_a_trigger_type_sends_whole_events_anyone_may_read_by_default(data_fixture):
    service = data_fixture.create_core_periodic_service()
    workspace = data_fixture.create_workspace()
    service_type = service_type_registry.get(CorePeriodicTriggerServiceType.type)
    payload = {"triggered_at": "2026-11-11T09:00:00+00:00", "next_run_at": None}

    assert service_type.can_subject_read(service, None, workspace) is True
    assert service_type.get_form_choices(None, workspace) is None
    assert service_type.split_event_payload(service, payload, 1) == [payload]
    assert service_type.get_event_context(service, payload) == {}


@pytest.mark.parametrize(
    "service_type_class",
    [
        CoreHTTPTriggerServiceType,
        CoreInboundEmailTriggerServiceType,
        CoreManualTriggerServiceType,
        CorePeriodicTriggerServiceType,
    ],
)
def test_trigger_events_can_be_skipped_by_default(service_type_class):
    service_type = service_type_registry.get(service_type_class.type)

    assert service_type.events_can_be_skipped is True

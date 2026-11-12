from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.triggers.exceptions import AgentTriggerDoesNotExist
from baserow.contrib.agent.triggers.handler import AgentTriggerHandler
from baserow.contrib.agent.triggers.trash_types import AgentTriggerTrashableItemType
from baserow.contrib.integrations.core.constants import (
    PERIODIC_INTERVAL_DAY,
)
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.core.models import TrashEntry
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.trash.handler import TrashHandler


def daily_trigger(data_fixture, **kwargs) -> AgentTrigger:
    service = data_fixture.create_core_periodic_service(
        interval=PERIODIC_INTERVAL_DAY, hour=9
    )
    return data_fixture.create_agent_trigger(service=service, **kwargs)


@pytest.mark.django_db
def test_create_trigger_creates_an_armed_service(data_fixture):
    agent = data_fixture.create_agent_application()

    with freeze_time("2026-01-01 08:00"):
        trigger = AgentTriggerHandler().create_trigger(
            agent,
            service_type_registry.get("periodic"),
            {"interval": PERIODIC_INTERVAL_DAY, "hour": 9, "minute": 0},
            message="'Daily digest'",
        )

    service = CorePeriodicService.objects.get(id=trigger.service_id)
    assert (trigger.agent, trigger.enabled) == (agent, True)
    assert trigger.message["formula"] == "'Daily digest'"
    assert (service.interval, service.hour) == (PERIODIC_INTERVAL_DAY, 9)
    assert service.next_run_at == datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    assert AgentTriggerHandler().list_triggers(agent).get() == trigger


@pytest.mark.django_db
def test_update_trigger_reschedules_only_when_its_schedule_changes_or_it_switches_on(
    data_fixture,
):
    trigger = daily_trigger(data_fixture, enabled=False)
    handler = AgentTriggerHandler()
    moved_on = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
    at_eleven = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)

    def next_run_at() -> datetime:
        return CorePeriodicService.objects.get(id=trigger.service_id).next_run_at

    def move_next_run() -> None:
        CorePeriodicService.objects.filter(id=trigger.service_id).update(
            next_run_at=moved_on
        )

    with freeze_time("2026-01-01 10:00"):
        move_next_run()
        handler.update_trigger(trigger, message="'Changed'")
        handler.update_trigger(trigger, enabled=False)
        handler.update_trigger(
            trigger,
            prepared_service_values={"interval": PERIODIC_INTERVAL_DAY, "hour": 9},
        )
        assert next_run_at() == moved_on

        handler.update_trigger(
            trigger,
            prepared_service_values={"interval": PERIODIC_INTERVAL_DAY, "hour": 11},
        )
        assert next_run_at() == at_eleven

        move_next_run()
        handler.update_trigger(trigger, enabled=True)
        assert next_run_at() == at_eleven

    trigger.refresh_from_db()
    assert (trigger.enabled, trigger.message["formula"]) == (True, "'Changed'")


@pytest.mark.django_db
def test_trashing_a_trigger_hides_its_service_until_it_is_restored(
    data_fixture, mocker
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    trigger = daily_trigger(data_fixture, agent=agent)
    arm = mocker.patch.object(CorePeriodicTriggerServiceType, "arm")

    AgentTriggerHandler().delete_trigger(user, trigger)

    entry = TrashEntry.objects.get()
    assert (entry.trash_item_type, entry.application_id, entry.name) == (
        AgentTriggerTrashableItemType.type,
        agent.id,
        "periodic",
    )
    assert AgentTrigger.trash.filter(id=trigger.id).exists()
    assert not CorePeriodicService.objects.filter(id=trigger.service_id).exists()
    assert Service.trash.filter(id=trigger.service_id).exists()
    with pytest.raises(AgentTriggerDoesNotExist):
        AgentTriggerHandler().get_trigger(trigger.id)

    TrashHandler.restore_item(user, AgentTriggerTrashableItemType.type, trigger.id)

    assert AgentTriggerHandler().get_trigger(trigger.id).service.trashed is False
    assert CorePeriodicService.objects.filter(id=trigger.service_id).exists()
    arm.assert_called_once()


@pytest.mark.django_db
def test_deleting_a_trigger_or_its_agent_deletes_the_service(data_fixture):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    trashed, kept = [daily_trigger(data_fixture, agent=agent) for _ in range(2)]
    AgentTriggerHandler().delete_trigger(user, trashed)

    TrashHandler.permanently_delete(trashed)
    agent.delete()

    assert not AgentTrigger.objects_and_trash.exists()
    assert not Service.objects_and_trash.filter(
        id__in=[trashed.service_id, kept.service_id]
    ).exists()

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.utils import timezone

import pytest
from freezegun import freeze_time

from baserow.contrib.agent.models import AgentApplication, AgentTrigger
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.triggers.actions import (
    CreateAgentTriggerActionType,
    DeleteAgentTriggerActionType,
    UpdateAgentTriggerActionType,
)
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.integrations.core.models import (
    CorePeriodicService,
)
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry
from baserow.core.operations import UpdateApplicationOperationType

from ..utils import agent_url

MESSAGE = {"formula": "'Daily digest'", "mode": "simple", "version": "0.1"}


@pytest.fixture
def periodic_trigger(data_fixture):
    def create(agent: AgentApplication, **service_values: Any) -> AgentTrigger:
        service = data_fixture.create_core_periodic_service(**service_values)
        return data_fixture.create_agent_trigger(
            agent=agent, service=service, message=MESSAGE
        )

    return create


@pytest.mark.django_db
def test_configuration_lists_the_available_trigger_types(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    url = agent_url(agent, "configuration")

    assert api_client.get(url).json()["available_trigger_types"] == ["periodic"]

    mocker.patch(
        "baserow.contrib.agent.triggers.handler.AGENT_TRIGGER_TYPES_ENABLED",
        ("periodic", "http_trigger"),
    )
    assert set(api_client.get(url).json()["available_trigger_types"]) == {
        "periodic",
        "http_trigger",
    }

    mocker.patch.object(
        CorePeriodicTriggerServiceType, "is_deactivated", return_value=True
    )
    assert api_client.get(url).json()["available_trigger_types"] == ["http_trigger"]


def call(
    name: str, user: AbstractUser, agent: AgentApplication, trigger: AgentTrigger
) -> Any:
    service = AgentTriggerService()
    calls = {
        "list": lambda: service.list_triggers(user, agent.id),
        "get": lambda: service.get_trigger(user, agent.id, trigger.id),
        "create": lambda: service.create_trigger(user, agent.id, "periodic"),
        "update": lambda: service.update_trigger(
            user, agent.id, trigger.id, enabled=False
        ),
        "delete": lambda: service.delete_trigger(user, agent.id, trigger.id),
    }
    return calls[name]()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,operations",
    [
        ("list", [ReadAgentConfigurationOperationType]),
        ("get", [ReadAgentConfigurationOperationType]),
        (
            "create",
            [UpdateApplicationOperationType, ReadAgentConfigurationOperationType],
        ),
        (
            "update",
            [UpdateApplicationOperationType, ReadAgentConfigurationOperationType],
        ),
        (
            "delete",
            [UpdateApplicationOperationType, ReadAgentConfigurationOperationType],
        ),
    ],
)
def test_each_trigger_call_checks_its_operations_on_the_agent(
    data_fixture, periodic_trigger, mocker, name, operations
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    trigger = periodic_trigger(agent)
    check = mocker.spy(CoreHandler, "check_multiple_permissions")

    call(name, user, agent, trigger)

    assert [
        (permission.operation_name, permission.context.id)
        for args, _ in check.call_args_list
        for permission in args[1]
    ] == [(operation.type, agent.id) for operation in operations]


@pytest.mark.django_db
@pytest.mark.parametrize("write", ["create", "update", "delete"])
def test_trigger_writes_need_the_feature_flag(
    data_fixture, periodic_trigger, settings, write
):
    user = data_fixture.create_user()
    agent = data_fixture.create_agent_application(user=user)
    trigger = periodic_trigger(agent)
    settings.FEATURE_FLAGS = []

    with pytest.raises(FeatureDisabledException):
        call(write, user, agent, trigger)

    trigger.refresh_from_db()
    assert (AgentTrigger.objects.count(), trigger.enabled, trigger.trashed) == (
        1,
        True,
        False,
    )


@pytest.mark.django_db
def test_list_triggers_serializes_type_message_service_and_schema(
    data_fixture, periodic_trigger, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent, interval="DAY", hour=9)

    response = api_client.get(agent_url(agent, "triggers:list"))

    assert response.status_code == 200, response.json()
    [item] = response.json()
    assert {key: item[key] for key in ("id", "type", "enabled", "message")} == {
        "id": trigger.id,
        "type": "periodic",
        "enabled": True,
        "message": MESSAGE,
    }
    assert (
        item["service"]["type"],
        item["service"]["interval"],
        item["service"]["hour"],
    ) == ("periodic", "DAY", 9)
    assert list(item["schema"]["properties"]) == ["triggered_at", "next_run_at"]


@pytest.mark.django_db
def test_create_trigger_returns_it_and_registers_the_action(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    registered = mocker.spy(CreateAgentTriggerActionType, "send_action_done_signal")

    response = api_client.post(
        agent_url(agent, "triggers:list"), {"type": "periodic", "message": MESSAGE}
    )

    assert response.status_code == 200, response.json()
    trigger = AgentTrigger.objects.get()
    assert isinstance(trigger.service.specific, CorePeriodicService)
    # Created with no interval, so arm() scheduled nothing.
    assert trigger.service.specific.next_run_at is None
    body = response.json()
    assert (body["id"], body["type"], body["enabled"], body["message"]) == (
        trigger.id,
        "periodic",
        True,
        MESSAGE,
    )
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "trigger_id": trigger.id,
        "trigger_type": "periodic",
    }


@pytest.mark.django_db
def test_create_trigger_with_service_values_schedules_it(
    data_fixture, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    service_values = {
        "interval": "DAY",
        "hour": 9,
        "minute": 0,
        "timezone": "Europe/Rome",
    }

    with freeze_time("2026-11-10 07:30"):
        token = data_fixture.generate_token(api_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
        response = api_client.post(
            agent_url(agent, "triggers:list"),
            {"type": "periodic", "message": MESSAGE, "service": service_values},
        )

    assert response.status_code == 200, response.json()
    service = CorePeriodicService.objects.get(agent_trigger__id=response.json()["id"])
    assert {key: getattr(service, key) for key in service_values} == service_values
    assert service.next_run_at == datetime(2026, 11, 10, 8, 0, tzinfo=dt_timezone.utc)
    body = response.json()["service"]
    assert {key: body[key] for key in service_values} == service_values


@pytest.mark.django_db
@pytest.mark.parametrize(
    "service,error",
    [
        ({"timezone": "Mars/Olympus"}, "ERROR_TRIGGER_SERVICE_MISCONFIGURED"),
        ({"type": "http_trigger"}, "ERROR_REQUEST_BODY_VALIDATION"),
    ],
)
def test_create_rejects_invalid_service_values(
    data_fixture, api_client, api_user, service, error
):
    agent = data_fixture.create_agent_application(user=api_user)

    response = api_client.post(
        agent_url(agent, "triggers:list"),
        {"type": "periodic", "message": MESSAGE, "service": service},
    )

    assert response.status_code == 400
    assert response.json()["error"] == error
    assert not AgentTrigger.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "type_name,error",
    [
        ("manual", "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        ("http_trigger", "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        ("upsert_row", "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        ("unknown", "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        (5, "ERROR_REQUEST_BODY_VALIDATION"),
        (["periodic"], "ERROR_REQUEST_BODY_VALIDATION"),
    ],
)
def test_create_rejects_a_type_the_agent_can_not_use(
    data_fixture, api_client, api_user, type_name, error
):
    agent = data_fixture.create_agent_application(user=api_user)

    response = api_client.post(
        agent_url(agent, "triggers:list"),
        {"type": type_name, "message": MESSAGE, "service": {"interval": "DAY"}},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == error
    assert not AgentTrigger.objects.exists()


@pytest.mark.django_db
def test_update_refuses_to_switch_on_a_trigger_of_a_type_the_agent_can_not_use(
    data_fixture, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = data_fixture.create_agent_trigger(
        agent=agent,
        service=data_fixture.create_core_http_trigger_service(),
        enabled=False,
    )

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id),
        {"enabled": True},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"
    trigger.refresh_from_db()
    assert trigger.enabled is False
    assert trigger.service.specific.is_public is False


@pytest.mark.django_db
def test_update_trigger_saves_the_switch_message_and_service_values(
    data_fixture, periodic_trigger, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent)
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")
    message = {**MESSAGE, "formula": "'Hourly check'"}

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id),
        {
            "enabled": False,
            "message": message,
            "service": {"interval": "HOUR", "minute": 30},
        },
    )

    assert response.status_code == 200, response.json()
    trigger.refresh_from_db()
    service = CorePeriodicService.objects.get(id=trigger.service_id)
    assert (trigger.enabled, trigger.message, service.interval, service.minute) == (
        False,
        message,
        "HOUR",
        30,
    )
    body = response.json()
    assert (body["enabled"], body["message"], body["service"]["interval"]) == (
        False,
        message,
        "HOUR",
    )
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "trigger_id": trigger.id,
        "trigger_type": "periodic",
        "changed_fields": ["enabled", "message", "service"],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        {"enabled": False},
        {"enabled": False, "service": {}},
        {"enabled": False, "service": {"type": "periodic"}},
    ],
)
def test_update_without_service_values_leaves_the_service_alone(
    data_fixture, periodic_trigger, api_client, api_user, mocker, payload
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent, interval="DAY", hour=9)
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id), payload
    )

    assert response.status_code == 200, response.json()
    service = CorePeriodicService.objects.get(id=trigger.service_id)
    assert (service.interval, service.hour) == ("DAY", 9)
    assert registered.call_args.args[1]["changed_fields"] == ["enabled"]


@pytest.mark.django_db
def test_update_with_the_saved_values_neither_reschedules_nor_audits(
    data_fixture, periodic_trigger, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    next_run_at = timezone.now() + timedelta(days=3)
    trigger = periodic_trigger(
        agent, interval="MINUTE", minute=1, next_run_at=next_run_at
    )
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id),
        {
            "name": "",
            "enabled": True,
            "message": MESSAGE,
            "service": {"type": "periodic", "minute": "1"},
        },
    )

    assert response.status_code == 200, response.json()
    service = CorePeriodicService.objects.get(id=trigger.service_id)
    assert service.next_run_at == next_run_at
    assert not registered.called


@pytest.mark.django_db
def test_update_rejects_a_misconfigured_service(
    data_fixture, periodic_trigger, api_client, api_user, settings
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent, interval="HOUR")
    settings.INTEGRATIONS_PERIODIC_MINUTE_MIN = 5

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id),
        {"service": {"interval": "MINUTE", "minute": 1}},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_TRIGGER_SERVICE_MISCONFIGURED"
    assert CorePeriodicService.objects.get(id=trigger.service_id).interval == "HOUR"


@pytest.mark.django_db
def test_update_rejects_the_values_of_another_service_type(
    data_fixture, periodic_trigger, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent)

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id),
        {"service": {"type": "http_trigger"}},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert body["detail"]["service"]["type"][0]["code"] == "type_mismatch"


@pytest.mark.django_db
def test_delete_trigger_moves_it_to_the_trash(
    data_fixture, periodic_trigger, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    trigger = periodic_trigger(agent)
    registered = mocker.spy(DeleteAgentTriggerActionType, "send_action_done_signal")

    response = api_client.delete(
        agent_url(agent, "triggers:item", trigger_id=trigger.id)
    )

    assert response.status_code == 204
    assert not AgentTrigger.objects.filter(id=trigger.id).exists()
    assert AgentTrigger.objects_and_trash.get(id=trigger.id).trashed
    assert TrashEntry.objects.get().trash_item_type == "agent_trigger"
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "trigger_id": trigger.id,
        "trigger_type": "periodic",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize(
    "case,error",
    [
        ("unknown", "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST"),
        ("other_agent", "ERROR_AGENT_TRIGGER_DOES_NOT_EXIST"),
        ("trashed_agent", "ERROR_APPLICATION_DOES_NOT_EXIST"),
    ],
)
def test_a_trigger_out_of_reach_is_not_found(
    data_fixture, periodic_trigger, api_client, api_user, method, case, error
):
    agent = data_fixture.create_agent_application(user=api_user)
    owner = (
        data_fixture.create_agent_application(user=api_user)
        if case == "other_agent"
        else agent
    )
    trigger = periodic_trigger(owner)
    if case == "trashed_agent":
        CoreHandler().delete_application(api_user, agent)
    trigger_id = 0 if case == "unknown" else trigger.id

    response = getattr(api_client, method)(
        agent_url(agent, "triggers:item", trigger_id=trigger_id), {"enabled": False}
    )

    assert response.status_code == 404
    assert response.json()["error"] == error
    assert AgentTrigger.objects.filter(id=trigger.id, enabled=True).exists()


@pytest.mark.django_db
def test_a_trigger_saves_its_trimmed_name_and_names_its_trash_entry(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")
    list_url = agent_url(agent, "triggers:list")

    unnamed = api_client.post(list_url, {"type": "periodic", "message": MESSAGE})
    named = api_client.post(
        list_url, {"type": "periodic", "message": MESSAGE, "name": "  Digest  "}
    )
    too_long = api_client.post(
        list_url, {"type": "periodic", "message": MESSAGE, "name": "x" * 76}
    )

    assert (unnamed.json()["name"], named.json()["name"]) == ("", "Digest")
    assert too_long.status_code == 400
    assert too_long.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    url = agent_url(agent, "triggers:item", trigger_id=unnamed.json()["id"])
    renamed = api_client.patch(url, {"name": f" {'y' * 75} "})

    assert renamed.status_code == 200, renamed.json()
    assert AgentTrigger.objects.get(id=unnamed.json()["id"]).name == "y" * 75
    assert registered.call_args.args[1]["changed_fields"] == ["name"]
    assert api_client.patch(url, {"name": "y" * 76}).status_code == 400

    api_client.patch(url, {"name": ""})
    for created in (unnamed, named):
        api_client.delete(
            agent_url(agent, "triggers:item", trigger_id=created.json()["id"])
        )

    assert list(TrashEntry.objects.order_by("id").values_list("name", flat=True)) == [
        "periodic",
        "Digest",
    ]

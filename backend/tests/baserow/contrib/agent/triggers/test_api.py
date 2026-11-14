from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.test.utils import CaptureQueriesContext
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
from baserow.contrib.database.table.models import Table
from baserow.contrib.integrations.core.models import CorePeriodicService
from baserow.contrib.integrations.core.service_types import (
    CorePeriodicTriggerServiceType,
)
from baserow.contrib.integrations.local_baserow.models import LocalBaserowRowsCreated
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowsCreatedTriggerServiceType,
)
from baserow.core.exceptions import FeatureDisabledException
from baserow.core.handler import CoreHandler
from baserow.core.models import Agent as Identity
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

    assert api_client.get(url).json()["available_trigger_types"] == [
        "local_baserow_rows_created",
        "local_baserow_rows_updated",
        "local_baserow_rows_deleted",
        "periodic",
    ]

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


@pytest.mark.django_db
def test_configuration_tells_how_many_trigger_runs_can_wait(
    data_fixture, api_client, api_user, settings
):
    settings.AGENT_TRIGGER_MAX_QUEUED_RUNS = 3
    agent = data_fixture.create_agent_application(user=api_user)

    response = api_client.get(agent_url(agent, "configuration"))

    assert response.json()["max_queued_trigger_runs"] == 3


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
        "list_types": lambda: service.list_trigger_types(user, agent.id),
    }
    return calls[name]()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,operations",
    [
        ("list", [ReadAgentConfigurationOperationType]),
        ("get", [ReadAgentConfigurationOperationType]),
        ("list_types", [ReadAgentConfigurationOperationType]),
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
def test_list_triggers_serializes_type_message_and_service(
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
    assert list(item["service"]["schema"]["properties"]) == [
        "triggered_at",
        "next_run_at",
    ]


@pytest.mark.django_db
def test_list_triggers_query_count_does_not_grow_with_the_triggers(
    data_fixture, periodic_trigger, api_client, api_user
):
    agent = data_fixture.create_agent_application(user=api_user)
    url = agent_url(agent, "triggers:list")
    periodic_trigger(agent)
    api_client.get(url)

    with CaptureQueriesContext(connection) as one_trigger:
        api_client.get(url)
    for _ in range(4):
        periodic_trigger(agent)
    with CaptureQueriesContext(connection) as five_triggers:
        response = api_client.get(url)

    assert len(response.json()) == 5
    assert len(five_triggers) == len(one_trigger)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,trigger_loads",
    [({"name": "Digest"}, 1), ({"service": {"interval": "HOUR"}}, 2)],
)
def test_update_loads_the_trigger_twice_only_to_validate_service_values(
    data_fixture, periodic_trigger, api_client, api_user, payload, trigger_loads
):
    agent = data_fixture.create_agent_application(user=api_user)
    url = agent_url(agent, "triggers:item", trigger_id=periodic_trigger(agent).id)

    with CaptureQueriesContext(connection) as queries:
        response = api_client.patch(url, payload)

    assert response.status_code == 200
    loads = [
        query
        for query in queries.captured_queries
        if query["sql"].startswith('SELECT "agent_agenttrigger"')
    ]
    assert len(loads) == trigger_loads


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
        "",
        "Digest",
    ]


@pytest.mark.django_db
def test_a_trigger_saves_its_overlap_rule_and_shows_its_last_firing(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")
    list_url = agent_url(agent, "triggers:list")

    created = api_client.post(list_url, {"type": "periodic", "message": MESSAGE})
    waiting = api_client.post(
        list_url, {"type": "periodic", "message": MESSAGE, "on_overlap": "wait"}
    )

    assert created.status_code == waiting.status_code == 200, created.json()
    body = created.json()
    assert {
        key: body[key]
        for key in (
            "on_overlap",
            "last_fired_on",
            "last_skipped_on",
            "last_skipped_reason",
        )
    } == {
        "on_overlap": "skip",
        "last_fired_on": None,
        "last_skipped_on": None,
        "last_skipped_reason": "",
    }
    assert waiting.json()["on_overlap"] == "wait"

    url = agent_url(agent, "triggers:item", trigger_id=body["id"])
    response = api_client.patch(url, {"on_overlap": "wait"})

    assert response.status_code == 200, response.json()
    assert response.json()["on_overlap"] == "wait"
    assert AgentTrigger.objects.get(id=body["id"]).on_overlap == "wait"
    assert registered.call_args.args[1]["changed_fields"] == ["on_overlap"]

    rejected = api_client.patch(url, {"on_overlap": "queue"})

    assert rejected.status_code == 400
    assert rejected.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_a_trigger_saves_how_many_rows_each_conversation_gets(
    data_fixture, api_client, api_user, mocker
):
    agent = data_fixture.create_agent_application(user=api_user)
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")
    list_url = agent_url(agent, "triggers:list")

    default = api_client.post(list_url, {"type": "periodic", "message": MESSAGE})
    chosen = api_client.post(
        list_url, {"type": "periodic", "message": MESSAGE, "batch_size": 5}
    )
    too_small = api_client.post(
        list_url, {"type": "periodic", "message": MESSAGE, "batch_size": 0}
    )

    assert (default.json()["batch_size"], chosen.json()["batch_size"]) == (20, 5)
    assert too_small.status_code == 400
    assert too_small.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert AgentTrigger.objects.count() == 2

    url = agent_url(agent, "triggers:item", trigger_id=default.json()["id"])
    updated = api_client.patch(url, {"batch_size": 100})
    too_large = api_client.patch(url, {"batch_size": 101})

    assert updated.status_code == 200, updated.json()
    assert updated.json()["batch_size"] == 100
    assert registered.call_args.args[1]["changed_fields"] == ["batch_size"]
    assert too_large.status_code == 400
    assert AgentTrigger.objects.get(id=default.json()["id"]).batch_size == 100


@pytest.mark.django_db
def test_a_new_trigger_waits_unless_its_events_can_be_skipped(
    data_fixture, api_client, api_user, mocker
):
    mocker.patch(
        "baserow.contrib.agent.triggers.handler.AGENT_TRIGGER_TYPES_ENABLED",
        ("periodic", LocalBaserowRowsCreatedTriggerServiceType.type),
    )
    agent = data_fixture.create_agent_application(user=api_user)
    url = agent_url(agent, "triggers:list")
    rows = {"type": LocalBaserowRowsCreatedTriggerServiceType.type, "message": MESSAGE}

    responses = [
        api_client.post(url, rows),
        api_client.post(url, {"type": "periodic", "message": MESSAGE}),
        api_client.post(url, {**rows, "on_overlap": "skip"}),
    ]

    assert [response.json()["on_overlap"] for response in responses] == [
        "wait",
        "skip",
        "skip",
    ]


ROWS_CREATED = LocalBaserowRowsCreatedTriggerServiceType.type


def agent_reading_orders(
    data_fixture, user: AbstractUser
) -> tuple[AgentApplication, Table]:
    """An agent of the user acting as a member identity, and an Orders table."""

    agent = data_fixture.create_agent_application(user=user)
    identity = Identity.objects.create(workspace=agent.workspace, name="Reader")
    AgentApplication.objects.filter(id=agent.id).update(
        run_as_subject_type="core.Agent", run_as_subject_id=identity.id
    )
    database = data_fixture.create_database_application(
        workspace=agent.workspace, name="Sales"
    )
    return agent, data_fixture.create_database_table(database=database, name="Orders")


def remove_run_identity(agent: AgentApplication) -> None:
    AgentApplication.objects.filter(id=agent.id).update(
        run_as_subject_type=None, run_as_subject_id=None
    )


@pytest.mark.django_db
def test_trigger_types_offer_what_the_run_identity_reads(
    data_fixture, api_client, api_user
):
    agent, table = agent_reading_orders(data_fixture, api_user)
    url = agent_url(agent, "triggers:types")

    response = api_client.get(url)

    assert response.status_code == 200, response.json()
    by_type = {item["type"]: item for item in response.json()}
    assert list(by_type) == [
        "local_baserow_rows_created",
        "local_baserow_rows_updated",
        "local_baserow_rows_deleted",
        "periodic",
    ]
    assert by_type["periodic"] == {
        "type": "periodic",
        "form_choices": None,
        "default_on_overlap": "skip",
    }
    rows = by_type[ROWS_CREATED]
    [database] = rows["form_choices"]["databases"]
    assert (rows["default_on_overlap"], database["name"], database["views"]) == (
        "wait",
        "Sales",
        [],
    )
    assert [(item["id"], item["name"]) for item in database["tables"]] == [
        (table.id, "Orders")
    ]

    remove_run_identity(agent)

    unset = {item["type"]: item for item in api_client.get(url).json()}
    assert unset[ROWS_CREATED]["form_choices"] == {"databases": []}


@pytest.mark.django_db
def test_a_row_trigger_is_refused_a_table_its_run_identity_cannot_read(
    data_fixture, api_client, api_user
):
    agent, table = agent_reading_orders(data_fixture, api_user)
    elsewhere = data_fixture.create_database_table(user=api_user, name="Elsewhere")
    url = agent_url(agent, "triggers:list")

    refused = api_client.post(
        url,
        {
            "type": ROWS_CREATED,
            "message": MESSAGE,
            "service": {"table_id": elsewhere.id},
        },
    )

    assert refused.status_code == 400, refused.json()
    assert refused.json()["error"] == "ERROR_AGENT_TRIGGER_NO_ACCESS"
    assert not AgentTrigger.objects.exists()

    created = api_client.post(
        url,
        {"type": ROWS_CREATED, "message": MESSAGE, "service": {"table_id": table.id}},
    )
    item = agent_url(agent, "triggers:item", trigger_id=created.json()["id"])
    moved = api_client.patch(item, {"service": {"table_id": elsewhere.id}})

    assert created.status_code == 200, created.json()
    assert moved.status_code == 400
    assert moved.json()["error"] == "ERROR_AGENT_TRIGGER_NO_ACCESS"
    assert (
        LocalBaserowRowsCreated.objects.get(
            agent_trigger__id=created.json()["id"]
        ).table_id
        == table.id
    )


@pytest.mark.django_db
def test_a_row_trigger_cannot_switch_on_once_its_run_identity_is_gone(
    data_fixture, api_client, api_user
):
    agent, table = agent_reading_orders(data_fixture, api_user)
    created = api_client.post(
        agent_url(agent, "triggers:list"),
        {
            "type": ROWS_CREATED,
            "message": MESSAGE,
            "enabled": False,
            "service": {"table_id": table.id},
        },
    )
    item = agent_url(agent, "triggers:item", trigger_id=created.json()["id"])
    remove_run_identity(agent)

    switched = api_client.patch(item, {"enabled": True})
    edited = api_client.patch(
        item, {"message": MESSAGE, "on_overlap": "skip", "batch_size": 5}
    )

    assert switched.status_code == 400
    assert switched.json()["error"] == "ERROR_AGENT_TRIGGER_NO_ACCESS"
    assert edited.status_code == 200, edited.json()
    trigger = AgentTrigger.objects.get(id=created.json()["id"])
    assert (trigger.enabled, trigger.on_overlap, trigger.batch_size) == (
        False,
        "skip",
        5,
    )


@pytest.mark.django_db
def test_changing_the_type_replaces_the_service_and_keeps_the_trigger(
    data_fixture, api_client, api_user, mocker
):
    agent, table = agent_reading_orders(data_fixture, api_user)
    old_service = data_fixture.create_core_periodic_service(
        interval="DAY", hour=9, minute=0, timezone="UTC"
    )
    trigger = data_fixture.create_agent_trigger(
        agent=agent,
        service=old_service,
        message=MESSAGE,
        name="Digest",
        on_overlap="wait",
        batch_size=5,
        last_skipped_on=timezone.now(),
        last_skipped_reason="rate_limited",
    )
    conversation = data_fixture.create_shared_agent_conversation(
        agent=agent, trigger=trigger
    )
    registered = mocker.spy(UpdateAgentTriggerActionType, "send_action_done_signal")
    url = agent_url(agent, "triggers:item", trigger_id=trigger.id)
    message = {**MESSAGE, "formula": "'New orders'"}

    response = api_client.patch(
        url,
        {"type": ROWS_CREATED, "service": {"table_id": table.id}, "message": message},
    )

    assert response.status_code == 200, response.json()
    assert (response.json()["id"], response.json()["type"]) == (
        trigger.id,
        ROWS_CREATED,
    )
    trigger.refresh_from_db()
    assert trigger.service.specific.table_id == table.id
    assert not CorePeriodicService.objects.filter(id=old_service.id).exists()
    assert (
        trigger.enabled,
        trigger.name,
        trigger.on_overlap,
        trigger.batch_size,
        trigger.message,
        trigger.last_skipped_on,
        trigger.last_skipped_reason,
    ) == (True, "Digest", "wait", 5, message, None, "")
    conversation.refresh_from_db()
    assert conversation.trigger_id == trigger.id
    assert registered.call_args.args[1] == {
        "agent_id": agent.id,
        "trigger_id": trigger.id,
        "trigger_type": ROWS_CREATED,
        "changed_fields": ["message", "type", "service"],
    }

    rows_service_id = trigger.service_id
    schedule = {"interval": "DAY", "hour": 9, "minute": 0, "timezone": "UTC"}
    with freeze_time("2026-11-10 07:30"):
        token = data_fixture.generate_token(api_user)
        api_client.credentials(HTTP_AUTHORIZATION=f"JWT {token}")
        back = api_client.patch(url, {"type": "periodic", "service": schedule})

    assert back.status_code == 200, back.json()
    service = CorePeriodicService.objects.get(agent_trigger__id=trigger.id)
    assert service.next_run_at == datetime(2026, 11, 10, 9, 0, tzinfo=dt_timezone.utc)
    assert not LocalBaserowRowsCreated.objects.filter(id=rows_service_id).exists()


@pytest.mark.django_db
def test_changing_only_the_type_starts_from_the_new_types_defaults(
    data_fixture, api_client, api_user
):
    agent, table = agent_reading_orders(data_fixture, api_user)
    rows_service = data_fixture.create_local_baserow_rows_created_service(table=table)
    trigger = data_fixture.create_agent_trigger(
        agent=agent, service=rows_service, message=MESSAGE
    )

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id), {"type": "periodic"}
    )

    assert response.status_code == 200, response.json()
    service = CorePeriodicService.objects.get(agent_trigger__id=trigger.id)
    assert (service.interval, service.minute) == (None, 0)
    assert not LocalBaserowRowsCreated.objects.filter(id=rows_service.id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload,error",
    [
        ({"type": "http_trigger"}, "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        ({"type": "unknown"}, "ERROR_AGENT_TRIGGER_TYPE_NOT_AVAILABLE"),
        (
            {"type": ROWS_CREATED, "service": {"table_id": "elsewhere"}},
            "ERROR_AGENT_TRIGGER_NO_ACCESS",
        ),
    ],
)
def test_changing_the_type_is_refused_like_a_new_trigger(
    data_fixture, periodic_trigger, api_client, api_user, payload, error
):
    agent, _ = agent_reading_orders(data_fixture, api_user)
    elsewhere = data_fixture.create_database_table(user=api_user, name="Elsewhere")
    trigger = periodic_trigger(agent, interval="DAY", hour=9)
    service_id = trigger.service_id
    if "service" in payload:
        payload["service"]["table_id"] = elsewhere.id

    response = api_client.patch(
        agent_url(agent, "triggers:item", trigger_id=trigger.id), payload
    )

    assert response.status_code == 400
    assert response.json()["error"] == error
    trigger.refresh_from_db()
    assert trigger.service_id == service_id
    assert CorePeriodicService.objects.get(id=service_id).interval == "DAY"

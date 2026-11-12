import json
from datetime import datetime, timezone

import pytest
from rest_framework import serializers

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.triggers.data_providers import (
    AgentTriggerDispatchContext,
    TriggerDataProviderType,
)
from baserow.contrib.agent.triggers.handler import AgentTriggerHandler
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH
from baserow.contrib.database.fields.models import Field
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.formula.types import BaserowFormulaObject

PAYLOAD = {
    "triggered_at": "2026-11-09T09:00:00+00:00",
    "next_run_at": "2026-11-09T10:00:00+00:00",
}
FIRED_AT = datetime(2026, 11, 10, 9, 7, 42, tzinfo=timezone.utc)


class MessageSerializer(serializers.Serializer):
    message = FormulaSerializerField()


@pytest.fixture
def periodic_trigger(data_fixture):
    def create(message: str | BaserowFormulaObject = "") -> AgentTrigger:
        return data_fixture.create_agent_trigger(message=message)

    return create


@pytest.mark.parametrize(
    "formula,valid",
    [("get('trigger.triggered_at')", True), ("get('nowhere.triggered_at')", False)],
)
def test_message_formulas_are_validated_against_the_trigger_provider(formula, valid):
    serializer = MessageSerializer(
        data={"message": formula}, context={"application_type": AgentApplicationType}
    )

    assert serializer.is_valid() is valid, serializer.errors


@pytest.mark.django_db
def test_dispatch_context_exposes_the_payload_as_trigger(periodic_trigger):
    trigger = periodic_trigger()
    payload = {**PAYLOAD, "fired_at": "from the service"}
    context = AgentTriggerDispatchContext(trigger, payload, FIRED_AT)

    assert context["trigger.triggered_at"] == PAYLOAD["triggered_at"]
    assert context["trigger.fired_at"] == "2026-11-10 09:07 (UTC)"
    assert context["trigger.missing"] is None
    assert context.workspace == trigger.agent.workspace
    assert (context.clone().trigger, context.clone().fired_at) == (trigger, FIRED_AT)
    assert payload == {**PAYLOAD, "fired_at": "from the service"}


@pytest.mark.django_db
def test_formula_dates_use_the_timezone_fired_at_is_shown_in(data_fixture):
    service = data_fixture.create_core_periodic_service(timezone="Pacific/Auckland")
    trigger = data_fixture.create_agent_trigger(service=service)
    payload = {"triggered_at": "2026-01-02T09:30:00+13:00"}
    fired_at = datetime(2026, 1, 1, 20, 30, tzinfo=timezone.utc)
    context = AgentTriggerDispatchContext(trigger, payload, fired_at)
    formula = BaserowFormulaObject.create(
        "datetime_format(get('trigger.triggered_at'), 'YYYY-MM-DD')"
    )

    assert context["trigger.fired_at"] == "2026-01-02 09:30 (Pacific/Auckland)"
    assert (
        resolve_formula(formula, formula_runtime_function_registry, context)
        == "2026-01-02"
    )


@pytest.mark.django_db
def test_get_data_chunk_maps_list_payload_rows_through_the_service_type(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(user=user, table=table, name="Name")
    agent = data_fixture.create_agent_application(workspace=table.database.workspace)
    service = data_fixture.create_local_baserow_rows_created_service(table=table)
    trigger = data_fixture.create_agent_trigger(agent=agent, service=service)
    payload = {"results": [{"Name": "Horse"}], "has_next_page": False}
    context = AgentTriggerDispatchContext(trigger, payload, FIRED_AT)
    provider = TriggerDataProviderType()

    assert provider.get_data_chunk(context, ["rows", "0", field.db_column]) == "Horse"
    assert provider.get_data_chunk(context, ["rows", "0"]) == {"Name": "Horse"}
    assert provider.get_data_chunk(context, ["fired_at"]) == "2026-11-10 09:07 (UTC)"


@pytest.mark.django_db
def test_resolve_message_resolves_the_formula(periodic_trigger):
    trigger = periodic_trigger("concat('Digest for ', get('trigger.triggered_at'))")

    assert (
        AgentTriggerHandler().resolve_message(trigger, PAYLOAD, FIRED_AT)
        == "Digest for 2026-11-09T09:00:00+00:00"
    )


@pytest.mark.django_db
def test_resolve_message_resolves_the_default_message_in_the_service_timezone(
    data_fixture,
):
    trigger = data_fixture.create_agent_trigger(
        service=data_fixture.create_core_periodic_service(timezone="Europe/Rome"),
        message={
            "formula": "concat('Periodic trigger fired at ', get('trigger.fired_at'))",
            "mode": "simple",
            "version": "0.1",
        },
    )

    assert (
        AgentTriggerHandler().resolve_message(trigger, PAYLOAD, FIRED_AT)
        == "Periodic trigger fired at 2026-11-10 10:07 (Europe/Rome)"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("message", ["", "' '"])
def test_resolve_message_falls_back_to_the_payload(periodic_trigger, message):
    trigger = periodic_trigger(message)
    expected = "Trigger data:\n```json\n" + json.dumps(PAYLOAD, indent=2) + "\n```"

    assert AgentTriggerHandler().resolve_message(trigger, PAYLOAD, FIRED_AT) == expected


@pytest.mark.django_db
def test_resolve_message_cuts_to_the_message_limit(periodic_trigger):
    trigger = periodic_trigger("get('trigger.triggered_at')")
    payload = {"triggered_at": "x" * (AGENT_TEXT_MAX_LENGTH + 1)}

    assert (
        len(AgentTriggerHandler().resolve_message(trigger, payload, FIRED_AT))
        == AGENT_TEXT_MAX_LENGTH
    )


def orders_trigger(data_fixture, message: str = "") -> tuple[AgentTrigger, Field]:
    """A rows-created trigger on an Orders table with a Name and a Notes field."""

    table = data_fixture.create_database_table(name="Orders")
    name = data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_long_text_field(table=table, name="Notes")
    agent = data_fixture.create_agent_application(workspace=table.database.workspace)
    service = data_fixture.create_local_baserow_rows_created_service(
        table=table, integration=None
    )
    trigger = data_fixture.create_agent_trigger(
        agent=agent, service=service, message=message
    )
    return trigger, name


def rows_payload(*names: str, notes: str = "") -> dict:
    return {
        "results": [
            {"id": index, "Name": name, "Notes": notes}
            for index, name in enumerate(names, start=1)
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_a_list_payload_is_read_as_rows_next_to_its_event_values(data_fixture):
    trigger, name = orders_trigger(data_fixture)

    context = AgentTriggerDispatchContext(
        trigger, rows_payload("Horse", "Cow"), FIRED_AT
    )

    assert context[f"trigger.rows.1.{name.db_column}"] == "Cow"
    assert (context["trigger.count"], context["trigger.table"]) == (2, "Orders")
    assert context["trigger.fired_at"] == "2026-11-10 09:07 (UTC)"
    assert context["trigger.rows"] == (
        '\n```json\n[\n{"id": 1, "Name": "Horse", "Notes": ""},\n'
        '{"id": 2, "Name": "Cow", "Notes": ""}\n]\n```'
    )


@pytest.mark.django_db
def test_rows_over_the_message_room_are_left_out_whole_and_counted(data_fixture):
    trigger, _ = orders_trigger(
        data_fixture, "concat(get('trigger.count'), ' new: ', get('trigger.rows'))"
    )
    notes = "x" * 40_000

    content = AgentTriggerHandler().resolve_message(
        trigger, rows_payload("Horse", "Cow", "Pig", notes=notes), FIRED_AT
    )

    assert content.startswith('3 new: \n```json\n[\n{"id": 1, "Name": "Horse"')
    assert content.endswith(
        f'"Name": "Cow", "Notes": "{notes}"}}\n]\n```\n…and 1 more rows not shown'
    )
    assert "Pig" not in content
    assert len(content) < AGENT_TEXT_MAX_LENGTH


@pytest.mark.django_db
def test_a_row_trigger_without_a_message_opens_with_its_event_values_and_rows(
    data_fixture,
):
    trigger, _ = orders_trigger(data_fixture)

    content = AgentTriggerHandler().resolve_message(
        trigger, rows_payload("Horse"), FIRED_AT
    )

    assert content == (
        'Trigger data:\n```json\n{\n  "count": 1,\n  "table": "Orders"\n}\n```'
        '\n```json\n[\n{"id": 1, "Name": "Horse", "Notes": ""}\n]\n```'
    )

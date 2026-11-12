from datetime import datetime, timezone

import pytest
from rest_framework import serializers

from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.models import AgentTrigger
from baserow.contrib.agent.triggers.data_providers import (
    AgentTriggerDispatchContext,
    TriggerDataProviderType,
)
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

    assert provider.get_data_chunk(context, ["0", field.db_column]) == "Horse"
    assert provider.get_data_chunk(context, ["0"]) == {"Name": "Horse"}
    assert provider.get_data_chunk(context, ["fired_at"]) == "2026-11-10 09:07 (UTC)"

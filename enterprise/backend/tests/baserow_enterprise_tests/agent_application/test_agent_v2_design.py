import asyncio
from dataclasses import dataclass
from typing import Any

from django.urls import reverse

import pytest
from pydantic_ai.toolsets import AbstractToolset
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.agents.service import AgentService
from baserow.core.handler import CoreHandler
from baserow_enterprise.agent_application.approval_preview import (
    build_approval_preview,
)
from baserow_enterprise.agent_application.handler import AgentApplicationHandler
from baserow_enterprise.agent_application.models import AgentChat, AgentTool
from baserow_enterprise.agent_application.tools.gating import RuleToolset
from baserow_enterprise.agent_application.tools.handler import AgentToolHandler
from baserow_enterprise.agent_application.tools.rules import (
    normalize_workspace_config,
)
from baserow_enterprise.agent_application.triggers.handler import AgentTriggerHandler
from baserow_enterprise.agent_application.triggers.registries import (
    agent_trigger_type_registry,
    substitute_trigger_tokens,
)


@pytest.fixture
def agent_with_table(data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    field = data_fixture.create_text_field(user, table=table, name="Company")
    application = (
        CoreHandler()
        .create_application(user, workspace, "agent", init_with_data=True, name="Agent")
        .specific
    )
    agent = AgentApplicationHandler().get_main_agent(application)
    return user, token, workspace, application, agent, table, field


# ---------------------------------------------------------------------------
# Per-tool identities
# ---------------------------------------------------------------------------


@dataclass
class _FakeDeps:
    user: Any


@dataclass
class _FakeCtx:
    deps: _FakeDeps
    tool_call_approved: bool = False


class _EchoActorToolset(AbstractToolset):
    """Returns the subject a call runs as."""

    @property
    def id(self):
        return "echo"

    async def get_tools(self, ctx):
        return {}

    async def call_tool(self, name, tool_args, ctx, tool):
        return ctx.deps.user


def test_rule_toolset_runs_a_tool_as_its_identity():
    toolset = RuleToolset(
        _EchoActorToolset(),
        normalize_workspace_config({"access": "everything"}),
        identities={"list_tables": "other-identity"},
    )
    ctx = _FakeCtx(deps=_FakeDeps(user="agent-identity"))

    assert asyncio.run(toolset.call_tool("list_tables", {}, ctx, None)) == (
        "other-identity"
    )
    # Tools without an override keep the agent's identity, and the shared
    # deps are never mutated.
    assert asyncio.run(toolset.call_tool("list_rows", {}, ctx, None)) == (
        "agent-identity"
    )
    assert ctx.deps.user == "agent-identity"


@pytest.mark.django_db
def test_tool_identities_config_only_keeps_workspace_agents(
    agent_with_table, data_fixture
):
    user, token, workspace, application, agent, table, field = agent_with_table
    identity = AgentService().create_agent(user, workspace, name="Reader")
    other_workspace = data_fixture.create_workspace(user=user)
    foreign = AgentService().create_agent(user, other_workspace, name="Foreign")
    tool = AgentToolHandler().create_tool(user, agent, "workspace", config={})

    tool = AgentToolHandler().update_tool(
        user,
        tool,
        config={
            "access": "everything",
            "tool_identities": {
                "list_rows": identity.id,
                "list_tables": str(identity.id),
                "create_rows": foreign.id,
                "delete_rows": "nope",
            },
        },
    )

    assert tool.config["tool_identities"] == {
        "list_rows": identity.id,
        "list_tables": identity.id,
    }


@pytest.mark.django_db
def test_action_tool_identity_api(agent_with_table, data_fixture):
    user, token, workspace, application, agent, table, field = agent_with_table
    identity = AgentService().create_agent(user, workspace, name="Mailer")
    other_workspace = data_fixture.create_workspace(user=user)
    foreign = AgentService().create_agent(user, other_workspace, name="Foreign")
    tool = AgentToolHandler().create_tool(
        user, agent, "service", name="Notify", service_type_str="smtp_email"
    )
    url = reverse("api:agent:tool_item", kwargs={"tool_id": tool.id})

    response = api_client = None  # noqa: F841
    from rest_framework.test import APIClient

    client = APIClient()
    response = client.patch(
        url,
        {"identity_id": identity.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["identity_id"] == identity.id

    response = client.patch(
        url,
        {"identity_id": foreign.id},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST

    response = client.patch(
        url, {"identity_id": None}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["identity_id"] is None


# ---------------------------------------------------------------------------
# Trigger tokens, example payloads and substitution
# ---------------------------------------------------------------------------


def test_substitute_trigger_tokens_per_trigger_type():
    comment = {
        "message": "@Investor reach out",
        "user": {"id": 1, "name": "Bram"},
        "row_id": 7,
        "table_id": 12,
    }
    assert (
        substitute_trigger_tokens(
            "{{trigger.comment.author}} wrote: {{ trigger.comment.message }} "
            "on row {{trigger.row.id}} of {{trigger.table.id}}",
            "row_comment_created",
            comment,
        )
        == "Bram wrote: @Investor reach out on row 7 of 12"
    )

    rows = {"results": [{"id": 3, "Company": "SuperPlane"}, {"id": 4}]}
    assert (
        substitute_trigger_tokens(
            "Row {{trigger.row.id}}: {{trigger.row.Company}}", "rows_created", rows
        )
        == "Row 3: SuperPlane"
    )
    assert '"SuperPlane"' in substitute_trigger_tokens(
        "{{trigger.rows}}", "rows_created", rows
    )

    assert (
        substitute_trigger_tokens(
            "At {{trigger.time}}", "periodic", {"triggered_at": "2026-01-01T09:00"}
        )
        == "At 2026-01-01T09:00"
    )
    assert (
        substitute_trigger_tokens(
            "{{trigger.query.source}} / {{trigger.body.message}}",
            "http_trigger",
            {"query_params": {"source": "zapier"}, "body": {"message": "hi"}},
        )
        == "zapier / hi"
    )
    assert (
        substitute_trigger_tokens(
            "From {{trigger.email.from}}: {{trigger.email.subject}}",
            "email_trigger",
            {"from": {"address": "ada@example.com"}, "subject": "Hello"},
        )
        == "From ada@example.com: Hello"
    )
    # Unknown tokens and unknown triggers are left as written.
    assert (
        substitute_trigger_tokens("{{trigger.nothing}}", "periodic", {})
        == "{{trigger.nothing}}"
    )
    assert (
        substitute_trigger_tokens("{{trigger.time}}", "bogus", {}) == "{{trigger.time}}"
    )


@pytest.mark.django_db
def test_table_trigger_sample_payload_uses_the_table_fields(agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    trigger = AgentTriggerHandler().create_trigger(
        user,
        application,
        "local_baserow_rows_created",
        service_values={"table_id": table.id},
    )
    trigger_type = agent_trigger_type_registry.get("rows_created")

    sample = trigger_type.get_sample_payload(trigger)
    assert sample["results"][0]["id"] == 1
    assert sample["results"][0]["Company"] == "Sample company"
    assert [token["token"] for token in trigger_type.get_tokens(trigger)] == [
        "{{trigger.rows}}",
        "{{trigger.row.id}}",
        "{{trigger.row.Field name}}",
    ]


@pytest.mark.django_db
def test_trigger_api_lists_tokens_and_example(agent_with_table):
    from rest_framework.test import APIClient

    user, token, workspace, application, agent, table, field = agent_with_table
    AgentTriggerHandler().create_trigger(user, application, "periodic")

    response = APIClient().get(
        reverse("api:agent:triggers", kwargs={"application_id": application.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    listed = response.json()[0]
    assert listed["tokens"][0]["token"] == "{{trigger.time}}"
    assert "triggered_at" in listed["sample_payload"]


# ---------------------------------------------------------------------------
# Approval previews
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_approval_preview_for_rows_and_fields(agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    chat = AgentChat.objects.create(agent=agent, user=user)

    rows = build_approval_preview(
        chat,
        None,
        f"create_rows_in_table_{table.id}",
        {"rows": [{"Company": "A", "Stage": "New"}, {"Company": "B"}], "thought": "x"},
    )
    assert rows == {
        "kind": "table",
        "columns": ["Company", "Stage"],
        "rows": [["A", "New"], ["B", None]],
    }

    fields = build_approval_preview(
        chat, None, "create_fields", {"table_id": table.id, "thought": "add"}
    )
    assert fields == {
        "kind": "fields",
        "fields": [{"key": "Table id", "value": table.id}],
    }


@pytest.mark.django_db
def test_approval_preview_resolves_email_service_fields(agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    tool = AgentToolHandler().create_tool(
        user,
        agent,
        "service",
        name="Send intro email",
        config={"inputs": [{"name": "email", "type": "text"}]},
        service_type_str="smtp_email",
        service_values={
            "to_emails": "get('tool_input.email')",
            "subject": "'Interesting company'",
            "body": "'Hello there'",
        },
    )
    chat = AgentChat.objects.create(agent=agent, user=user)

    preview = build_approval_preview(
        chat, tool, "send_intro_email", {"email": "darko@example.com"}
    )

    assert preview["kind"] == "email"
    assert preview["to"] == "darko@example.com"
    assert preview["subject"] == "Interesting company"
    assert preview["body"] == "Hello there"


# ---------------------------------------------------------------------------
# Template setup
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_setup_creates_table_trigger_and_actions(agent_with_table):
    user, token, workspace, application, agent, table, field = agent_with_table
    AgentApplicationHandler().apply_setup(
        user,
        application,
        {
            "run_mode": "rows_created",
            "trigger_table_id": table.id,
            "actions": ["smtp_email", "slack_write_message"],
            "permissions": "ask_first",
        },
    )

    trigger = application.triggers.get()
    assert trigger.service.specific.get_type().type == "local_baserow_rows_created"
    assert trigger.service.specific.table_id == table.id
    assert sorted(
        tool.service.specific.get_type().type
        for tool in AgentTool.objects.filter(agent=agent, type="service")
    ) == ["slack_write_message", "smtp_email"]

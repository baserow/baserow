"""What the person deciding on a held call reads: every value the call sends."""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from baserow.contrib.integrations.mcp.handler import MCPServerHandler, MCPToolSettings
from baserow.core.chat_runs.tool_input import MAX_HELD_INPUT_SIZE

from ..integrations.mcp.utils import serve
from .test_replies import (
    allow_tools,
    decide,
    pause,
    respond,
    run_reply,
    tool_call,
)

RECIPIENTS = [f"person{index}@example.com" for index in range(25)]
BODY = "".join(f"Line {index} of the newsletter.\n" for index in range(80))[:1910]


def mcp_mail_server(sent: list) -> FastMCP:
    server = FastMCP("test")

    @server.tool()
    def send_mail(
        recipients: list[str], body: str, passenger: str = "", api_key: str = ""
    ) -> str:
        """Send an email."""

        sent.append({"recipients": recipients, "body": body, "passenger": passenger})
        return "Sent."

    return server


@pytest.fixture
def mail_agent(data_fixture, configured_agent, mocker):
    """An Agent whose connected app's ``send_mail`` asks first, and what it sent."""

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    sent = []
    serve(mocker, mcp_mail_server(sent))
    integration = data_fixture.create_mcp_server_integration(application=agent)
    MCPServerHandler().refresh_tools(integration)
    MCPServerHandler().update_tools(
        integration, [MCPToolSettings("send_mail", enabled=True, ask_first=True)]
    )
    return user, agent, f"mcp{integration.id}_send_mail", sent


@pytest.mark.django_db
def test_a_held_mcp_call_shows_every_argument_it_sends(mail_agent, mocker):
    assert len(BODY) == 1910
    user, agent, send, sent = mail_agent
    respond(
        mocker,
        (
            {
                0: tool_call(
                    send,
                    "call_mail",
                    recipients=RECIPIENTS,
                    body=BODY,
                    passenger="Ann Smith",
                    api_key="s3cret",
                )
            },
        ),
    )

    reply = pause(user, agent)

    [step] = reply.steps
    assert step["status"] == "waiting"
    assert "truncated" not in step["input"]
    assert step["input"]["values"] == {
        "recipients": RECIPIENTS,
        "body": BODY,
        "passenger": "Ann Smith",
        "api_key": "••••",
    }

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert sent == [{"recipients": RECIPIENTS, "body": BODY, "passenger": "Ann Smith"}]
    assert reply.steps[0]["status"] == "done"
    assert reply.steps[0]["input"]["values"]["recipients"] == RECIPIENTS


@pytest.mark.django_db
def test_a_held_mcp_call_too_large_to_store_still_shows_its_arguments(
    mail_agent, mocker
):
    user, agent, send, _ = mail_agent
    body = "b" * (MAX_HELD_INPUT_SIZE + 10_000)
    respond(
        mocker,
        ({0: tool_call(send, "call_mail", recipients=RECIPIENTS, body=body)},),
    )

    reply = pause(user, agent)

    [step] = reply.steps
    held = step["input"]
    assert step["status"] == "waiting"
    assert held["truncated"] is True
    assert held["values"]["recipients"] == RECIPIENTS
    shown = held["values"]["body"]
    assert len(shown) == len(body) - held["omitted_characters"] + 1
    assert shown.startswith("b" * 200_000)
    assert len(json.dumps(held["values"])) <= MAX_HELD_INPUT_SIZE


@pytest.fixture
def rows_agent(data_fixture, configured_agent):
    """
    An Agent that asks first before it changes or deletes rows of a table with
    11 fields and 11 rows.
    """

    user = data_fixture.create_user()
    agent = configured_agent(user=user)
    table = allow_tools(
        data_fixture,
        agent,
        ("get_table_schema", "list_table_rows", "update_rows", "delete_rows"),
        ask_first=("update_rows", "delete_rows"),
    )
    names = [f"Field {index}" for index in range(9)] + ["Bank account"]
    for name in names:
        data_fixture.create_text_field(table=table, name=name)
    primary = table.field_set.get(name="Name")
    model = table.get_model()
    rows = [
        model.objects.create(**{f"field_{primary.id}": f"Customer {index}"})
        for index in range(11)
    ]
    return user, agent, table, ["Name", *names], rows


@pytest.mark.django_db
def test_a_held_row_update_shows_every_value_whole(rows_agent, mocker):
    user, agent, table, names, rows = rows_agent
    values = {name: f"New {name}" for name in names}
    values["Field 0"] = "n" * 1500
    values["Bank account"] = "NL91 ABNA 0417 1643 00"
    assert len(values) == 11
    respond(
        mocker,
        (
            {
                0: tool_call(
                    "update_rows",
                    "call_update",
                    table_id=table.id,
                    rows=[{"id": rows[0].id, **values}],
                )
            },
        ),
    )

    reply = pause(user, agent)

    [step] = reply.steps
    assert step["status"] == "waiting"
    assert "truncated" not in step["input"]
    assert step["input"]["values"]["rows"] == [{"row": "Customer 0", "values": values}]

    run_reply(decide(user, reply, approved=True))

    reply.refresh_from_db()
    assert reply.steps[0]["status"] == "done"
    assert reply.steps[0]["input"]["values"]["rows"][0]["values"] == values
    bank_account = table.field_set.get(name="Bank account")
    row = table.get_model().objects.get(id=rows[0].id)
    assert getattr(row, f"field_{bank_account.id}") == "NL91 ABNA 0417 1643 00"


@pytest.mark.django_db
def test_a_held_delete_shows_every_row(rows_agent, mocker):
    user, agent, table, _, rows = rows_agent
    respond(
        mocker,
        (
            {
                0: tool_call(
                    "delete_rows",
                    "call_delete",
                    table_id=table.id,
                    row_ids=[row.id for row in rows],
                )
            },
        ),
    )

    reply = pause(user, agent)

    [step] = reply.steps
    assert step["status"] == "waiting"
    assert step["input"]["requested_count"] == 11
    assert "truncated" not in step["input"]
    assert step["input"]["values"]["rows"] == [
        f"Customer {index}" for index in range(11)
    ]

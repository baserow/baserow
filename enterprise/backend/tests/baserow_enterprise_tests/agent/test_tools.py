import asyncio
import json
from unittest.mock import Mock

import pytest
from asgiref.sync import async_to_sync
from pydantic_ai.models.function import DeltaToolCall, FunctionModel

from baserow.contrib.agent.api.serializers import AgentMessageSerializer
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import AgentResponder
from baserow.contrib.agent.types import AgentReplyRequest
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.agents.service import AgentService
from baserow.core.tools import ToolContext
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_tool_calls_recheck_the_identity_role(
    enterprise_data_fixture, enable_enterprise, synced_roles, settings
):
    settings.BASEROW_USE_LOCAL_CACHE = True
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    table = enterprise_data_fixture.create_database_table(
        database=enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    )
    enterprise_data_fixture.create_text_field(table=table, name="Name", primary=True)
    service = AgentService()
    identity = service.create_agent(admin, workspace, name="Writer", role_uid="EDITOR")
    tool = agent_tool_type_registry.get("create_rows").get_tool(
        ToolContext(user=identity, workspace=workspace)
    )

    def create(name):
        arguments = tool.function_schema.validator.validate_python(
            {"table_id": table.id, "rows": [{"Name": name}]}
        )
        return async_to_sync(tool.function)(**arguments)

    assert create("Before downgrade").return_value[0]["Name"] == "Before downgrade"
    service.update_agent(admin, identity, role_uid="VIEWER")

    refused = create("After downgrade")
    assert refused.return_value == {
        "error": "You don't have permission to do this in this workspace."
    }
    assert refused.metadata == {"error_code": "permission_denied"}
    assert list(
        table.get_model(attribute_names=True).objects.values_list("name", flat=True)
    ) == ["Before downgrade"]


@pytest.mark.django_db
def test_linked_table_names_already_disclosed_by_schema_survive_a_denied_read(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    source, linked, hidden = [
        enterprise_data_fixture.create_database_table(database=database, name=name)
        for name in ("Projects", "Customers", "UNDISCLOSED_TABLE_CANARY")
    ]
    for table in (source, linked, hidden):
        enterprise_data_fixture.create_text_field(
            table=table, name="Name", primary=True
        )
    FieldHandler().create_field(
        admin, source, "link_row", name="Customer", link_row_table=linked
    )
    identity = AgentService().create_agent(
        admin, workspace, name="Reader", role_uid="NO_ACCESS"
    )
    RoleAssignmentHandler().assign_role(
        identity, workspace, role=Role.objects.get(uid="VIEWER"), scope=source
    )
    application = enterprise_data_fixture.create_agent_application(workspace=workspace)
    reply = enterprise_data_fixture.create_agent_message(
        user=admin, agent=application, role="assistant", status="running"
    )
    request = AgentReplyRequest(
        reply_id=reply.id,
        workspace=workspace,
        instructions="Read tables.",
        provider_type="openai",
        model_identifier="test-model",
        prompt="Read related rows.",
        history=[],
        acting_subject=identity,
        allowed_tool_names=["list_tables", "get_table_schema", "list_table_rows"],
    )
    calls = iter(
        [
            ("list_tables", {}),
            ("get_table_schema", {"table_ids": [source.id]}),
            ("list_table_rows", {"table_id": linked.id}),
            ("list_table_rows", {"table_id": hidden.id}),
        ]
    )

    async def stream(messages, info):
        call = next(calls, None)
        if call is None:
            yield "Done."
        else:
            name, arguments = call
            yield {0: DeltaToolCall(name=name, json_args=json.dumps(arguments))}

    async def wait_for_stop():
        await asyncio.Event().wait()

    journal = Mock(stop_reason=None)
    journal.wait_for_stop = wait_for_stop
    responder = AgentResponder(
        request, journal, FunctionModel(stream_function=stream), {}
    )

    outcome = async_to_sync(responder.answer)()
    saved = AgentHandler().finish_reply(
        reply.id, outcome.status, outcome.error_code, outcome.result
    )
    saved.refresh_from_db()

    assert saved.status == "completed"
    assert [step["status"] for step in saved.steps] == [
        "done",
        "done",
        "failed",
        "failed",
    ]
    assert saved.steps[1]["input"]["target"] == "Projects"
    assert saved.steps[2]["input"]["target"] == "Customers"
    assert saved.steps[2]["error_code"] == "not_found"
    assert "target" not in saved.steps[3]["input"]
    assert saved.steps[3]["error_code"] == "not_found"
    emitted = [
        entry.args[1]
        for entry in journal.emit.call_args_list
        if entry.args[0] == "step"
    ]
    linked_steps = [step for step in emitted if step["id"] == saved.steps[2]["id"]]
    assert [step["status"] for step in linked_steps] == ["running", "failed"]
    assert all(step["input"]["target"] == "Customers" for step in linked_steps)
    assert AgentMessageSerializer(saved).data["steps"] == saved.steps
    assert "UNDISCLOSED_TABLE_CANARY" not in json.dumps(emitted)
    assert "UNDISCLOSED_TABLE_CANARY" not in json.dumps(saved.steps)

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.messages import (
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from baserow_enterprise.assistant.action_memory import (
    get_mutation_evidence,
    get_verified_tool_outcomes,
)
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.tools.automation.types.node import (
    ActionNodeCreate,
    TriggerNodeCreate,
)
from baserow_enterprise.assistant.tools.builder.types.data_source import (
    DataSourceCreate,
)
from baserow_enterprise.assistant.tools.database.tools import (
    create_fields,
    create_tables,
    create_view_filters,
    create_views,
)
from baserow_enterprise.assistant.tools.registries import (
    AssistantToolRegistry,
    AssistantToolType,
)
from baserow_enterprise.assistant.tools.routing import ModeAwareToolset
from baserow_enterprise.assistant.tools.toolset import InlineRefsToolset

from .utils import make_test_ctx


@pytest.mark.asyncio
async def test_routed_call_remains_in_instructions_until_reissued():
    from baserow_enterprise.assistant.agents import dynamic_pending_mode_calls

    deps = SimpleNamespace(mode=AgentMode.DATABASE)
    executed = []
    step = 0

    def create_workflows(name: str):
        executed.append(name)
        return {"created_workflows": [{"id": 1, "name": name}]}

    def list_tables():
        return []

    def respond(messages, info):
        nonlocal step
        step += 1
        if step == 1:
            part = ToolCallPart("search_tools", {"queries": ["create_workflows"]})
        elif step == 2:
            part = ToolCallPart("create_workflows", {"name": "Process Orders"})
        elif step in (3, 4):
            assert executed == []
            assert "create_workflows" in info.instructions
            assert "not executed" in info.instructions
            # An intervening lookup must not discard the unfinished operation.
            part = (
                ToolCallPart("list_tables", {})
                if step == 3
                else ToolCallPart("create_workflows", {"name": "Process Orders"})
            )
        else:
            assert step == 5
            assert "pending_mode_calls" not in info.instructions
            part = TextPart("Created Process Orders.")
        return ModelResponse(parts=[part])

    model = FunctionModel(respond, profile={"supported_native_tools": frozenset()})
    toolset = ModeAwareToolset(
        InlineRefsToolset(
            FunctionToolset([create_workflows, list_tables]),
            model=model,
            model_profile=MagicMock(),
        ),
        deps,
    )
    result = await Agent(
        model=model,
        toolsets=[toolset],
        instructions=["Complete the user's request.", dynamic_pending_mode_calls],
    ).run("Create a workflow", deps=deps)
    assert result.output == "Created Process Orders."
    assert executed == ["Process Orders"]


@pytest.mark.asyncio
async def test_deferred_tool_switches_modes_then_executes_once():
    executed = []
    requests = []
    deps = SimpleNamespace(mode=AgentMode.DATABASE)

    def create_workflows(name: str):
        executed.append(name)
        return {"created_workflows": [{"id": 1, "name": name}]}

    def respond(messages, info):
        requests.append({tool.name: tool for tool in info.function_tools})
        step = len(requests)
        if step == 1:
            assert "search_tools" in requests[-1]
            assert "create_workflows" not in requests[-1]
            part = ToolCallPart("search_tools", {"queries": ["create_workflows"]})
        elif step == 2:
            assert executed == []
            part = ToolCallPart("create_workflows", {})
        elif step == 3:
            assert deps.mode == AgentMode.AUTOMATION
            assert executed == []
            assert all(
                not evidence.changed for evidence in get_mutation_evidence(messages)
            )
            assert get_verified_tool_outcomes(messages) == []
            assert any(
                isinstance(part, ToolReturnPart)
                and part.content.get("changed") is False
                and "was not executed yet" in part.content["next_steps"]
                for part in messages[-1].parts
            )
            assert requests[-1]["create_workflows"].parameters_json_schema[
                "required"
            ] == ["name"]
            part = ToolCallPart("create_workflows", {"name": "Process Orders"})
        else:
            assert step == 4
            part = TextPart("Created Process Orders.")
        return ModelResponse(parts=[part])

    model = FunctionModel(respond, profile={"supported_native_tools": frozenset()})
    toolset = ModeAwareToolset(
        InlineRefsToolset(
            FunctionToolset([create_workflows]), model=model, model_profile=MagicMock()
        ),
        deps,
    )

    result = await Agent(model=model, toolsets=[toolset], retries=0).run(
        "Create a workflow", deps=deps
    )

    assert result.output == "Created Process Orders."
    assert executed == ["Process Orders"]


@pytest.mark.asyncio
async def test_unavailable_tool_group_is_absent_from_routing_and_catalog():
    def create_workflows(name: str):
        raise AssertionError("An unavailable tool must never execute")

    class UnavailableTools(AssistantToolType):
        type = "unavailable"

        def can_use(self, user, workspace):
            return False

        def get_tool_functions(self):
            return [create_workflows]

        def get_toolset(self):
            return FunctionToolset([create_workflows])

    registry = AssistantToolRegistry()
    registry.register(UnavailableTools())
    deps = SimpleNamespace(mode=AgentMode.DATABASE)
    model = TestModel()
    toolset, catalog = registry.build_toolset(None, None, model, MagicMock(), deps)
    ctx = RunContext(deps=deps, model=model, usage=RunUsage(), prompt="Create")

    assert catalog == ""
    assert await toolset.get_tools(ctx) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "function, arguments",
    [
        (
            create_tables,
            {"database_id": 1, "tables": [], "add_sample_rows": False},
        ),
        (create_fields, {"table_id": 1, "fields": []}),
        (create_views, {"table_id": 1, "views": []}),
        (create_view_filters, {"view_filters": []}),
    ],
)
async def test_empty_creation_payload_retries_before_accessing_the_database(
    function, arguments
):
    """The missing database fixture also prevents unnoticed lookups or writes."""

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([function]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(
        deps=make_test_ctx(None, None).deps,
        model=model,
        usage=RunUsage(),
        prompt="Create items",
    )
    tools = await toolset.get_tools(ctx)

    with pytest.raises(ModelRetry, match="Nothing was changed"):
        await toolset.call_tool(
            function.__name__,
            {**arguments, "thought": "Creating items"},
            ctx,
            tools[function.__name__],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("table_id", [0, -1, "0"])
async def test_placeholder_ids_are_rejected_before_repair_or_execution(
    monkeypatch, table_id
):
    executed = []

    def read_table(table_id: int):
        executed.append(table_id)

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([read_table]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(deps=None, model=model, usage=RunUsage(), prompt="Read a table")
    tools = await toolset.get_tools(ctx)
    repair = AsyncMock()
    monkeypatch.setattr(toolset, "_fix_tool_args", repair)

    result = await toolset.call_tool(
        "read_table", {"table_id": table_id}, ctx, tools["read_table"]
    )

    assert "Not executed" in result["error"]
    assert "list_tables" in result["next_steps"]
    assert executed == []
    repair.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_id_cannot_be_repaired_without_real_information(monkeypatch):
    executed = []

    def read_table(table_id: int):
        executed.append(table_id)

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([read_table]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(deps=None, model=model, usage=RunUsage(), prompt="Read a table")
    tools = await toolset.get_tools(ctx)
    repair = AsyncMock(
        return_value=SimpleNamespace(
            output=json.dumps({"__cannot_fix__": "table_id must come from list_tables"})
        )
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.toolset.run_agent_with_model", repair
    )

    with pytest.raises(ModelRetry, match="table_id must come from list_tables"):
        await toolset.call_tool("read_table", {}, ctx, tools["read_table"])

    repair.assert_awaited_once()
    assert executed == []


@pytest.mark.asyncio
@pytest.mark.parametrize("table_id", ["--1", "²"])
async def test_malformed_ids_reach_argument_repair_without_running_the_tool(
    monkeypatch, table_id
):
    executed = []

    def read_table(table_id: int):
        executed.append(table_id)

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([read_table]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(deps=None, model=model, usage=RunUsage(), prompt="Read a table")
    tools = await toolset.get_tools(ctx)
    repair = AsyncMock(side_effect=ModelRetry("Read the real table ID first."))
    monkeypatch.setattr(toolset, "_fix_tool_args", repair)

    with pytest.raises(ModelRetry, match="Read the real table ID first"):
        await toolset.call_tool(
            "read_table", {"table_id": table_id}, ctx, tools["read_table"]
        )

    repair.assert_awaited_once()
    assert repair.call_args.args[:2] == ("read_table", {"table_id": table_id})
    assert executed == []


@pytest.mark.parametrize("node_type", [[], {}], ids=["list", "object"])
@pytest.mark.parametrize(
    "payload_model, fields",
    [
        pytest.param(TriggerNodeCreate, {"ref": "t", "label": "Trigger"}, id="trigger"),
        pytest.param(
            ActionNodeCreate,
            {"ref": "a", "label": "Action", "previous_node_ref": "t"},
            id="action",
        ),
        pytest.param(
            DataSourceCreate,
            {"ref": "d", "name": "Source", "table_id": 1},
            id="data-source",
        ),
    ],
)
def test_malformed_type_aliases_produce_validation_errors(
    payload_model, fields, node_type
):
    with pytest.raises(ValidationError) as exc:
        payload_model.model_validate({**fields, "type": node_type})

    assert [(error["loc"], error["type"]) for error in exc.value.errors()] == [
        (("type",), "literal_error")
    ]


@pytest.mark.asyncio
async def test_malformed_type_is_repaired_before_running_the_tool(monkeypatch):
    executed = []

    def read_source(data_source: DataSourceCreate):
        executed.append(data_source)
        return data_source.type

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([read_source]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(deps=None, model=model, usage=RunUsage(), prompt="Read a source")
    tools = await toolset.get_tools(ctx)
    fields = {"ref": "d", "name": "Source", "table_id": 1}
    repair = AsyncMock(
        return_value=SimpleNamespace(
            output=json.dumps(
                {"data_source": {**fields, "type": "local_baserow_list_rows"}}
            )
        )
    )
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.toolset.run_agent_with_model", repair
    )

    result = await toolset.call_tool(
        "read_source",
        {"data_source": {**fields, "type": []}},
        ctx,
        tools["read_source"],
    )

    repair.assert_awaited_once()
    assert result == "list_rows"
    assert executed == [DataSourceCreate(**fields, type="list_rows")]

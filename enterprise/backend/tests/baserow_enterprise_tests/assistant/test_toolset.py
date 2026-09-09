import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import RunUsage

from baserow_enterprise.assistant.tools.automation.types.node import (
    ActionNodeCreate,
    TriggerNodeCreate,
)
from baserow_enterprise.assistant.tools.builder.types.data_source import (
    DataSourceCreate,
)
from baserow_enterprise.assistant.tools.toolset import InlineRefsToolset


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

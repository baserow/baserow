import json
from collections.abc import Awaitable, Callable, Iterator
from types import SimpleNamespace
from typing import Annotated, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger
from pydantic import AfterValidator, ValidationError
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

from baserow.core.exceptions import PermissionDenied, UserNotInWorkspace
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
from baserow_enterprise.assistant.tools.shared.errors import ToolInputError
from baserow_enterprise.assistant.tools.toolset import (
    _MAX_REPORTED_ERRORS,
    InlineRefsToolset,
    _dropped_values,
)
from baserow_enterprise.assistant.types import BaseModel as AssistantBaseModel

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
            part = ToolCallPart("create_workflows", {})
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
async def test_complete_deferred_tool_executes_once_without_a_second_call():
    executed = []
    deps = SimpleNamespace(mode=AgentMode.DATABASE)
    step = 0

    def create_workflows(name: Annotated[str, AfterValidator(str.strip)]):
        executed.append(name)
        return {"created_workflows": [{"id": 1, "name": name}]}

    def respond(messages, info):
        nonlocal step
        step += 1
        if step == 1:
            part = ToolCallPart("search_tools", {"queries": ["create_workflows"]})
        elif step == 2:
            part = ToolCallPart("create_workflows", {"name": " Process Orders "})
        else:
            assert step == 3
            assert deps.mode == AgentMode.AUTOMATION
            assert executed == ["Process Orders"]
            assert any(evidence.changed for evidence in get_mutation_evidence(messages))
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
@pytest.mark.parametrize(
    "initial_args", [{}, {"name": 7}, {"name": "Orders", "extra": True}]
)
async def test_deferred_tool_switches_modes_then_executes_once(initial_args):
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
            part = ToolCallPart("create_workflows", initial_args)
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
@pytest.mark.parametrize(
    "error, expected",
    [
        (PermissionDenied(), "permission was denied"),
        (UserNotInWorkspace(), "outside the current workspace"),
        (ToolInputError("Invalid workflow"), "Invalid workflow"),
        (ModelRetry("Invalid workflow"), "Invalid workflow"),
    ],
)
async def test_complete_deferred_tool_preserves_domain_errors(error, expected):
    deps = SimpleNamespace(mode=AgentMode.DATABASE)

    def create_workflows(name: str):
        raise error

    model = TestModel()
    toolset = ModeAwareToolset(
        InlineRefsToolset(
            FunctionToolset([create_workflows]), model=model, model_profile=MagicMock()
        ),
        deps,
    )
    ctx = RunContext(deps=deps, model=model, usage=RunUsage(), prompt="Create")
    tools = await toolset.get_tools(ctx)
    if isinstance(error, ModelRetry):
        with pytest.raises(ModelRetry, match=expected):
            await toolset.call_tool(
                "create_workflows", {"name": "Orders"}, ctx, tools["create_workflows"]
            )
    else:
        result = await toolset.call_tool(
            "create_workflows", {"name": "Orders"}, ctx, tools["create_workflows"]
        )
        assert expected in result["error"]
    assert deps.mode == AgentMode.AUTOMATION


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", [AgentMode.DATABASE, AgentMode.APPLICATION, AgentMode.AUTOMATION]
)
async def test_docs_search_runs_in_every_mode_without_a_tool_search(mode):
    searched = []
    deps = SimpleNamespace(mode=mode)

    def search_user_docs(question: str):
        searched.append(question)
        return {"answer": "Use the share button."}

    def respond(messages, info):
        if searched:
            return ModelResponse(parts=[TextPart("Use the share button.")])
        return ModelResponse(
            parts=[ToolCallPart("search_user_docs", {"question": "Share a view"})]
        )

    model = FunctionModel(respond, profile={"supported_native_tools": frozenset()})
    toolset = ModeAwareToolset(
        InlineRefsToolset(
            FunctionToolset([search_user_docs]), model=model, model_profile=MagicMock()
        ),
        deps,
    )
    result = await Agent(model=model, toolsets=[toolset], retries=0).run(
        "How do I share a view?", deps=deps
    )

    assert result.output == "Use the share button."
    assert searched == ["Share a view"]
    assert result.usage.requests == 2


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


class _Column(AssistantBaseModel):
    name: str
    label: str | None = None


async def _save_column_toolset(
    monkeypatch: pytest.MonkeyPatch, repaired: dict[str, Any] | None = None
) -> tuple[Callable[[dict[str, Any]], Awaitable[Any]], AsyncMock, list[_Column]]:
    """
    Build a ``save_column`` toolset whose repair always gives the same answer.

    :param monkeypatch: Replaces the repair call.
    :param repaired: The arguments the repair answers with. Defaults to the column
        "Go".
    :return: A function that calls the tool, the repair mock and the saved columns.
    """

    saved: list[_Column] = []

    def save_column(column: _Column) -> None:
        saved.append(column)

    model = TestModel()
    toolset = InlineRefsToolset(
        FunctionToolset([save_column]), model=model, model_profile=MagicMock()
    )
    ctx = RunContext(deps=None, model=model, usage=RunUsage(), prompt="Save")
    tools = await toolset.get_tools(ctx)
    answer = {"column": {"name": "Go"}} if repaired is None else repaired
    repair = AsyncMock(return_value=SimpleNamespace(output=json.dumps(answer)))
    monkeypatch.setattr(
        "baserow_enterprise.assistant.tools.toolset.run_agent_with_model", repair
    )

    async def call(arguments: dict[str, Any]) -> Any:
        return await toolset.call_tool(
            "save_column", arguments, ctx, tools["save_column"]
        )

    return call, repair, saved


@pytest.mark.asyncio
async def test_repair_that_drops_a_value_does_not_run_the_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call, repair, saved = await _save_column_toolset(monkeypatch)

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"title": "Go", "navigation_type": "page"}})

    repair.assert_awaited_once()
    assert "did NOT run" in str(exc.value)
    assert (
        "A repair would drop or change these values, so the call did not run: "
        'column.navigation_type="page". Send each one under an accepted key with an '
        "accepted value, or leave it out on purpose."
    ) in str(exc.value)
    assert saved == []


@pytest.mark.asyncio
async def test_repair_that_drops_a_value_and_fails_validation_reports_the_sent_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call, repair, saved = await _save_column_toolset(
        monkeypatch, repaired={"column": {"caption": "Go"}}
    )

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"title": "Go", "navigation_type": "page"}})

    repair.assert_awaited_once()
    assert "'title' is not a key of this object" in str(exc.value)
    assert "caption" not in str(exc.value)
    assert (
        "A repair would drop or change these values, so the call did not run: "
        'column.navigation_type="page".'
    ) in str(exc.value)
    assert saved == []


@pytest.mark.asyncio
async def test_repair_that_fails_validation_reports_the_sent_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call, repair, saved = await _save_column_toolset(
        monkeypatch, repaired={"column": {"caption": "Go"}}
    )

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"title": "Go"}})

    repair.assert_awaited_once()
    assert str(exc.value).startswith("save_column did NOT run")
    assert "'title' is not a key of this object" in str(exc.value)
    assert "caption" not in str(exc.value)
    assert saved == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unknown",
    [
        pytest.param({"navigation_type": "page", "pin": 0}, id="values"),
        pytest.param({"notes": "[" * 100_000}, id="deeply-nested-json-text"),
    ],
)
async def test_unknown_keys_with_values_go_back_without_a_repair(
    monkeypatch: pytest.MonkeyPatch, unknown: dict[str, Any]
) -> None:
    call, repair, saved = await _save_column_toolset(monkeypatch)

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"name": "Go", **unknown}})

    repair.assert_not_awaited()
    assert str(exc.value).startswith("save_column did NOT run")
    assert all(
        f"'{key}' is not a key of this object" in str(exc.value) for key in unknown
    )
    assert saved == []


@pytest.mark.asyncio
async def test_deeply_nested_json_text_goes_back_without_running_the_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call, repair, saved = await _save_column_toolset(monkeypatch)
    nested = "[" * 100_000
    decode = json.loads

    def decode_or_overflow(text: str | bytes | bytearray, **kwargs: Any) -> Any:
        if text == nested:
            raise RecursionError
        return decode(text, **kwargs)

    # Whether json.loads overflows on this text depends on the stack size.
    monkeypatch.setattr(json, "loads", decode_or_overflow)

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"label": nested}})

    repair.assert_awaited_once()
    assert str(exc.value).startswith("save_column did NOT run")
    assert "A repair would drop" not in str(exc.value)
    assert saved == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sent",
    [
        pytest.param({"column": {"title": "Go"}}, id="moved-value"),
        pytest.param(
            {"column": {"name": "Go", "caption": ""}}, id="dropped-empty-value"
        ),
        pytest.param({"column": '{"name": "Go"}'}, id="decoded-json-string"),
    ],
)
async def test_repair_that_keeps_every_value_runs_the_tool(
    monkeypatch: pytest.MonkeyPatch, sent: dict[str, Any]
) -> None:
    call, repair, saved = await _save_column_toolset(monkeypatch)

    await call(sent)

    repair.assert_awaited_once()
    assert saved == [_Column(name="Go")]


@pytest.mark.asyncio
async def test_retry_message_lists_a_limited_number_of_dropped_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call, _, saved = await _save_column_toolset(monkeypatch)
    extras = {f"extra_{n}": f"value {n}" for n in range(_MAX_REPORTED_ERRORS + 2)}

    with pytest.raises(ModelRetry) as exc:
        await call({"column": {"title": "Go", **extras}})

    last_shown = _MAX_REPORTED_ERRORS - 1
    assert f'column.extra_{last_shown}="value {last_shown}"' in str(exc.value)
    assert f"column.extra_{_MAX_REPORTED_ERRORS}" not in str(exc.value)
    assert ", and 2 more." in str(exc.value)
    assert saved == []


@pytest.fixture
def logged_warnings() -> Iterator[list[str]]:
    messages: list[str] = []
    sink_id = logger.add(
        lambda message: messages.append(message.record["message"]), level="WARNING"
    )
    yield messages
    logger.remove(sink_id)


@pytest.mark.asyncio
async def test_warning_for_a_rejected_repair_lists_a_limited_number_of_values(
    monkeypatch: pytest.MonkeyPatch, logged_warnings: list[str]
) -> None:
    call, _, _ = await _save_column_toolset(monkeypatch)
    extras = {f"extra_{n}": f"value {n}" for n in range(_MAX_REPORTED_ERRORS + 2)}

    with pytest.raises(ModelRetry):
        await call({"column": {"title": "Go", **extras}})

    (warning,) = [text for text in logged_warnings if "would drop" in text]
    assert f"{len(extras)} in total" in warning
    assert f'column.extra_{_MAX_REPORTED_ERRORS - 1}="' in warning
    assert f"column.extra_{_MAX_REPORTED_ERRORS}" not in warning
    assert ", and 2 more" in warning


def test_dropped_values_compares_values_not_keys() -> None:
    original = {"a": {"x": "Go", "n": 5, "flag": True, "ratio": 2.0, "empty": None}}
    repaired = {"b": ["go"], "n": "5", "flag": "true", "ratio": 2}

    assert _dropped_values(original, repaired) == []
    assert _dropped_values({"a": "Go", "b": "Go"}, {"a": "Go"}) == [("b", "Go")]


def test_dropped_values_reports_list_paths_and_falsy_values() -> None:
    original = {"columns": [{"name": "A"}, {"name": "B", "hidden": False, "width": 0}]}
    repaired = {"columns": [{"name": "A"}, {"name": "B"}]}

    assert _dropped_values(original, repaired) == [
        ("columns.1.hidden", False),
        ("columns.1.width", 0),
    ]


@pytest.mark.parametrize(
    "sent, repaired",
    [
        pytest.param("Single Select", "single_select", id="space-to-underscore"),
        pytest.param("single-select", "SINGLE SELECT", id="hyphen-to-space"),
        pytest.param("single_select", "Single-Select", id="underscore-to-hyphen"),
        pytest.param("page\tname\n", "Page-Name", id="tab-and-newline"),
    ],
)
def test_dropped_values_ignores_case_and_separators(sent: str, repaired: str) -> None:
    assert _dropped_values({"type": sent}, {"type": repaired}) == []
    assert _dropped_values({"type": sent}, {"type": "multiple_select"}) == [
        ("type", sent)
    ]


@pytest.mark.parametrize(
    "sent, repaired",
    [
        pytest.param("19.90", 19.9, id="decimal-text-to-float"),
        pytest.param("-3", -3, id="negative-text-to-int"),
        pytest.param("2.0", 2, id="whole-decimal-text-to-int"),
        pytest.param(-2.5, "-2.50", id="negative-float-to-text"),
        pytest.param("9007199254740993", 9007199254740993, id="large-integer-text"),
    ],
)
def test_dropped_values_compares_numbers_as_numbers(sent: Any, repaired: Any) -> None:
    assert _dropped_values({"n": sent}, {"n": repaired}) == []


@pytest.mark.parametrize(
    "sent, repaired",
    [
        pytest.param(-5, 5, id="sign-of-int"),
        pytest.param(-2.5, 2.5, id="sign-of-float"),
        pytest.param("-10", 10, id="sign-of-text-to-int"),
        pytest.param("-10", "10", id="sign-of-text-to-text"),
        pytest.param("19.90", 19, id="truncated-decimal"),
        pytest.param("9007199254740993", 9007199254740992, id="last-digit-of-integer"),
    ],
)
def test_dropped_values_reports_numbers_that_differ(sent: Any, repaired: Any) -> None:
    assert _dropped_values({"n": sent}, {"n": repaired}) == [("n", sent)]


def test_dropped_values_reads_json_strings_as_the_values_they_hold() -> None:
    assert _dropped_values({"c": '[{"name": "A"}]'}, {"c": [{"name": "A"}]}) == []
    assert _dropped_values({"c": "[]"}, {"c": []}) == []
    assert _dropped_values(
        {"c": ' {"name": "A", "label": "B"}'}, {"c": {"name": "A"}}
    ) == [("c.label", "B")]


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("[draft] notes", id="bracket-text"),
        pytest.param("{not json", id="broken-json"),
        pytest.param("null", id="json-null"),
    ],
)
def test_dropped_values_keeps_other_strings_whole(text: str) -> None:
    assert _dropped_values({"c": text}, {}) == [("c", text)]

"""
Deterministic assembly guard for the Kuma assistant toolset.

No LLM, no network: the real production toolset is built via
``assistant_tool_registry.build_toolset()`` for a real user + workspace, and
every tool it exposes is forced to produce the JSON schema and description the
model actually reads. This is the guard against a pydantic model, annotation or
docstring change that leaves the assistant unable to start — a class of failure
that only the (paid, CI-skipped) eval suite would otherwise notice.
"""

import asyncio
import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth.models import AbstractUser

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import ToolsetTool
from pydantic_ai.usage import RunUsage

from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Workspace
from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps
from baserow_enterprise.assistant.tools.registries import assistant_tool_registry
from baserow_enterprise.assistant.tools.routing import (
    ModeAwareToolset,
    is_tool_active,
    tool_home,
)
from baserow_enterprise.assistant.tools.search_user_docs.tool_types import (
    SearchDocsToolType,
)
from baserow_enterprise.assistant.tools.toolset import (
    InlineRefsToolset,
    _find_placeholder_ids,
    format_tool_arg_errors,
    inline_refs,
)

from .utils import create_fake_tool_helpers

# Profile lookups take the model string; no live model is ever constructed.
MODEL_STRING = "groq:test-model"

ALL_MODES: list[AgentMode] = list(AgentMode)


def registered_tool_functions() -> list[Callable]:
    """Every tool function reachable through the assistant tool registry."""

    return [
        func
        for tool_type in assistant_tool_registry.get_all()
        for func in tool_type.get_tool_functions()
    ]


REGISTERED_TOOLS: dict[str, Callable] = {
    func.__name__: func for func in registered_tool_functions()
}


@dataclass(frozen=True)
class BuiltToolset:
    """The production toolset, its dependencies, and tool catalog."""

    toolset: AbstractToolset
    deps: AssistantDeps
    catalog: str

    def tools_in(self, mode: AgentMode) -> dict[str, ToolsetTool]:
        """Tools the assembled toolset exposes while the agent is in *mode*."""

        return {
            name: tool
            for name, tool in self.managed_tools_in(mode).items()
            if not tool.tool_def.defer_loading
        }

    def managed_tools_in(self, mode: AgentMode) -> dict[str, ToolsetTool]:
        """All resolvable tools, including deferred tools owned by another mode."""

        self.deps.mode = mode
        ctx: RunContext[AssistantDeps] = RunContext(
            deps=self.deps, model=TestModel(), usage=RunUsage()
        )
        return asyncio.run(self.toolset.get_tools(ctx))

    def all_exposed_tools(self) -> dict[str, ToolsetTool]:
        """Union of the tools exposed across every mode."""

        return {
            name: tool
            for mode in ALL_MODES
            for name, tool in self.tools_in(mode).items()
        }


def build_production_toolset(user: AbstractUser, workspace: Workspace) -> BuiltToolset:
    deps = AssistantDeps(
        user=user, workspace=workspace, tool_helpers=create_fake_tool_helpers()
    )
    toolset, catalog = assistant_tool_registry.build_toolset(
        user=user, workspace=workspace, model=MODEL_STRING, deps=deps
    )
    deps.tool_catalog = catalog
    return BuiltToolset(toolset=toolset, deps=deps, catalog=catalog)


@pytest.fixture
def searchable_knowledge_base() -> Iterator[None]:
    """Open the ``search_user_docs`` gate, which needs pgvector plus indexed docs."""

    with patch.object(SearchDocsToolType, "can_use", return_value=True):
        yield


@pytest.fixture
def built(data_fixture: Any, searchable_knowledge_base: None) -> BuiltToolset:
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    return build_production_toolset(user, workspace)


# ===========================================================================
# Assembly
# ===========================================================================


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ALL_MODES, ids=lambda mode: mode.value)
def test_toolset_assembles_in_every_mode(mode: AgentMode, built: BuiltToolset) -> None:
    tools = built.tools_in(mode)
    assert tools, f"{mode.value} mode exposes no tools at all"
    unknown = set(tools) - set(REGISTERED_TOOLS)
    assert not unknown, (
        f"{mode.value} mode exposes unregistered tools {sorted(unknown)}"
    )


@pytest.mark.django_db
def test_every_registered_tool_is_exposed_in_some_mode(built: BuiltToolset) -> None:
    exposed = set(built.all_exposed_tools())
    dropped = set(REGISTERED_TOOLS) - exposed
    assert not dropped, (
        f"Registered tools {sorted(dropped)} are unreachable in every mode: the "
        "assistant can never call them. Add a route for them in "
        "baserow_enterprise.assistant.tools.routing._tool_routes."
    )
    assert exposed == set(REGISTERED_TOOLS)


@pytest.mark.django_db
def test_wrong_mode_tools_are_deferred_but_resolvable(built: BuiltToolset) -> None:
    managed = built.managed_tools_in(AgentMode.DATABASE)

    assert not managed["create_tables"].tool_def.defer_loading
    routed = managed["create_workflows"]
    assert routed.tool_def.defer_loading
    assert routed.tool_def.metadata["assistant_mode"] == "automation"
    assert managed["list_workflows"].tool_def.metadata["assistant_mode"] == (
        "automation"
    )


@pytest.mark.django_db(transaction=True)
def test_gpt_oss_model_can_discover_route_and_execute_a_wrong_mode_tool(
    built: BuiltToolset, data_fixture: Any
) -> None:
    automation = data_fixture.create_automation_application(
        user=built.deps.user,
        workspace=built.deps.workspace,
        name="Restaurant Automation",
    )
    workflow = data_fixture.create_automation_workflow(
        automation=automation, name="Process Orders"
    )
    built.deps.mode = AgentMode.DATABASE
    expected = {
        "workflows": [{"id": workflow.id, "name": "Process Orders", "state": "draft"}]
    }
    visible_by_request: list[dict[str, Any]] = []

    def model_function(messages, info: AgentInfo) -> ModelResponse:
        visible = {tool.name: tool for tool in info.function_tools}
        visible_by_request.append(visible)
        request_number = len(visible_by_request)

        if request_number == 1:
            # Groq has no native ToolSearch, so Pydantic AI must expose its local
            # fallback while withholding the deferred production-tool schema.
            assert "search_tools" in visible
            assert "list_workflows" not in visible
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="search_tools",
                        args={"queries": ["list_workflows"]},
                    )
                ]
            )

        call = ToolCallPart(
            tool_name="list_workflows",
            args={
                "automation_id": automation.id,
                "thought": "Checking the existing workflows",
            },
        )
        if request_number == 2:
            # Discovery makes the real schema model-visible, but it remains
            # deferred until the mode-aware wrapper receives the first call.
            assert visible["list_workflows"].defer_loading
            assert set(
                visible["list_workflows"].parameters_json_schema["required"]
            ) == {"automation_id", "thought"}
            return ModelResponse(parts=[call])

        if request_number == 3:
            # The retry triggered by the discovered call switched modes. The
            # next request now contains the active, non-deferred schema.
            assert built.deps.mode == AgentMode.AUTOMATION
            assert not visible["list_workflows"].defer_loading
            return ModelResponse(parts=[call])

        tool_return = messages[-1].parts[-1]
        assert isinstance(tool_return, ToolReturnPart)
        assert tool_return.tool_name == "list_workflows"
        assert tool_return.content == expected
        return ModelResponse(parts=[TextPart(content="done")])

    gpt_oss = GroqModel(
        "openai/gpt-oss-120b", provider=GroqProvider(api_key="not-used")
    )
    agent: Agent[AssistantDeps, str] = Agent(
        model=FunctionModel(model_function, profile=gpt_oss.profile),
        deps_type=AssistantDeps,
        output_type=str,
        toolsets=[built.toolset],
    )

    result = agent.run_sync("List the workflows", deps=built.deps)

    assert result.output == "done"
    assert len(visible_by_request) == 4


@pytest.mark.django_db
def test_toolset_still_assembles_when_a_tool_group_is_gated_off(
    data_fixture: Any,
) -> None:
    """``can_use()`` returning False must drop tools, not break assembly."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    with patch.object(SearchDocsToolType, "can_use", return_value=False):
        built = build_production_toolset(user, workspace)
        exposed = set(built.all_exposed_tools())
    assert "search_user_docs" not in exposed
    assert "list_tables" in exposed
    assert built.catalog
    assert "search_user_docs" not in built.catalog


@pytest.mark.django_db
def test_permission_errors_become_actionable_tool_results(built: BuiltToolset) -> None:
    inner = MagicMock()
    inner.call_tool = AsyncMock(side_effect=PermissionDenied())
    routed = ModeAwareToolset(inner, built.deps)
    tool = built.managed_tools_in(AgentMode.DATABASE)["create_tables"]

    result = asyncio.run(routed.call_tool("create_tables", {}, None, tool))

    assert result["error"] == (
        "create_tables was not executed because permission was denied."
    )
    assert "Do not retry or claim" in result["next_steps"]


# ===========================================================================
# Per-tool schema contract
# ===========================================================================


def _refs_in(node: Any) -> list[str]:
    """Every ``$ref``/``$defs`` key left in a schema after ref inlining."""

    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("$ref", "$defs"):
                found.append(key)
            found.extend(_refs_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_refs_in(item))
    return found


@pytest.mark.django_db
@pytest.mark.parametrize("tool_name", sorted(REGISTERED_TOOLS))
def test_tool_exposes_a_schema_the_model_can_read(
    tool_name: str, built: BuiltToolset
) -> None:
    tool = built.all_exposed_tools().get(tool_name)
    assert tool is not None, f"{tool_name} is registered but exposed in no mode"

    description = (tool.tool_def.description or "").strip()
    assert description, (
        f"{tool_name} has no description: the model gets a nameless tool. Give "
        "the tool function a docstring."
    )

    schema = tool.tool_def.parameters_json_schema
    assert isinstance(schema, dict), f"{tool_name}: parameter schema is not an object"
    assert schema.get("type") == "object", (
        f"{tool_name}: parameter schema type is {schema.get('type')!r}, expected "
        "'object'"
    )
    properties = schema.get("properties")
    assert isinstance(properties, dict) and properties, (
        f"{tool_name}: parameter schema has no properties"
    )
    leftover = _refs_in(schema)
    assert not leftover, (
        f"{tool_name}: schema still contains {sorted(set(leftover))} after "
        "inline_refs; open-weight models cannot follow the indirection."
    )


# ===========================================================================
# Catalog
# ===========================================================================


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ALL_MODES, ids=lambda mode: mode.value)
def test_catalog_lists_every_tool_callable_in_that_mode(
    mode: AgentMode, built: BuiltToolset
) -> None:
    listed = {
        name
        for line in built.catalog.splitlines()
        if line.startswith("- ") and ": " in line
        for name in line.split(": ", 1)[1].split(", ")
    }
    missing = set(built.tools_in(mode)) - listed
    assert not missing, (
        f"The catalog omits {mode.value} tools {sorted(missing)}; the model "
        "will never know they exist."
    )


@pytest.mark.django_db
def test_deps_expose_one_catalog(built: BuiltToolset) -> None:
    assert built.deps.tool_catalog == built.catalog


def test_canonical_home_is_independent_from_shared_visibility() -> None:
    assert tool_home("list_workflows") == AgentMode.AUTOMATION
    assert is_tool_active("list_workflows", AgentMode.EXPLAIN)


@pytest.mark.django_db
def test_tool_catalog_stays_compact_and_does_not_repeat_tool_docs(
    built: BuiltToolset,
) -> None:
    assert len(built.catalog) < 4000
    assert "WHEN to use" not in built.catalog
    assert built.catalog.startswith("- database:")


# ===========================================================================
# Failure-path machinery (tools.toolset)
# ===========================================================================


class _FieldArg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    field_type: str


class _CreateFieldsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: int
    fields: list[_FieldArg]


_ARGS_SCHEMA: dict = inline_refs(_CreateFieldsArgs.model_json_schema())


class _ModelValidator:
    """Stand-in for the pydantic-core validator pydantic-ai attaches to a tool."""

    def validate_python(self, value: Any) -> dict[str, Any]:
        return _CreateFieldsArgs.model_validate(value).model_dump()


def _validation_errors(wrong_args: dict) -> list[dict]:
    with pytest.raises(ValidationError) as exc_info:
        _CreateFieldsArgs.model_validate(wrong_args)
    return exc_info.value.errors(include_url=False, include_context=False)


def test_arg_error_report_names_paths_shapes_and_id_producers() -> None:
    wrong_args = {"table_id": "nope", "fields": [{"name": "Amount", "kind": "number"}]}

    report = format_tool_arg_errors(
        "create_fields", _ARGS_SCHEMA, wrong_args, _validation_errors(wrong_args)
    )

    assert "create_fields did NOT run" in report
    assert "Call list_tables to get a real id" in report
    assert "fields.0.field_type: required" in report
    assert "name*, field_type*" in report
    assert "Never invent an id" in report


def test_arg_error_report_never_raises_on_malformed_error_payloads() -> None:
    report = format_tool_arg_errors("list_rows", {}, {"table_id": 1}, None)

    assert "list_rows did NOT run" in report


@pytest.mark.parametrize(
    "args,expected",
    [
        ({"table_id": 0}, [("table_id", "list_tables", 0)]),
        ({"navigate_to_page_id": 0}, [("navigate_to_page_id", "list_pages", 0)]),
        (
            {"view": {"cover_field_id": -1}},
            [("view.cover_field_id", "get_tables_schema", -1)],
        ),
        ({"field_ids": [3, 0]}, [("field_ids[1]", "get_tables_schema", 0)]),
        (
            {"filters": [{"field_id": "0"}]},
            [("filters[0].field_id", "get_tables_schema", "0")],
        ),
        ({"table_id": 5, "row_id": 0, "amount": 0}, []),
    ],
)
def test_placeholder_id_detection(
    args: dict[str, Any], expected: list[tuple[str, str, Any]]
) -> None:
    assert _find_placeholder_ids(args) == expected


def _wrapped_toolset() -> tuple[InlineRefsToolset, AsyncMock]:
    inner = MagicMock()
    inner.call_tool = AsyncMock(return_value={"ok": True})
    return InlineRefsToolset(inner, model=MODEL_STRING), inner.call_tool


def test_call_tool_blocks_invented_ids_before_execution() -> None:
    toolset, inner_call = _wrapped_toolset()

    result = asyncio.run(
        toolset.call_tool("create_fields", {"table_id": 0, "fields": []}, None, None)
    )

    assert "Invented IDs: table_id=0" in result["error"]
    assert "list_tables" in result["next_steps"]
    inner_call.assert_not_awaited()


def test_call_tool_executes_with_real_ids() -> None:
    toolset, inner_call = _wrapped_toolset()

    result = asyncio.run(toolset.call_tool("list_rows", {"table_id": 7}, None, None))

    assert result == {"ok": True}
    inner_call.assert_awaited_once_with("list_rows", {"table_id": 7}, None, None)


def _fixer_toolset() -> tuple[InlineRefsToolset, AsyncMock]:
    toolset, inner_call = _wrapped_toolset()
    toolset._original_validators["create_fields"] = _ModelValidator()
    toolset._schemas["create_fields"] = _ARGS_SCHEMA
    return toolset, inner_call


def _call_with_fixer_reply(toolset: InlineRefsToolset, reply: str) -> Any:
    with patch("baserow_enterprise.assistant.tools.toolset.Agent") as agent_cls:
        agent_cls.return_value.run = AsyncMock(
            return_value=SimpleNamespace(output=reply)
        )
        return asyncio.run(
            toolset.call_tool("create_fields", {"fields": []}, None, None)
        )


def test_fixed_args_are_revalidated_and_executed() -> None:
    toolset, inner_call = _fixer_toolset()
    fixed = {"table_id": 7, "fields": [{"name": "Amount", "field_type": "number"}]}

    result = _call_with_fixer_reply(toolset, json.dumps(fixed))

    assert result == {"ok": True}
    inner_call.assert_awaited_once_with("create_fields", fixed, None, None)


def test_cannot_fix_reply_raises_model_retry_instead_of_executing() -> None:
    toolset, inner_call = _fixer_toolset()
    reply = json.dumps({"__cannot_fix__": "the real table id"})

    with pytest.raises(ModelRetry, match="the real table id"):
        _call_with_fixer_reply(toolset, reply)
    inner_call.assert_not_awaited()


def test_still_invalid_fix_raises_the_rendered_report() -> None:
    toolset, inner_call = _fixer_toolset()

    with pytest.raises(ModelRetry, match="did NOT run") as exc_info:
        _call_with_fixer_reply(toolset, json.dumps({"fields": []}))

    assert "table_id" in str(exc_info.value)
    inner_call.assert_not_awaited()


def test_fixer_crash_degrades_to_model_retry_with_the_report() -> None:
    toolset, inner_call = _fixer_toolset()

    with patch("baserow_enterprise.assistant.tools.toolset.Agent") as agent_cls:
        agent_cls.return_value.run = AsyncMock(side_effect=RuntimeError("boom"))
        with pytest.raises(ModelRetry, match="did NOT run"):
            asyncio.run(toolset.call_tool("create_fields", {"fields": []}, None, None))
    inner_call.assert_not_awaited()

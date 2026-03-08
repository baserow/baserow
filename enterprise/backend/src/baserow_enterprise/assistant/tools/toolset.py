"""
Pydantic-ai toolset utilities for the assistant.

Contains schema helpers (``inline_refs``), lenient argument validation,
the ``InlineRefsToolset`` wrapper, ``ModeAwareToolset``, and the compact
tool manifest builder.  These are pure toolset concerns with no dependency
on the Baserow registry system.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import AgentDepsT, ToolsetTool
from typing_extensions import Self

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import AssistantDeps

# ---------------------------------------------------------------------------
# Schema utilities
# ---------------------------------------------------------------------------

# Keys that are JSON Schema / Pydantic metadata the LLM doesn't need.
_STRIP_KEYS = frozenset({"$defs", "discriminator", "title"})


def inline_refs(schema: dict) -> dict:
    """
    Recursively resolve all ``$ref`` pointers in a JSON schema, producing a
    self-contained schema with no ``$defs`` section.

    Also strips ``discriminator`` and ``title`` metadata that LLMs don't need
    and that can contain dangling ``$defs`` references.

    Many LLM providers (especially open-weight models behind Groq) struggle
    with ``$ref`` / ``$defs`` indirection.  Inlining makes the schema
    directly readable by the model.
    """

    defs = schema.get("$defs", {})
    _seen: set[str] = set()  # guard against circular refs

    def _resolve(node, *, _inside_properties=False):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].rsplit("/", 1)[-1]
                if ref_name in _seen:
                    return {"type": "object"}  # break circular ref
                _seen.add(ref_name)
                resolved = _resolve(defs[ref_name]) if ref_name in defs else node
                _seen.discard(ref_name)
                return resolved
            result = {}
            for k, v in node.items():
                # Strip JSON Schema metadata keys, but never strip property
                # names inside a "properties" dict (e.g. a field literally
                # named "title" or "description").
                if k in _STRIP_KEYS and not _inside_properties:
                    continue
                result[k] = _resolve(v, _inside_properties=(k == "properties"))
            return result
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        return node

    return _resolve(schema)


# ---------------------------------------------------------------------------
# Lenient validator & fixer
# ---------------------------------------------------------------------------

_FIXER_PROMPT = """\
You are a JSON repair tool. You receive a JSON object that failed schema \
validation, the validation errors, and the target JSON schema. Return ONLY \
the fixed JSON object — no explanation, no markdown fences. Preserve the \
original values as much as possible; only change what is needed to satisfy \
the schema."""


class _LenientValidator:
    """
    Drop-in replacement for pydantic-core ``SchemaValidator`` that parses
    JSON without enforcing the tool's parameter schema.

    Real validation happens later in ``InlineRefsToolset.call_tool()``,
    where we can attempt an async structured-output fix before failing.
    """

    def validate_json(self, input, *, allow_partial="off", **kwargs):
        if isinstance(input, (str, bytes, bytearray)):
            return json.loads(input) if input else {}
        return input

    def validate_python(self, input, *, allow_partial="off", **kwargs):
        return input if input is not None else {}


_LENIENT_VALIDATOR = _LenientValidator()


# ---------------------------------------------------------------------------
# InlineRefsToolset
# ---------------------------------------------------------------------------


class InlineRefsToolset(AbstractToolset[AgentDepsT]):
    """
    Wraps another toolset with two responsibilities:

    1. **Inline $ref/$defs** in tool parameter schemas so open-weight models
       can parse them directly.
    2. **Fix broken tool args** via a lightweight structured-output call
       instead of going through the full agent retry loop (which is slow
       and rarely succeeds).
    """

    def __init__(self, inner: AbstractToolset[AgentDepsT], model: str):
        self._inner = inner
        self._model = model
        self._original_validators: dict[str, Any] = {}
        self._schemas: dict[str, dict] = {}

    @property
    def id(self) -> str:
        return self._inner.id

    # --- Delegation methods (match WrapperToolset pattern) ---

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    def apply(self, visitor: Callable[[AbstractToolset[AgentDepsT]], None]) -> None:
        self._inner.apply(visitor)

    def visit_and_replace(
        self,
        visitor: Callable[[AbstractToolset[AgentDepsT]], AbstractToolset[AgentDepsT]],
    ) -> AbstractToolset[AgentDepsT]:
        new = InlineRefsToolset(
            self._inner.visit_and_replace(visitor), model=self._model
        )
        return new

    # --- Tool interception ---

    async def get_tools(self, ctx) -> dict[str, ToolsetTool[AgentDepsT]]:
        tools = await self._inner.get_tools(ctx)
        for name, tool in tools.items():
            # Inline $ref/$defs in the JSON schema
            tool.tool_def.parameters_json_schema = inline_refs(
                tool.tool_def.parameters_json_schema
            )
            # Save the original validator and schema, then replace with
            # lenient passthrough so validation failures reach call_tool()
            # where we can attempt an async fix.
            self._original_validators[name] = tool.args_validator
            self._schemas[name] = tool.tool_def.parameters_json_schema
            tool.args_validator = _LENIENT_VALIDATOR
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        original_validator = self._original_validators.get(name)
        if original_validator:
            try:
                tool_args = original_validator.validate_python(tool_args)
            except ValidationError as e:
                tool_args = await self._fix_tool_args(name, tool_args, e)
        return await self._inner.call_tool(name, tool_args, ctx, tool)

    async def _fix_tool_args(
        self,
        tool_name: str,
        wrong_args: dict[str, Any],
        error: ValidationError,
    ) -> dict[str, Any]:
        """
        Attempt to fix invalid tool arguments via a lightweight structured-
        output call. If the fix also fails validation, raises ``ModelRetry``
        so pydantic-ai can handle it normally.
        """

        schema = self._schemas.get(tool_name, {})
        error_details = error.errors(include_url=False, include_context=False)

        logger.warning(
            "[assistant] Tool '{}' args failed validation, attempting fix. Errors: {}",
            tool_name,
            error_details,
        )

        prompt = (
            f"Tool: {tool_name}\n\n"
            f"Schema:\n{json.dumps(schema, indent=2)}\n\n"
            f"Invalid input:\n{json.dumps(wrong_args, indent=2)}\n\n"
            f"Validation errors:\n{json.dumps(error_details, indent=2)}"
        )

        try:
            fix_agent = Agent(
                output_type=str,
                instructions=_FIXER_PROMPT,
                name="fix_agent",
            )
            from baserow_enterprise.assistant.model_profiles import (
                UTILITY,
                get_model_settings,
            )

            fixer_settings = get_model_settings(self._model, UTILITY)
            result = await fix_agent.run(
                prompt,
                model=self._model,
                model_settings={
                    **fixer_settings,
                    "response_format": {"type": "json_object"},
                },
            )
            fixed_args = json.loads(result.output)
        except Exception as exc:
            logger.warning(
                "[assistant] Fixer call failed for tool '{}': {}",
                tool_name,
                exc,
            )
            raise ModelRetry(
                f"Tool arguments invalid and fix attempt failed: {error_details}"
            ) from exc

        # Re-validate with original schema
        original_validator = self._original_validators[tool_name]
        try:
            validated = original_validator.validate_python(fixed_args)
        except ValidationError as e2:
            logger.warning(
                "[assistant] Fixed args for tool '{}' still invalid: {}",
                tool_name,
                e2.errors(include_url=False, include_context=False),
            )
            raise ModelRetry(
                f"Tool arguments still invalid after fix attempt: "
                f"{e2.errors(include_url=False, include_context=False)}"
            ) from e2

        return validated


# ---------------------------------------------------------------------------
# Mode-aware toolset
# ---------------------------------------------------------------------------


class ModeAwareToolset(AbstractToolset[AgentDepsT]):
    """
    Filters the inner toolset based on the current :class:`AgentMode`.

    In **DO** mode every tool is available except those in ``_DO_EXCLUDE``.
    In **EXPLAIN** mode only tools listed in ``_EXPLAIN_INCLUDE`` are exposed.
    """

    _DO_EXCLUDE: frozenset[str] = frozenset({"search_user_docs"})
    _EXPLAIN_INCLUDE: frozenset[str] = frozenset(
        {
            "list_builders",
            "list_tables",
            "get_tables_schema",
            "list_rows",
            "list_views",
            "list_workflows",
            "list_pages",
            "list_data_sources",
            "list_elements",
            "list_actions",
            "navigate",
            "search_user_docs",
            "switch_mode",
        }
    )

    def __init__(self, inner: AbstractToolset[AgentDepsT], deps: "AssistantDeps"):
        self._inner = inner
        self._deps = deps

    @property
    def id(self) -> str:
        return self._inner.id

    async def __aenter__(self) -> Self:
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> bool | None:
        return await self._inner.__aexit__(*args)

    def apply(self, visitor: Callable[[AbstractToolset[AgentDepsT]], None]) -> None:
        self._inner.apply(visitor)

    def visit_and_replace(
        self,
        visitor: Callable[[AbstractToolset[AgentDepsT]], AbstractToolset[AgentDepsT]],
    ) -> AbstractToolset[AgentDepsT]:
        return ModeAwareToolset(self._inner.visit_and_replace(visitor), self._deps)

    async def get_tools(self, ctx) -> dict[str, ToolsetTool[AgentDepsT]]:
        from baserow_enterprise.assistant.deps import AgentMode

        all_tools = await self._inner.get_tools(ctx)
        if self._deps.mode == AgentMode.DO:
            return {k: v for k, v in all_tools.items() if k not in self._DO_EXCLUDE}
        return {k: v for k, v in all_tools.items() if k in self._EXPLAIN_INCLUDE}

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError

        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except ToolInputError as exc:
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Compact tool manifest
# ---------------------------------------------------------------------------


def tool_manifest_line_compact(name: str, description: str) -> str:
    """Format a single tool entry — first line of description only."""

    desc = description.strip()
    first_line = desc.split("\n")[0].strip() if desc else name
    return f"- {name}: {first_line}"


_MODULE_LABELS: dict[str, str] = {
    "core": "Core (workspace & modules)",
    "navigation": "Navigation",
    "database": "Database (tables, fields, views, rows)",
    "builder": "Application Builder (pages, elements, data sources, actions)",
    "automation": "Automations (workflows, triggers, actions)",
    "search_user_docs": "Documentation",
}


def generate_tool_manifest_compact(
    module_groups: list[tuple[str, list[Callable]]],
    routing_rules: str = "",
) -> str:
    """
    Build a compact ``<available_tools>`` manifest: routing rules + tools
    grouped by module with section headers.

    :param module_groups: ``(module_type, funcs)`` pairs, one per module.
    :param routing_rules: Cross-tool routing rules to prepend.
    :return: A newline-separated manifest string.
    """

    lines: list[str] = []
    if routing_rules:
        lines.append(routing_rules.strip())
        lines.append("")
    for module_type, funcs in module_groups:
        if not funcs:
            continue
        label = _MODULE_LABELS.get(module_type, module_type)
        lines.append(f"## {label}")
        for func in funcs:
            lines.append(tool_manifest_line_compact(func.__name__, func.__doc__ or ""))
        lines.append("")
    return "\n".join(lines).rstrip()

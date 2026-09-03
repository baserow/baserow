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

from baserow_enterprise.assistant.deps import AgentMode

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
# Validation-error rendering
# ---------------------------------------------------------------------------

# Read-only tool that returns real values for a given id argument.
_ID_DISCOVERY_TOOL: dict[str, str] = {
    "table_id": "list_tables",
    "field_id": "get_tables_schema",
    "column_field_id": "get_tables_schema",
    "date_field_id": "get_tables_schema",
    "cover_field_id": "get_tables_schema",
    "start_date_field_id": "get_tables_schema",
    "end_date_field_id": "get_tables_schema",
    "view_id": "list_views",
    "row_id": "list_rows",
    "database_id": "list_builders",
    "application_id": "list_builders",
    "automation_id": "list_builders",
    "builder_id": "list_builders",
    "page_id": "list_pages",
    "navigate_to_page_id": "list_pages",
    "element_id": "list_elements",
    "data_source_id": "list_data_sources",
    "workflow_id": "list_workflows",
    "node_id": "list_nodes",
}

_MAX_REPORTED_ERRORS = 8


def _unwrap_union(node: Any) -> dict:
    """First non-null branch of an anyOf/oneOf, else the node itself."""

    if not isinstance(node, dict):
        return {}
    for key in ("anyOf", "oneOf"):
        for branch in node.get(key) or ():
            if isinstance(branch, dict) and branch.get("type") != "null":
                return branch
    return node


def _schema_at(schema: dict, loc: tuple) -> tuple[dict, bool]:
    """
    Follow a pydantic error ``loc`` into an already ref-inlined schema.

    Returns the deepest node reached and whether the whole path resolved.
    A union branch tag in ``loc`` (``('parent_element', 'int')``) does not
    resolve, so callers must never present a partial result as the
    authoritative key set.
    """

    node = _unwrap_union(schema)
    for part in loc:
        nxt = (
            _unwrap_union(node.get("items"))
            if isinstance(part, int)
            else _unwrap_union((node.get("properties") or {}).get(part))
        )
        if not nxt:
            return node, False
        node = nxt
    return node, True


def _keys_of(node: dict) -> list[str]:
    """Property names of *node*, required ones suffixed with ``*``."""

    required = set(node.get("required") or ())
    return [f"{k}*" if k in required else k for k in (node.get("properties") or {})]


def _describe_shape(node: dict, exact: bool) -> str:
    """One-line description of the value a schema node expects."""

    if not node or not exact:
        return "the value this tool's schema documents at that path"
    if node.get("type") == "array":
        item = _unwrap_union(node.get("items"))
        keys = _keys_of(item)
        if keys:
            return f"a list of objects with keys: {', '.join(keys)}"
        return f"a list of {item.get('type') or 'values'}"
    if node.get("enum"):
        return "one of: " + ", ".join(str(v) for v in node["enum"])
    keys = _keys_of(node)
    if keys:
        return f"an object with keys: {', '.join(keys)}"
    return str(node.get("type") or "value")


def _discovery_hint(field_name: str) -> str:
    tool = _ID_DISCOVERY_TOOL.get(field_name)
    if tool:
        return f" Call {tool} to get a real id."
    if field_name.endswith("_id"):
        return " Call the matching list_* tool to get a real id."
    return ""


def _short(value: Any, limit: int = 60) -> str:
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = repr(value)
    return text if len(text) <= limit else f"{text[:limit]}…(truncated)"


def format_tool_arg_errors(
    tool_name: str, schema: dict, wrong_args: Any, errors: list[dict]
) -> str:
    """
    Render pydantic errors as instructions the model can act on.

    Raw error dicts name only the rejected key; each line here also states
    what is legal at that path and which tool returns real ids. Runs on the
    failure path of every tool call, so it must never raise.
    """

    try:
        return _render_tool_arg_errors(tool_name, schema, wrong_args, errors)
    except Exception:
        logger.exception("[assistant] Could not render arg errors for '{}'", tool_name)
        return f"{tool_name} did NOT run — its arguments were rejected: {errors}"


def _render_tool_arg_errors(
    tool_name: str, schema: dict, wrong_args: Any, errors: list[dict]
) -> str:
    lines: list[str] = []
    id_rejected = False

    for err in errors[:_MAX_REPORTED_ERRORS]:
        loc = tuple(err.get("loc") or ())
        path = ".".join(str(p) for p in loc) or "(arguments)"
        leaf = str(loc[-1]) if loc else ""
        id_rejected = id_rejected or leaf.endswith("_id")
        err_type = err.get("type", "")

        if err_type == "missing":
            node, exact = _schema_at(schema, loc)
            lines.append(
                f"- {path}: required, but you did not send it. Send "
                f"{_describe_shape(node, exact)}.{_discovery_hint(leaf)}"
            )
        elif err_type in ("extra_forbidden", "unexpected_keyword_argument"):
            node, exact = _schema_at(schema, loc[:-1])
            keys = _keys_of(node) if exact else []
            allowed = (
                f"The only keys accepted here are: {', '.join(keys)}."
                if keys
                else "Use only the keys this tool's schema defines at that path."
            )
            lines.append(
                f"- {path}: '{leaf}' is not a key of this object. {allowed} "
                "Move the value under an accepted key, or drop it."
            )
        else:
            node, exact = _schema_at(schema, loc)
            lines.append(
                f"- {path}: {err.get('msg', err_type)} — you sent "
                f"{_short(err.get('input'))}, expected "
                f"{_describe_shape(node, exact)}.{_discovery_hint(leaf)}"
            )

    hidden = len(errors) - len(lines)
    if hidden > 0:
        lines.append(f"- ...and {hidden} more error(s); fix them the same way.")

    sent = (
        ", ".join(sorted(wrong_args))
        if isinstance(wrong_args, dict) and wrong_args
        else "(none)"
    )
    footer = (
        "Keys marked * are required. Send the whole corrected argument object "
        f"in a new {tool_name} call."
    )
    if id_rejected:
        footer += (
            " Never invent an id or send a placeholder such as 0 — take ids from "
            "a create_* result or a list_* tool result."
        )
    return (
        f"{tool_name} did NOT run — its arguments were rejected.\n"
        f"Keys you sent: {sent}.\n" + "\n".join(lines) + f"\n{footer}"
    )


# ---------------------------------------------------------------------------
# Lenient validator & fixer
# ---------------------------------------------------------------------------

_FIXER_PROMPT = """\
You repair tool-call JSON. You receive the target JSON schema, the object that \
failed validation, and the validation errors. Return ONLY a JSON object — no \
explanation, no markdown fences.

Rules:
1. Preserve every value the caller supplied. You may move a value to the \
correct key, rename a key, drop an unsupported key, or convert a value to the \
type the schema requires — nothing else.
2. Do not invent data. Fill in a required value only when it is already \
present elsewhere in the caller's object, or when the schema itself \
determines it (a default, a const, or a single-member enum). Never invent an \
identifier, and never satisfy a required field with a placeholder such as 0, \
1, "", "unknown" or a guessed name.
3. If a required value is genuinely absent and rule 2 does not supply it, do \
not guess. Return exactly \
{"__cannot_fix__": "<which values are missing and where they must come from>"}."""


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
# Invented resource ids
# ---------------------------------------------------------------------------

# Only ids listed here are checked, so a user's own ``*_id`` column is never flagged.
_ID_PRODUCERS: dict[str, str] = {
    "database_id": "list_builders",
    "application_id": "list_builders",
    "automation_id": "list_builders",
    "builder_id": "list_builders",
    "table_id": "list_tables",
    "field_id": "get_tables_schema",
    "view_id": "list_views",
    "page_id": "list_pages",
    "element_id": "list_elements",
    "data_source_id": "list_data_sources",
    "workflow_id": "list_workflows",
    "node_id": "list_nodes",
}


def _id_producer(key: str) -> str | None:
    """Longest-suffix match, so ``cover_field_id`` resolves like ``field_id``."""

    for name in sorted(_ID_PRODUCERS, key=len, reverse=True):
        if key.endswith(name):
            return _ID_PRODUCERS[name]
    return None


def _is_placeholder_id(value: Any) -> bool:
    """Every Baserow primary key is >= 1, so an ID <= 0 was invented."""

    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value <= 0
    if isinstance(value, str):
        text = value.strip()
        return bool(text) and text.lstrip("-").isdigit() and int(text) <= 0
    return False


def _find_placeholder_ids(node: Any, path: str = "") -> list[tuple[str, str, Any]]:
    """Return ``(json_path, producer_tool, value)`` for every invented resource
    ID in the raw tool arguments, at any nesting depth."""

    found: list[tuple[str, str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            producer = _id_producer(key)
            if producer is not None:
                if _is_placeholder_id(value):
                    found.append((child, producer, value))
                continue
            plural = _id_producer(key[:-1]) if key.endswith("s") else None
            if plural is not None and isinstance(value, list):
                found.extend(
                    (f"{child}[{i}]", plural, item)
                    for i, item in enumerate(value)
                    if _is_placeholder_id(item)
                )
                continue
            found.extend(_find_placeholder_ids(value, child))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(_find_placeholder_ids(item, f"{path}[{i}]"))
    return found


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
            # Re-cache on every re-issue so the fixer sees the schema the model saw.
            if tool.args_validator is not _LENIENT_VALIDATOR:
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
        placeholders = _find_placeholder_ids(tool_args)
        if placeholders:
            logger.warning(
                "[assistant] Tool '{}' called with placeholder IDs: {}",
                name,
                placeholders,
            )
            offenders = ", ".join(f"{p}={v!r}" for p, _, v in placeholders)
            producers = " / ".join(sorted({t for _, t, _ in placeholders}))
            return {
                "error": (
                    f"Not executed. Invented IDs: {offenders}. Baserow IDs start "
                    "at 1. Only send an ID you have read from a tool result or "
                    "from <ui_context>."
                ),
                "next_steps": (
                    f"Call {producers} to read the real ID (switch_mode first if "
                    f"it is not available in this mode), then call {name} again "
                    "with the same arguments and that ID."
                ),
            }
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
        report = format_tool_arg_errors(tool_name, schema, wrong_args, error_details)

        logger.warning(
            "[assistant] Tool '{}' args failed validation, attempting fix. Errors: {}",
            tool_name,
            error_details,
        )

        prompt = (
            f"Tool: {tool_name}\n\n"
            f"Schema:\n{json.dumps(schema, indent=2)}\n\n"
            f"Invalid input:\n{json.dumps(wrong_args, indent=2)}\n\n"
            f"Validation errors:\n{json.dumps(error_details, indent=2)}\n\n"
            f"What is wrong:\n{report}"
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
            raise ModelRetry(report) from exc

        if isinstance(fixed_args, dict) and "__cannot_fix__" in fixed_args:
            missing = fixed_args["__cannot_fix__"]
            logger.warning(
                "[assistant] Fixer could not repair args for tool '{}': {}",
                tool_name,
                missing,
            )
            raise ModelRetry(
                f"Tool '{tool_name}' was called without required information: "
                f"{missing}. Do not retry with a guessed or placeholder value — "
                f"obtain the real value first (list or fetch the resource, or "
                f"ask the user), then call the tool again."
            )

        # Re-validate with original schema
        original_validator = self._original_validators[tool_name]
        try:
            validated = original_validator.validate_python(fixed_args)
        except ValidationError as e2:
            retry_errors = e2.errors(include_url=False, include_context=False)
            logger.warning(
                "[assistant] Fixed args for tool '{}' still invalid: {}",
                tool_name,
                retry_errors,
            )
            raise ModelRetry(
                format_tool_arg_errors(tool_name, schema, fixed_args, retry_errors)
            ) from e2

        return validated


# ---------------------------------------------------------------------------
# Mode-aware toolset
# ---------------------------------------------------------------------------


def _build_mode_tool_map() -> dict[AgentMode, frozenset[str]]:
    """Build mode → tool-names mapping from actual function references.

    Derives names via ``f.__name__`` instead of hand-maintained string
    lists to eliminate typo risk.
    """

    from .automation.tools import TOOL_FUNCTIONS as AUTO_FN
    from .builder.tools import TOOL_FUNCTIONS as BUILDER_FN
    from .core.tools import create_builders, list_builders, switch_mode, update_builder
    from .database.tools import TOOL_FUNCTIONS as DB_FN
    from .navigation.tools import navigate
    from .search_user_docs.tools import search_user_docs

    n = frozenset  # alias for readability

    def names(*funcs):
        return n(f.__name__ for f in funcs)

    shared = names(
        navigate,
        switch_mode,
        list_builders,
        # Read-only database tools available in every mode
        *[f for f in DB_FN if f.__name__.startswith(("list_", "get_"))],
    )

    return {
        AgentMode.DATABASE: shared | names(*DB_FN, create_builders, update_builder),
        AgentMode.APPLICATION: shared
        | names(*BUILDER_FN, create_builders, update_builder),
        AgentMode.AUTOMATION: shared | names(*AUTO_FN, create_builders, update_builder),
        AgentMode.EXPLAIN: shared
        | names(
            *[f for f in BUILDER_FN if f.__name__.startswith("list_")],
            *[f for f in AUTO_FN if f.__name__.startswith("list_")],
            search_user_docs,
        ),
    }


_MODE_TOOL_MAP: dict[AgentMode, frozenset[str]] | None = None


def _get_mode_tool_map() -> dict[AgentMode, frozenset[str]]:
    global _MODE_TOOL_MAP
    if _MODE_TOOL_MAP is None:
        _MODE_TOOL_MAP = _build_mode_tool_map()
    return _MODE_TOOL_MAP


class ModeAwareToolset(AbstractToolset[AgentDepsT]):
    """
    Filters the inner toolset based on the current :class:`AgentMode`.

    Each domain mode (DATABASE, APPLICATION, AUTOMATION) exposes only its
    relevant tools plus shared read-only tools. EXPLAIN mode exposes
    read-only tools plus ``search_user_docs``.
    """

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
        all_tools = await self._inner.get_tools(ctx)
        allowed = _get_mode_tool_map()[self._deps.mode]
        return {k: v for k, v in all_tools.items() if k in allowed}

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        from baserow.core.exceptions import UserNotInWorkspace
        from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError

        try:
            return await self._inner.call_tool(name, tool_args, ctx, tool)
        except ToolInputError as exc:
            return {"error": str(exc)}
        except UserNotInWorkspace:
            return {
                "error": (
                    "One or more IDs reference a resource outside the current "
                    "workspace. Use the appropriate list_* tool to find "
                    "the correct IDs and retry."
                )
            }
        except Exception as exc:
            # Every Baserow lookup miss raises a plain `<Name>DoesNotExist`.
            if not type(exc).__name__.endswith("DoesNotExist"):
                raise
            logger.warning(
                "[assistant] Tool '{}' referenced a missing resource: {}: {}",
                name,
                type(exc).__name__,
                exc,
            )
            return {
                "error": (
                    f"{name} referenced something that does not exist or is not "
                    f"accessible: {exc}"
                ),
                "next_steps": (
                    "Every id and type value must come from a previous tool "
                    "result, never from a guess or a placeholder. Re-read it "
                    "from the latest list_*/get_*/create_* result, or call the "
                    f"matching list_*/get_* tool to look it up, then retry {name}."
                ),
            }


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

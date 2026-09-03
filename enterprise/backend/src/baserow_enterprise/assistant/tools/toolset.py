"""
Pydantic-ai toolset utilities for the assistant.

Contains schema helpers, lenient argument validation, and the
``InlineRefsToolset`` wrapper.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from loguru import logger
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.toolsets import AbstractToolset
from pydantic_ai.toolsets.abstract import AgentDepsT, ToolsetTool
from typing_extensions import Self

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

# Read-only tool that returns real values for a given id argument (suffix-matched).
_ID_PRODUCERS: dict[str, str] = {
    "database_id": "list_builders",
    "application_id": "list_builders",
    "automation_id": "list_builders",
    "builder_id": "list_builders",
    "table_id": "list_tables",
    "field_id": "get_tables_schema",
    "view_id": "list_views",
    "row_id": "list_rows",
    "page_id": "list_pages",
    "element_id": "list_elements",
    "data_source_id": "list_data_sources",
    "workflow_id": "list_workflows",
    "node_id": "list_nodes",
}

# row_id stays hint-only: data-source row ids may hold formulas or user data.
_PLACEHOLDER_EXEMPT_IDS = frozenset({"row_id"})


def _id_suffix(key: str) -> str | None:
    """Longest-suffix match, so ``cover_field_id`` resolves like ``field_id``."""

    for name in sorted(_ID_PRODUCERS, key=len, reverse=True):
        if key.endswith(name):
            return name
    return None


def _id_producer(key: str) -> str | None:
    suffix = _id_suffix(key)
    return _ID_PRODUCERS[suffix] if suffix else None


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

    A union branch tag in ``loc`` (``('parent_element', 'int')``) does not
    resolve, so callers must never present a partial result as the
    authoritative key set.

    :param schema: The ref-inlined parameter schema.
    :param loc: The pydantic error location path.
    :return: The deepest node reached and whether the whole path resolved.
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
    tool = _id_producer(field_name)
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

    :param tool_name: The tool whose arguments were rejected.
    :param schema: The ref-inlined parameter schema the model saw.
    :param wrong_args: The rejected arguments.
    :param errors: The pydantic error dicts.
    :return: A multi-line report the model can act on.
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


LENIENT_ARGS_VALIDATOR = _LenientValidator()


# ---------------------------------------------------------------------------
# Invented resource ids
# ---------------------------------------------------------------------------


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
    """
    Find invented resource IDs in raw tool arguments at any nesting depth.

    :param node: The argument value to scan.
    :param path: The JSON path accumulated so far.
    :return: ``(json_path, producer_tool, value)`` per invented resource ID.
    """

    found: list[tuple[str, str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            suffix = _id_suffix(key)
            if suffix is not None and suffix not in _PLACEHOLDER_EXEMPT_IDS:
                if _is_placeholder_id(value):
                    found.append((child, _ID_PRODUCERS[suffix], value))
                continue
            plural = _id_suffix(key[:-1]) if key.endswith("s") else None
            if (
                plural is not None
                and plural not in _PLACEHOLDER_EXEMPT_IDS
                and isinstance(value, list)
            ):
                found.extend(
                    (f"{child}[{i}]", _ID_PRODUCERS[plural], item)
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
        """
        Return the inner tools with inlined schemas and lenient validators.

        :param ctx: The agent run context.
        :return: The tools, with the original validators and schemas cached
            so call_tool can validate and repair arguments itself.
        """

        tools = await self._inner.get_tools(ctx)
        for name, tool in tools.items():
            # Inline $ref/$defs in the JSON schema
            tool.tool_def.parameters_json_schema = inline_refs(
                tool.tool_def.parameters_json_schema
            )
            # Re-cache on every re-issue so the fixer sees the schema the model saw.
            if tool.args_validator is not LENIENT_ARGS_VALIDATOR:
                self._original_validators[name] = tool.args_validator
                self._schemas[name] = tool.tool_def.parameters_json_schema
                tool.args_validator = LENIENT_ARGS_VALIDATOR
        return tools

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: Any,
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """
        Validate the arguments, fixing them if needed, then call the tool.

        :param name: The tool name.
        :param tool_args: The raw tool arguments.
        :param ctx: The agent run context.
        :param tool: The toolset tool being called.
        :return: The inner tool result, or an error dict when the arguments
            carried placeholder IDs.
        """

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
        output call.

        :param tool_name: The tool whose arguments failed validation.
        :param wrong_args: The rejected arguments.
        :param error: The validation error they produced.
        :return: The repaired arguments, validated against the original schema.
        :raises ModelRetry: When the fixer fails, declares the arguments
            unfixable, or its fix also fails validation, so pydantic-ai can
            handle the retry normally.
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

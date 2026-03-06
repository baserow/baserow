"""
Eval: verify every registered tool produces valid structured output.

For each tool in the assistant registry, we ask the LLM to generate
arguments via structured output (strict mode). This catches:

- Schema incompatibilities with the LLM provider (oneOf, missing properties, ...)
- JSON parsing / validation failures
- Tool argument coercion issues (Pydantic parse_and_validate_args)

Run with: pytest -m eval -k test_eval_tool_structured_output -v

Configuration (via environment variables):
- EVAL_LLM_MODEL: The model to use (default: "groq:openai/gpt-oss-120b")
- OPENAI_API_KEY / GROQ_API_KEY: Required depending on the model
"""

import copy
import json
from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import RunUsage

from baserow_enterprise.assistant.deps import AssistantDeps, ToolHelpers
from baserow_enterprise.assistant.tools.automation.tools import automation_toolset
from baserow_enterprise.assistant.tools.core.tools import core_toolset
from baserow_enterprise.assistant.tools.database.tools import database_toolset
from baserow_enterprise.assistant.tools.navigation.tools import navigation_toolset

# ---------------------------------------------------------------------------
# Eval prompts — templates for per-tool structured output tests
# ---------------------------------------------------------------------------

TOOL_INSTRUCTION_TEMPLATE = (
    "You are a tool executor. Produce valid JSON arguments for the "
    "'{tool_name}' tool.\n\n"
    "Tool description: {tool_description}\n\n"
    "Schema: {schema_json}"
)

PROMPT_ALL_TOOLS_STRUCTURED_OUTPUT = (
    "Generate example arguments for the '{tool_name}' tool. "
    "Use realistic placeholder values (e.g. id=1, name='Example', "
    "page_id=1, table_id=1, application_id=1). "
    "Fill in ALL required fields with sensible values. "
    "For lists of union/discriminated types (anyOf), include exactly "
    "ONE item per variant type so each type is tested. "
    "For regular lists (non-union), include exactly one item. "
    "For optional fields, use null unless the field is essential. "
    "Return ONLY the JSON object, no markdown or explanation."
)

PROMPT_ROW_TOOLS_STRUCTURED_OUTPUT = (
    "Generate example arguments for the '{tool_name}' tool. "
    "Use realistic placeholder values. "
    "Fill in ALL required fields with sensible values. "
    "For lists of union/discriminated types (anyOf), include exactly "
    "ONE item per variant type so each type is tested. "
    "For regular lists (non-union), include exactly one item. "
    "For optional fields, use null unless the field is essential. "
    "Return ONLY the JSON object, no markdown or explanation."
)


_tool_helpers = ToolHelpers(lambda x: None, lambda x: None)


def _prepare_strict_schema(schema: dict) -> dict:
    """
    Transform a JSON schema for OpenAI/Groq strict output mode.
    Same implementation as in test_assistant_builder_tool_schemas.py.
    """

    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", schema.pop("definitions", {}))

    def _resolve(node):
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        if "$ref" in node:
            ref_name = node["$ref"].split("/")[-1]
            if ref_name in defs:
                return _resolve(copy.deepcopy(defs[ref_name]))
            return node

        resolved = {}
        for key, val in node.items():
            resolved[key] = _resolve(val)

        if "oneOf" in resolved:
            resolved["anyOf"] = resolved.pop("oneOf")

        for forbidden in (
            "discriminator",
            "default",
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "minLength",
            "maxLength",
            "minItems",
            "maxItems",
        ):
            resolved.pop(forbidden, None)

        if resolved.get("type") == "object" and "properties" in resolved:
            resolved["required"] = list(resolved["properties"].keys())
            resolved["additionalProperties"] = False

        return resolved

    result = _resolve(schema)

    if isinstance(result, dict):
        if result.get("type") != "object" and "properties" in result:
            result["type"] = "object"
        if result.get("type") == "object":
            if "properties" in result:
                result["required"] = list(result["properties"].keys())
            result["additionalProperties"] = False

    return result


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_all_tools_structured_output(data_fixture, eval_model):
    """
    Every tool's schema must work with the LLM's structured output endpoint.

    For each tool we:
    1. Build the strict-mode schema
    2. Call the LLM with response_format/json_schema strict mode
    3. Verify the response is valid JSON
    """
    # --- Setup: create minimal environment ---
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="TestTable")
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    # --- Collect all tools from the toolsets ---
    import asyncio

    from pydantic_ai.toolsets import CombinedToolset

    combined = CombinedToolset(
        [
            navigation_toolset,
            core_toolset,
            database_toolset,
            automation_toolset,
        ]
    )
    ctx = RunContext(
        deps=AssistantDeps(
            user=user,
            workspace=workspace,
            tool_helpers=_tool_helpers,
        ),
        model=MagicMock(),
        usage=RunUsage(),
    )
    all_toolset_tools = asyncio.run(combined.get_tools(ctx))

    model = eval_model
    failures: list[str] = []

    for tool_name, toolset_tool in sorted(all_toolset_tools.items()):
        raw_schema = toolset_tool.tool_def.parameters_json_schema
        strict_schema = _prepare_strict_schema(raw_schema)

        # Use a simple agent to generate example arguments
        tool_description = toolset_tool.tool_def.description
        generator_agent = Agent(
            output_type=str,
            instructions=TOOL_INSTRUCTION_TEMPLATE.format(
                tool_name=tool_name,
                tool_description=tool_description,
                schema_json=json.dumps(strict_schema),
            ),
        )

        try:
            result = generator_agent.run_sync(
                user_prompt=PROMPT_ALL_TOOLS_STRUCTURED_OUTPUT.format(
                    tool_name=tool_name
                ),
                model=model,
            )
            content = result.output
        except Exception as e:
            failures.append(f"[{tool_name}] Agent error: {e}")
            continue

        if not content:
            failures.append(f"[{tool_name}] Empty response")
            continue

        # Try to parse the response as JSON
        try:
            # Strip markdown code fences if present
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                if clean.endswith("```"):
                    clean = clean[:-3]
            parsed = json.loads(clean)
        except json.JSONDecodeError as e:
            failures.append(
                f"[{tool_name}] Invalid JSON: {e} -- response: {content[:200]}"
            )
            continue

        if not isinstance(parsed, dict):
            failures.append(f"[{tool_name}] Expected dict, got {type(parsed).__name__}")
            continue

        print(f"  OK: {tool_name}")

    assert not failures, (
        f"{len(failures)} tool(s) failed structured output:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_row_tools_structured_output(data_fixture, eval_model):
    """
    Row tools (create/update/delete_rows_in_table_X) are dynamically created
    with custom schemas built from table fields. This test creates a
    table with many field types and verifies each row tool's schema works with
    the LLM's structured output endpoint.
    """

    from baserow_enterprise.assistant.tools.database.tools import _build_row_tools

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="RichTable")

    # Create diverse field types
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_long_text_field(table=table, name="Description")
    data_fixture.create_number_field(table=table, name="Price")
    data_fixture.create_boolean_field(table=table, name="Active")
    data_fixture.create_date_field(table=table, name="Created")
    select_field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=select_field, value="Draft", order=0)
    data_fixture.create_select_option(field=select_field, value="Published", order=1)
    multi_field = data_fixture.create_multiple_select_field(table=table, name="Tags")
    data_fixture.create_select_option(field=multi_field, value="Important", order=0)
    data_fixture.create_select_option(field=multi_field, value="Urgent", order=1)

    tool_helpers = _tool_helpers
    row_tools = _build_row_tools(user, workspace, tool_helpers, table)

    model = eval_model
    failures: list[str] = []

    for _tool_key, tool in row_tools.items():
        raw_schema = tool.function_schema.json_schema
        strict_schema = _prepare_strict_schema(raw_schema)

        generator_agent = Agent(
            output_type=str,
            instructions=TOOL_INSTRUCTION_TEMPLATE.format(
                tool_name=tool.name,
                tool_description=tool.description,
                schema_json=json.dumps(strict_schema),
            ),
        )

        try:
            result = generator_agent.run_sync(
                user_prompt=PROMPT_ROW_TOOLS_STRUCTURED_OUTPUT.format(
                    tool_name=tool.name
                ),
                model=model,
            )
            content = result.output
        except Exception as e:
            failures.append(f"[{tool.name}] Agent error: {e}")
            continue

        if not content:
            failures.append(f"[{tool.name}] Empty response")
            continue

        try:
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                if clean.endswith("```"):
                    clean = clean[:-3]
            parsed = json.loads(clean)
        except json.JSONDecodeError as e:
            failures.append(
                f"[{tool.name}] Invalid JSON: {e} -- response: {content[:200]}"
            )
            continue

        if not isinstance(parsed, dict):
            failures.append(f"[{tool.name}] Expected dict, got {type(parsed).__name__}")
            continue

        print(f"  OK: {tool.name}")

    assert not failures, (
        f"{len(failures)} row tool(s) failed structured output:\n"
        + "\n".join(f"  - {f}" for f in failures)
    )

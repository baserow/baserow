import re
from collections.abc import Sequence
from typing import Any, Callable

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.toolsets import FunctionToolset
from pydantic_ai.usage import UsageLimits

from baserow.contrib.database.api.formula.serializers import TypeFormulaResultSerializer
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import FormulaField
from baserow.core.models import Workspace
from baserow_premium.prompts import get_formula_docs

from . import helpers
from .prompts import (
    FORMULA_AGENT_INSTRUCTIONS,
    SAMPLE_ROW_AGENT_INSTRUCTIONS,
    format_formula_fixer_prompt,
    format_sample_rows_prompt,
)

# ---------------------------------------------------------------------------
# Formula generation agent
# ---------------------------------------------------------------------------


class FormulaGenerationResult(PydanticBaseModel):
    """Output model for the formula generation agent."""

    table_id: int = Field(
        description=(
            "The ID of the table the formula field belongs to. It must be the "
            "`id` of one of the tables in the schema given in the prompt: the "
            "table that holds the fields the formula reads directly (for a "
            "lookup, the table holding the link field, not the linked table). "
            "Never invent an ID, and never use 0 or null."
        )
    )
    field_name: str = Field(
        description="The name of the formula field to be created. For a new field, it must be unique in the table."
    )
    formula: str = Field(
        description="The generated formula. Must be a valid Baserow formula."
    )
    formula_type: str = Field(
        description=(
            "The type of the generated formula. Must be one of: text, long_text, "
            "number, boolean, date, link_row, single_select, multiple_select, duration, array."
        )
    )
    is_formula_valid: bool = Field(
        description="Whether the generated formula is valid or not."
    )
    error_message: str = Field(
        default="",
        description="If the formula is not valid, an error message explaining why.",
    )


# Without an explicit budget pydantic-ai allows a single attempt, so the first
# validator rejection exhausts it ("Exceeded maximum output retries (1)").
FORMULA_AGENT_RETRIES = 3

formula_generation_agent: Agent[None, FormulaGenerationResult] = Agent(
    output_type=FormulaGenerationResult,
    instructions=FORMULA_AGENT_INSTRUCTIONS,
    name="formula_generation_agent",
    retries=FORMULA_AGENT_RETRIES,
)

GET_FORMULA_TYPE_TOOL_NAME = "get_formula_type"

# One rejected candidate is not evidence that the language cannot express a request.
FORMULA_MIN_ATTEMPTS_BEFORE_IMPOSSIBLE = 2


def _normalize_formula(formula: str) -> str:
    return " ".join(formula.split())


def _formula_attempts(messages: Sequence[ModelMessage]) -> tuple[set[str], set[str]]:
    """
    Split the formulas passed to get_formula_type during a run into accepted and
    rejected.

    A rejection reaches the model as a RetryPromptPart and an acceptance as a
    ToolReturnPart, so the two sets are the run's own record of what was checked.
    """

    attempted: dict[str, str] = {}
    accepted_ids: set[str] = set()
    rejected_ids: set[str] = set()
    for message in messages:
        for part in message.parts:
            if getattr(part, "tool_name", None) != GET_FORMULA_TYPE_TOOL_NAME:
                continue
            if isinstance(part, ToolCallPart):
                formula = part.args_as_dict().get("formula")
                if isinstance(formula, str) and formula.strip():
                    attempted[part.tool_call_id] = _normalize_formula(formula)
            elif isinstance(part, RetryPromptPart):
                rejected_ids.add(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                accepted_ids.add(part.tool_call_id)

    accepted = {f for call_id, f in attempted.items() if call_id in accepted_ids}
    rejected = {f for call_id, f in attempted.items() if call_id in rejected_ids}
    return accepted, rejected


@formula_generation_agent.output_validator
def _verdict_must_be_backed_by_validation(
    ctx: RunContext[None], output: FormulaGenerationResult
) -> FormulaGenerationResult:
    """
    Send back any verdict get_formula_type did not actually produce.

    Both directions are enforced: a valid verdict must name a formula the tool
    accepted, and an impossible verdict must follow several materially different
    candidates the tool rejected. A verdict with no tool call behind it is a guess.
    """

    accepted, rejected = _formula_attempts(ctx.messages)
    if output.is_formula_valid:
        if _normalize_formula(output.formula) not in accepted:
            raise ModelRetry(
                f"{output.formula!r} was never accepted by "
                f"{GET_FORMULA_TYPE_TOOL_NAME} in this run, so its validity is "
                f"unverified. Call {GET_FORMULA_TYPE_TOOL_NAME} on it and return "
                "the exact formula that passed."
            )
    elif len(accepted | rejected) < FORMULA_MIN_ATTEMPTS_BEFORE_IMPOSSIBLE:
        # Naming the conversions here too: this branch fires when the model gave up
        # without validating, so it never saw the compiler's type-mismatch hint.
        conversions = "; ".join(
            f"to {target} use {how}"
            for target, how in sorted(_CONVERSION_TO_TARGET_TYPE.items())
        )
        raise ModelRetry(
            "A single attempt is not evidence that the request cannot be "
            f"expressed. Validate at least {FORMULA_MIN_ATTEMPTS_BEFORE_IMPOSSIBLE} "
            f"materially different candidates with {GET_FORMULA_TYPE_TOOL_NAME} "
            "before giving up: vary the approach, and where a direct expression is "
            "rejected try one that converts the argument types first — any field "
            f"type can be converted ({conversions}). Justify failure only by "
            f"quoting the error {GET_FORMULA_TYPE_TOOL_NAME} returned, never by "
            "asserting from memory what the formula language does or does not "
            "support."
        )
    return output


# Keyed by the type name the compiler prints as the usable type for an argument.
_CONVERSION_TO_TARGET_TYPE: dict[str, str] = {
    "text": "totext(x) for a single value, or join(x, ', ') for a list",
    "char": "totext(x)",
    "url": "tourl(totext(x))",
    "link": "link(totext(x))",
    "number": "tonumber(totext(x)), or count(x) to count a list",
    "date": "todate(totext(x), 'YYYY-MM-DD')",
    "duration": "toduration(tonumber(totext(x))) reading the number as seconds",
    "boolean": "a comparison such as totext(x) != '' — there is no cast to boolean",
}

_USABLE_TYPES = re.compile(
    r"the only usable types? for this argument (?:is|are) ([a-z_]+(?:,[a-z_]+)*)"
)


def _type_mismatch_hint(error: str) -> str:
    """
    Explains that a rejected argument type is a conversion problem.

    Without this the compiler's wording reads as the language not supporting the
    operation at all, and the agent abandons a formula that a wrapped argument
    would have made valid.
    """

    if "was of type" not in error:
        return ""

    if "there are no possible types usable here" in error:
        return (
            " That argument slot accepts no type at all, so no conversion will "
            "fix it: restructure the expression instead of retrying conversions."
        )

    targets = {t for match in _USABLE_TYPES.findall(error) for t in match.split(",")}
    repairs = [
        f"to {target} use {_CONVERSION_TO_TARGET_TYPE[target]}"
        for target in sorted(targets)
        if target in _CONVERSION_TO_TARGET_TYPE
    ]
    hint = (
        " This is an argument type mismatch, not an unsupported operation. Any "
        "field type can be converted, so wrap the argument the error names in a "
        "conversion function and validate again rather than abandoning the formula."
    )
    if repairs:
        hint += " Convert " + "; ".join(repairs) + "."
    return hint


def get_formula_type_tool(
    user: AbstractUser, workspace: Workspace
) -> Callable[[str], str]:
    """
    Returns a function that validates a formula and returns its type.
    """

    def get_formula_type(table_id: int, field_name: str, formula: str) -> str:
        """
        Returns the type of a formula. Raises an exception if the formula
        is not valid.
        **ALWAYS** call this to validate a formula is valid before returning it.
        """

        nonlocal user, workspace

        table = helpers.filter_tables(user, workspace).filter(id=table_id).first()
        if not table:
            valid_ids = list(
                helpers.filter_tables(user, workspace).values_list("id", flat=True)
            )
            raise ModelRetry(
                f"Table with ID {table_id} not found in workspace. "
                f"Valid table IDs: {valid_ids}"
            )

        # Every rejection must reach the model as a ModelRetry: pydantic-ai turns
        # only that into a retry prompt, so any other exception aborts the user's
        # whole turn instead of letting the agent correct the formula.
        field = FormulaField(formula=formula, table=table, name=field_name, order=0)
        try:
            field.recalculate_internal_fields(raise_if_invalid=True)
            result = TypeFormulaResultSerializer(field).data
            error = result["error"]
        except Exception as exc:
            error = str(exc)

        if error:
            field_names = list(
                FieldHandler()
                .get_base_fields_queryset()
                .filter(table=table)
                .values_list("name", flat=True)
            )
            raise ModelRetry(
                f"Invalid formula: {error}.{_type_mismatch_hint(error)} "
                f"Available fields in table '{table.name}': {', '.join(field_names)}"
            )

        return result["formula_type"]

    return get_formula_type


def make_formula_fixer(
    user: AbstractUser, workspace: Workspace, tool_helpers
) -> Callable:
    """
    Returns a callback that tries to auto-generate a valid formula when the
    LLM-provided one is invalid.  Uses the ``formula_generation_agent``.
    """

    def fix_formula(table, field_name: str, original_formula: str) -> str | None:
        database_tables = helpers.filter_tables(user, workspace).filter(
            database_id=table.database_id
        )
        schema = [
            t.model_dump() for t in helpers.get_tables_schema(database_tables, True)
        ]
        tool_helpers.update_status(
            _("Fixing formula for %(name)s...") % {"name": field_name}
        )

        formula_type_tool = Tool(get_formula_type_tool(user, workspace))
        formula_toolset = FunctionToolset(
            [formula_type_tool], max_retries=FORMULA_AGENT_RETRIES
        )
        prompt = format_formula_fixer_prompt(
            field_name, original_formula, schema, get_formula_docs()
        )
        from baserow_enterprise.assistant.model_profiles import (
            UTILITY,
            get_model_settings,
            get_model_string,
        )

        model = get_model_string()
        result = formula_generation_agent.run_sync(
            prompt,
            model=model,
            model_settings=get_model_settings(model, UTILITY),
            toolsets=[formula_toolset],
            usage_limits=UsageLimits(request_limit=20),
        )
        if result.output.is_formula_valid:
            return result.output.formula
        return None

    return fix_formula


# ---------------------------------------------------------------------------
# Sample-row generation agent
# ---------------------------------------------------------------------------


def _find_reverse_link_row_fields(tables: list) -> dict[int, set[int]]:
    """
    Identify auto-created reverse link_row fields across a set of tables.

    When a link_row field is created between two tables, Baserow auto-creates
    a reverse field on the linked table.  For sample-row generation we only
    want the "owning" side (the explicitly created field) so the agent doesn't
    face circular dependencies.

    For any bidirectional pair the field with the **higher** ID is the
    auto-created reverse (it's created immediately after the explicit one).

    :returns: ``{table_id: {field_id, ...}}`` of reverse field IDs to exclude.
    """

    from baserow.contrib.database.fields.models import LinkRowField

    table_ids = {t.id for t in tables}
    link_fields = LinkRowField.objects.filter(
        table_id__in=table_ids, link_row_table_id__in=table_ids
    ).select_related("link_row_related_field")

    reverse_ids: dict[int, set[int]] = {}
    seen_pairs: set[tuple[int, int]] = set()

    for lf in link_fields:
        related = lf.link_row_related_field
        if related is None:
            continue
        pair = (min(lf.id, related.id), max(lf.id, related.id))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        # The field with the higher ID is the auto-created reverse.
        reverse = lf if lf.id > related.id else related
        reverse_ids.setdefault(reverse.table_id, set()).add(reverse.id)

    return reverse_ids


def generate_sample_rows(
    user: AbstractUser,
    workspace: Workspace,
    tool_helpers,
    created_tables: list,
    data_brief: str | None = None,
) -> dict[int, list[Any]]:
    """
    Use an agent with ``create_rows`` tools to generate and insert
    realistic sample rows for newly created tables.

    Instead of building one giant structured-output schema for all tables,
    this gives the agent a ``create_rows_in_table_<id>`` tool per table.
    The agent decides the insertion order itself — it naturally creates
    rows in linked-to tables first, sees the returned row IDs, and uses
    them in link_row fields of dependent tables.
    """

    from baserow_enterprise.assistant.model_profiles import (
        SAMPLE,
        get_model_settings,
        get_model_string,
    )

    from .tools import _build_row_tools

    tool_helpers.update_status(_("Generating example rows for these new tables..."))

    # Build a create_rows tool for every table in the database (not just
    # the newly created ones) so link_row fields can reference rows in
    # pre-existing tables too.
    database = created_tables[0].database
    all_db_tables = list(database.table_set.all())

    # Identify reverse (auto-created) link_row fields to exclude from the
    # create schema.  When a link_row is created between two tables in the
    # same batch, Baserow auto-creates a reverse field.  Including both
    # sides creates a circular dependency the sample-row agent cannot
    # resolve.  For any bidirectional pair, the field with the higher ID
    # is the auto-created reverse — we exclude it.
    reverse_field_ids = _find_reverse_link_row_fields(all_db_tables)

    create_tools = []
    for table in all_db_tables:
        # Exclude reverse link_row fields for this table
        exclude = reverse_field_ids.get(table.id)
        field_ids = None
        if exclude:
            all_field_ids = [
                fo["field"].id for fo in table.get_model().get_field_objects()
            ]
            field_ids = [fid for fid in all_field_ids if fid not in exclude]
        row_tools = _build_row_tools(
            user, workspace, tool_helpers, table, field_ids=field_ids
        )
        create_tools.append(row_tools["create"])

    # Build a description of each table so the agent knows the schemas.
    schemas = helpers.get_tables_schema(created_tables, full_schema=True)
    table_info = "\n".join(f"- {schema.model_dump()}" for schema in schemas)

    model = get_model_string()
    sample_row_agent = Agent(
        output_type=str,
        instructions=SAMPLE_ROW_AGENT_INSTRUCTIONS,
        tools=create_tools,
        name="sample_row_agent",
    )
    sample_row_agent.run_sync(
        format_sample_rows_prompt(table_info, data_brief=data_brief),
        model=model,
        model_settings=get_model_settings(model, SAMPLE),
        usage_limits=UsageLimits(request_limit=len(all_db_tables) * 3 + 2),
    )

    # Collect the rows that were actually inserted.
    rows_created: dict[int, list] = {}
    for table in created_tables:
        table_model = table.get_model()
        rows = list(table_model.objects.all())
        if rows:
            rows_created[table.id] = rows

    return rows_created

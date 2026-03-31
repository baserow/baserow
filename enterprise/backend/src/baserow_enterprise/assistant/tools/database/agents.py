from typing import Any, Callable

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field
from pydantic_ai import Agent, Tool
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
            "The ID of the table the formula is intended for. "
            "Should be the same as current_table_id, unless the formula can "
            "only be created in a different table."
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


formula_generation_agent: Agent[None, FormulaGenerationResult] = Agent(
    output_type=FormulaGenerationResult,
    instructions=FORMULA_AGENT_INSTRUCTIONS,
    name="formula_generation_agent",
)


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
            raise ValueError(f"Table with ID {table_id} not found in workspace.")

        field = FormulaField(formula=formula, table=table, name=field_name, order=0)
        field.recalculate_internal_fields(raise_if_invalid=True)

        result = TypeFormulaResultSerializer(field).data
        if result["error"]:
            field_names = list(
                FieldHandler()
                .get_base_fields_queryset()
                .filter(table=table)
                .values_list("name", flat=True)
            )
            raise TypeError(
                f"Invalid formula: {result['error']}. "
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
        formula_toolset = FunctionToolset([formula_type_tool])
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

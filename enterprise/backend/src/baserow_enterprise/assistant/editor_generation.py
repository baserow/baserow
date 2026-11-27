import json
from typing import Literal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import Agent, ModelRetry, PromptedOutput, TextOutput
from pydantic_ai.exceptions import AgentRunError

from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.operations import CreateTableDatabaseTableOperationType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.tools.fields import OptionColor
from baserow.contrib.database.tools.tables import (
    TableItemCreate,
    create_tables_in_database,
    get_database,
    get_table,
    get_tables_schema,
)
from baserow.contrib.database.tools.view_config import ViewSortItem, set_view_sorts
from baserow.contrib.database.tools.views import (
    ViewFilterItemCreate,
    ViewItemCreate,
    create_view_filter,
    create_views,
    get_view,
    resolve_view_filter,
)
from baserow.contrib.database.views.actions import (
    DeleteViewFilterActionType,
    UpdateViewActionType,
    UpdateViewFilterActionType,
)
from baserow.contrib.database.views.exceptions import (
    ViewFilterNotSupported,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.operations import (
    CreateViewFilterOperationType,
    CreateViewOperationType,
    ListViewFilterOperationType,
)
from baserow.core.formula.literals import wrap_static_string
from baserow.core.generative_ai.lifecycle import run_agent_sync_with_model
from baserow.core.handler import CoreHandler
from baserow.core.operations import CreateApplicationsWorkspaceOperationType
from baserow.core.tools.applications import ApplicationName, create_application
from baserow.core.tools.errors import ToolInputError
from baserow.core.tools.types import BaseModel
from baserow_enterprise.assistant.exceptions import EditorGenerationFailed
from baserow_enterprise.assistant.model_profiles import UTILITY
from baserow_enterprise.assistant.tools.database.agents import get_formula_type_tool
from baserow_premium.fields.visitors import get_ai_prompt_error
from baserow_premium.prompts import get_formula_docs


class InstructionDraft(BaseModel):
    instructions: str = Field(min_length=1, max_length=100000)


class FilterEdit(BaseModel):
    filter_id: int
    condition: ViewFilterItemCreate


class FilterChanges(BaseModel):
    operator: Literal["AND", "OR"] | None = Field(
        default=None, description="Change the top-level operator only when requested."
    )
    add: list[ViewFilterItemCreate] = Field(default_factory=list)
    update: list[FilterEdit] = Field(default_factory=list)
    remove: list[int] = Field(default_factory=list)
    summary: str


class NewView(BaseModel):
    view: ViewItemCreate | None = Field(
        description="The new view settings, or null if the request cannot be fulfilled."
    )
    filters: list[ViewFilterItemCreate] = Field(
        description="Every requested row condition. An empty list creates an unfiltered view."
    )
    operator: Literal["AND", "OR"] = "AND"
    sorts: list[ViewSortItem] = Field(
        description="Every requested sort, most important first. An empty list creates an unsorted view."
    )
    reason: str = Field(
        default="", description="Explain an unsupported request when view is null."
    )


FILTER_FORMAT = (
    "Each condition has field_id, type, operator, and value. For example, a text "
    'field with id 12 uses {"field_id": 12, "type": "text", "operator": "equal", '
    '"value": "In review"}. Use the real field IDs and field types from the supplied '
    "schema, including primary_field. For a formula use its scalar result type "
    "(formula_type), using text for char and url. Keep the formula field's own ID. "
    "The comparison belongs in operator. "
    "For a select field use option labels, and for date filters specify mode."
)


instructions_agent = Agent(
    name="draft_agent_instructions",
    output_type=InstructionDraft,
    instructions="Write the Agent's instructions in the user's language. Revise the "
    "current draft as requested. Preserve its other requirements. Return the actual "
    "instructions. Do not promise access to tools or data or change settings.",
)
filters_agent = Agent(
    name="edit_view_filters",
    output_type=FilterChanges,
    retries=3,
    instructions="Edit only the requested conditions of this database view. Added "
    "conditions go at the root. Reuse an existing blank condition for the requested "
    "field. Updates keep their group. For an unsupported request "
    "return no changes. Explain the result briefly in the supplied response_language. "
    + FILTER_FORMAT,
)
view_agent = Agent(
    name="create_database_view",
    output_type=NewView,
    retries=3,
    instructions="Design one database view on the supplied table. Include the "
    "filters and sorts requested. Use a unique name. Create a non-public view. "
    "If the request cannot be represented, return a null view and explain why. "
    "Put every filter in the top-level filters array and every sort in the top-level "
    "sorts array. These arrays are what Baserow actually applies. For a condition "
    "and a sort, return e.g. "
    '{"view":{"name":"Review","type":"grid"},"filters":[{"field_id":12,"type":"text",'
    '"operator":"equal","value":"In review"}],"sorts":[{"field_id":10,"order":"ASC"}]}. '
    + FILTER_FORMAT,
)


class DatabaseDesign(BaseModel):
    name: ApplicationName
    tables: list[TableItemCreate] = Field(min_length=1)


class AIFieldPromptDraft(BaseModel):
    parts: list[str | int] = Field(
        min_length=1,
        description="Ordered literal text strings and numeric field IDs to interpolate.",
    )


class RowColorRule(BaseModel):
    color: OptionColor
    operator: Literal["AND", "OR"] = "AND"
    filters: list[ViewFilterItemCreate]


TABLE_DESIGN_FORMAT = (
    "Use primary_field_name for the text primary field and omit it from fields. "
    "List only the options relevant to each field type. For example, a relationship "
    'is {"name":"Customer","type":"link_row","linked_table":"Customers"}. '
    "Use the exact table name and define the link on one side only. "
    'A single_select uses options like [{"value":"Open"},{"value":"Closed"}]. '
    "In formulas reference columns by name, e.g. field('Quantity') * field('Price')."
)


table_agent = Agent(
    name="design_table",
    output_type=PromptedOutput(TableItemCreate),
    retries=3,
    instructions="Design one new Baserow table for the request. Use the supplied name if set. "
    "Give it typed columns. Existing table names are available for links. "
    + TABLE_DESIGN_FORMAT,
)
database_agent = Agent(
    name="design_database",
    output_type=PromptedOutput(DatabaseDesign),
    retries=3,
    instructions="Design a new database with named tables and typed columns for the request. "
    "Use the supplied database name if set. Include only the tables needed. "
    + TABLE_DESIGN_FORMAT,
)
ai_prompt_agent = Agent(
    name="draft_ai_field_prompt",
    output_type=AIFieldPromptDraft,
    retries=3,
    instructions="Write the prompt an AI field will run for EACH row, in the user's language. "
    "Use the requested output type. Revise the current prompt when asked. "
    "Interleave instruction text with numeric IDs from the supplied fields to insert row values. "
    "Keep spacing around field values. Return plain text in the string parts.",
)
row_color_agent = Agent(
    name="add_row_color",
    output_type=RowColorRule,
    retries=3,
    instructions="Design one new conditional row color rule. Only return an empty filters list "
    "if the user explicitly requests a color for every row. " + FILTER_FORMAT,
)


def _generate(agent, profile, prompt, **context):
    return run_agent_sync_with_model(
        agent,
        json.dumps({"request": prompt, **context}, ensure_ascii=False),
        model=profile.create_model(),
        model_settings=profile.get_settings(UTILITY),
        timeout_seconds=90,
    ).output


def _result(summary="", changed=False, **data):
    return {"summary": summary, "changed": changed, "result": data}


def _schema(ctx, table_id):
    table = get_table(ctx, table_id, ListFieldsOperationType.type)
    return [item.model_dump(mode="json") for item in get_tables_schema([table], True)]


def _generate_formula(ctx, prompt, parameters, profile):
    table_id = parameters["table_id"]
    field_name = parameters["field_name"]
    validate = get_formula_type_tool(ctx.user, ctx.workspace)

    async def validated_formula(formula: str) -> str:
        formula = formula.strip()
        await sync_to_async(validate)(table_id, field_name, formula)
        return formula

    agent = Agent(
        name="draft_database_formula",
        output_type=TextOutput(validated_formula),
        retries=3,
        instructions="Write the Baserow formula requested for the open field. "
        "Use the current formula when the request revises it. Return only the "
        "complete replacement expression, without Markdown or explanation. Use "
        "the supplied field names, formula result types and function reference. "
        "For natural-language text searches, ignore case unless requested. "
        "If the compiler rejects the expression, use its feedback to correct it.",
    )
    formula = _generate(
        agent,
        profile,
        prompt,
        table=_schema(ctx, table_id),
        field_name=field_name,
        current_formula=parameters["current"],
        formula_reference=get_formula_docs(),
    )
    return _result(formula=formula)


def _create_planned_tables(ctx, database, tables):
    creation = create_tables_in_database(ctx, database, tables)
    if (
        len(creation.created_tables) != len(tables)
        or creation.errors
        or creation.formula_errors
        or creation.permission_denied
    ):
        raise EditorGenerationFailed()
    return creation.created_tables[0]


def _create_table(ctx, prompt, parameters, profile):
    database = get_database(ctx, parameters["database_id"])
    CoreHandler().check_permissions(
        ctx.user,
        CreateTableDatabaseTableOperationType.type,
        workspace=ctx.workspace,
        context=database,
    )
    existing = (
        TableHandler()
        .list_workspace_tables(ctx.user, ctx.workspace)
        .filter(database=database)
    )
    name = parameters["name"]
    plan = _generate(
        table_agent,
        profile,
        prompt,
        name=name,
        existing_tables=list(existing.values_list("name", flat=True)),
    )
    with transaction.atomic():
        table = _create_planned_tables(
            ctx, database, [plan.model_copy(update={"name": name}) if name else plan]
        )
    return _result(
        _("Created table “%(name)s”.") % {"name": table.name},
        changed=True,
        database_id=database.id,
        table_id=table.id,
    )


def _create_database(ctx, prompt, parameters, profile):
    CoreHandler().check_permissions(
        ctx.user,
        CreateApplicationsWorkspaceOperationType.type,
        workspace=ctx.workspace,
        context=ctx.workspace,
    )
    name = parameters["name"]
    design = _generate(database_agent, profile, prompt, name=name)
    with transaction.atomic():
        database = create_application(ctx, "database", name or design.name).specific
        table = _create_planned_tables(ctx, database, design.tables)
    return _result(
        _("Created database “%(name)s”.") % {"name": database.name},
        changed=True,
        database_id=database.id,
        table_id=table.id,
    )


def _ai_field_prompt(ctx, prompt, parameters, profile):
    table = get_table(ctx, parameters["table_id"], ListFieldsOperationType.type)
    fields = dict(
        table.field_set.exclude(id=parameters.get("field_id")).values_list("id", "name")
    )
    draft = _generate(
        ai_prompt_agent,
        profile,
        prompt,
        fields=fields,
        current=parameters["current"],
        output_type=parameters["output_type"],
        current_mode=parameters["mode"],
    )
    parts = []
    for value in draft.parts:
        if isinstance(value, int):
            if value not in fields:
                raise EditorGenerationFailed()
            parts.append(f"get('fields.field_{value}')")
        elif value:
            parts.append(wrap_static_string(value))
    if not parts or not any(isinstance(v, str) and v.strip() for v in draft.parts):
        raise EditorGenerationFailed()
    expression = parts[0] if len(parts) == 1 else f"concat({', '.join(parts)})"
    if get_ai_prompt_error(expression, table.id):
        raise EditorGenerationFailed()
    return _result(ai_prompt=expression)


def _row_color(ctx, prompt, view_id, profile):
    view = get_view(ctx, view_id)
    rule = _generate(
        row_color_agent, profile, prompt, table=_schema(ctx, view.table_id)
    )
    fields = {f.id: f for f in view.table.field_set.all()}
    filters = []
    for condition in rule.filters:
        field, op, value = resolve_view_filter(fields, condition, ctx.timezone)
        filters.append(
            {
                "id": str(uuid4()),
                "field": field.id,
                "type": op,
                "value": value,
                "group": None,
            }
        )
    return _result(
        color_rule={
            "id": str(uuid4()),
            "color": rule.color,
            "operator": rule.operator,
            "filters": filters,
            "filter_groups": [],
        }
    )


def _filter_state(view):
    return {
        "operator": view.filter_type,
        "groups": list(
            view.filter_groups.order_by("id").values(
                "id", "parent_group_id", "filter_type"
            )
        ),
        "filters": list(
            view.viewfilter_set.order_by("id").values(
                "id", "group_id", "field_id", "type", "value"
            )
        ),
    }


def _edit_filters(ctx, prompt, view_id, profile):
    view = get_view(ctx, view_id)
    for operation in (ListViewFilterOperationType, CreateViewFilterOperationType):
        CoreHandler().check_permissions(
            ctx.user, operation.type, workspace=ctx.workspace, context=view
        )
    before = _filter_state(view)
    changes = _generate(
        filters_agent,
        profile,
        prompt,
        table=_schema(ctx, view.table_id),
        view={**before, "name": view.name},
        response_language=ctx.user.profile.language,
    )
    change_operator = (
        changes.operator is not None and changes.operator != view.filter_type
    )
    if not (changes.add or changes.update or changes.remove or change_operator):
        return _result(changes.summary)
    with transaction.atomic():
        view = ViewHandler().get_view_for_update(ctx.user, view_id)
        filters = {f.id: f for f in view.viewfilter_set.select_for_update(of=("self",))}
        if before != _filter_state(view):
            raise EditorGenerationFailed()
        touched = [e.filter_id for e in changes.update] + changes.remove
        if len(set(touched)) != len(touched) or not set(touched).issubset(filters):
            raise EditorGenerationFailed()
        fields = {f.id: f for f in view.table.field_set.all()}
        if change_operator:
            UpdateViewActionType.do(
                ctx.user, view.specific, filter_type=changes.operator
            )
        for condition in changes.add:
            create_view_filter(ctx.user, view, fields, condition, ctx.timezone)
        for edit in changes.update:
            field, op, value = resolve_view_filter(fields, edit.condition, ctx.timezone)
            UpdateViewFilterActionType.do(
                ctx.user, filters[edit.filter_id], field, op, value
            )
        for pk in changes.remove:
            DeleteViewFilterActionType.do(ctx.user, filters[pk])
    return _result(changes.summary, changed=True)


def _create_view(ctx, prompt, table_id, profile):
    table = get_table(ctx, table_id, CreateViewOperationType.type)
    plan = _generate(view_agent, profile, prompt, table=_schema(ctx, table.id))
    if plan.view is None:
        return _result(plan.reason or _("Kuma could not create this view."))
    if plan.view.public:
        raise EditorGenerationFailed()
    with transaction.atomic():
        result = create_views(ctx, table.id, [plan.view])
        if not result["created_views"]:
            raise EditorGenerationFailed()
        created = result["created_views"][0]
        if created.get("skipped_fields"):
            raise EditorGenerationFailed()
        view = get_view(ctx, created["id"])
        fields = {f.id: f for f in table.field_set.all()}
        if plan.operator != view.filter_type and plan.filters:
            UpdateViewActionType.do(ctx.user, view.specific, filter_type=plan.operator)
        for condition in plan.filters:
            create_view_filter(ctx.user, view, fields, condition, ctx.timezone)
        if plan.sorts:
            set_view_sorts(ctx, view.id, plan.sorts)
    return _result(
        _("Created view “%(name)s”.") % {"name": view.name},
        changed=True,
        view_id=view.id,
    )


def run_editor_action(action, ctx, prompt, parameters, profile):
    try:
        if action == "create_table":
            return _create_table(ctx, prompt, parameters, profile)
        if action == "create_database":
            return _create_database(ctx, prompt, parameters, profile)
        if action == "generate_ai_field_prompt":
            return _ai_field_prompt(ctx, prompt, parameters, profile)
        if action == "add_row_color":
            return _row_color(ctx, prompt, parameters["view_id"], profile)
        if action == "generate_agent_instructions":
            draft = _generate(
                instructions_agent,
                profile,
                prompt,
                current=parameters["current"],
                agent_name=parameters.get("agent_name", ""),
            )
            if not draft.instructions.strip():
                raise EditorGenerationFailed()
            return _result(instructions=draft.instructions)
        if action == "create_view":
            return _create_view(ctx, prompt, parameters["table_id"], profile)
        if action == "edit_view_filters":
            return _edit_filters(ctx, prompt, parameters["view_id"], profile)
        if action == "generate_formula":
            return _generate_formula(ctx, prompt, parameters, profile)
    except (
        AgentRunError,
        TimeoutError,
        ModelRetry,
        ToolInputError,
        ViewFilterNotSupported,
        ViewFilterTypeNotAllowedForField,
        ValidationError,
    ) as exc:
        raise EditorGenerationFailed() from exc
    raise ValueError(f"Unsupported assistant action: {action}")

from collections.abc import Callable
from typing import Annotated, Any, Literal

from django.utils.translation import gettext as _

from pydantic import AwareDatetime, Field
from pydantic_ai import RunContext

from baserow.contrib.automation.tools import automations as shared_automations
from baserow.contrib.builder.tools import applications as shared_builders
from baserow.contrib.builder.tools.themes import ThemeName
from baserow.contrib.dashboard.tools import dashboards as shared_dashboards
from baserow.contrib.database.tools import databases as shared_databases
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools import applications as shared_applications
from baserow.core.tools import search as shared_search
from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset
from baserow_enterprise.audit_log import tools as shared_audit_log

from . import helpers
from .helpers import APPLICATION_TYPES

_BUILDER_TYPES = {value: key for key, value in APPLICATION_TYPES.items()}


def list_builders(
    ctx: RunContext[AssistantDeps],
    builder_types: Annotated[
        list[Literal["database", "application", "automation", "dashboard"]] | None,
        Field(
            description="Filter: only return builders of these types. null to return all types."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(
            ge=1,
            le=shared_applications.MAX_PAGE_SIZE,
            description="The number of builders a page.",
        ),
    ] = 20,
) -> dict[str, Any]:
    """\
    List databases, applications, automations, dashboards in the workspace.

    WHEN to use: You need to find databases, applications, automations, or dashboards in the workspace. Call this before creating builders to avoid duplicates.
    WHAT it does: Lists the builders the user can access, optionally filtered by type, one page at a time (20 by default).
    RETURNS: Dict of builders grouped by type, each with id, name, type. _info says when more pages follow.
    DO NOT USE when: You already know the builder ID you need.
    """

    ctx.deps.tool_helpers.update_status(
        _("Listing %(builder_types)ss...")
        % {
            "builder_types": builder_types[0]
            if builder_types and len(builder_types) == 1
            else "builder"
        }
    )

    result = shared_applications.list_applications(
        ctx.deps.tool_context(),
        types=[APPLICATION_TYPES[t] for t in builder_types or APPLICATION_TYPES],
        page=page,
        size=size,
    )

    builders_by_type = {}
    for application in result["applications"]:
        builder_type = _BUILDER_TYPES[application["type"]]
        builders_by_type.setdefault(builder_type, []).append(
            {**application, "type": builder_type}
        )

    if result["has_more"]:
        shown = len(result["applications"])
        builders_by_type["_info"] = (
            f"Showing {shown} of {result['total']} builders. "
            f"Call again with page={page + 1} for more, or use builder_types to "
            "filter."
        )

    return builders_by_type


def search_workspace(
    ctx: RunContext[AssistantDeps],
    query: shared_search.SearchQuery,
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    types: Annotated[
        list[str] | None,
        Field(
            description=(
                "Only return these types: database, database_table, database_field, "
                "database_row, builder, automation, dashboard, agent. Null for all."
            )
        ),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(
            ge=1,
            le=shared_search.MAX_PAGE_SIZE,
            description="The number of results a page.",
        ),
    ] = 20,
) -> dict[str, Any]:
    """\
    Search the workspace by name or content.

    WHEN to use: The user names something and you don't know where it is, like a customer, a row value, or which table holds some data.
    WHAT it does: Finds databases, tables, fields, rows, applications, automations, dashboards and agents the user can access.
    RETURNS: results with type, id, title, subtitle, metadata, and has_more. A row's table_id and row_id are in its metadata.
    DO NOT USE when: You already know the table and want to filter its rows; use list_rows.
    """

    ctx.deps.tool_helpers.update_status(_("Searching the workspace..."))

    return shared_search.search_workspace(
        ctx.deps.tool_context(), query=query, types=types, page=page, size=size
    )


def list_audit_log(
    ctx: RunContext[AssistantDeps],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    query: shared_audit_log.SearchQuery | None = None,
    user_id: Annotated[
        int | None, Field(description="Only what this user did, by user ID.")
    ] = None,
    action_types: Annotated[
        list[str] | None,
        Field(description="Only these actions, like create_table or delete_rows."),
    ] = None,
    from_timestamp: Annotated[
        AwareDatetime | None,
        Field(
            description=(
                "Only from this moment, in ISO format with the offset of the user's "
                "timezone, like 2026-11-02T09:00:00+01:00."
            )
        ),
    ] = None,
    to_timestamp: Annotated[
        AwareDatetime | None,
        Field(description="Only up to this moment, in the same format."),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(
            ge=1,
            le=shared_audit_log.MAX_PAGE_SIZE,
            description="The number of entries a page.",
        ),
    ] = 50,
) -> dict[str, Any]:
    """\
    List who did what in this workspace.

    WHEN to use: User asks who changed, created or deleted something, or what happened recently.
    WHAT it does: Returns audit log entries of this workspace, newest first, optionally by text, user, action or date. Needs an advanced or enterprise licence and a workspace admin.
    RETURNS: entries with id, timestamp, actor, action_type, description, and has_more.
    HOW: Prefer action_types over query when you know the action. To find the name of a table or row, leave query out and read the descriptions.
    NO RESULTS: With a query this doesn't prove nothing happened. Try another word or no query before saying so.
    """

    ctx.deps.tool_helpers.update_status(_("Reading the audit log..."))

    return shared_audit_log.list_audit_log(
        ctx.deps.tool_context(),
        query=query,
        user_id=user_id,
        action_types=action_types,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        page=page,
        size=size,
    )


def _create_or_reuse(
    ctx: RunContext[AssistantDeps],
    builder_type: str,
    name: str,
    create: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """
    Reuse the builder of this type with exactly this name, or create it.

    :param ctx: The run context.
    :param builder_type: Kuma's type of the builder.
    :param name: The exact name.
    :param create: Creates the builder and returns its id and name.
    :return: The created and the reused builder, each in a list that may be empty.
    """

    ctx.deps.tool_helpers.raise_if_cancelled()
    existing = helpers.find_builder(ctx.deps.tool_context(), builder_type, name)
    if existing is not None:
        return {"created_builders": [], "reused_builders": [existing]}
    return {
        "created_builders": [{**create(), "type": builder_type}],
        "reused_builders": [],
    }


def create_database(
    ctx: RunContext[AssistantDeps],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="Name of the database, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create one new database.

    WHEN to use: User wants a new database. For several, call this once per database.
    WHAT it does: Creates the database, or reuses one with exactly this name.
    RETURNS: created_builders and reused_builders, one of them holding the database with id, name, type.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates. Add tables with create_tables.
    NOT FOR APP RECORDS: Never create a database to hold records an app should show unless the user asked for new data storage or an example, demo, or sample app. Call list_tables and, if nothing matches, ask the user instead.
    """

    tool_context = ctx.deps.tool_context()
    return _create_or_reuse(
        ctx,
        "database",
        name,
        lambda: shared_databases.create_database(tool_context, name)[
            "created_database"
        ],
    )


def create_automation(
    ctx: RunContext[AssistantDeps],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="Name of the automation, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create one new automation.

    WHEN to use: User wants a new automation. A request that names it or asks for an empty one is enough. For several, call this once per automation.
    WHAT it does: Creates the automation, or reuses one with exactly this name.
    RETURNS: created_builders and reused_builders, one of them holding the automation with id, name, type.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates. Add workflows with create_workflows.
    """

    tool_context = ctx.deps.tool_context()
    return _create_or_reuse(
        ctx,
        "automation",
        name,
        lambda: shared_automations.create_automation(tool_context, name)[
            "created_automation"
        ],
    )


def create_dashboard(
    ctx: RunContext[AssistantDeps],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="Name of the dashboard, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create one new dashboard.

    WHEN to use: User wants a new dashboard. For several, call this once per dashboard.
    WHAT it does: Creates the dashboard, or reuses one with exactly this name.
    RETURNS: created_builders and reused_builders, one of them holding the dashboard with id, name, type.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates. Add widgets with create_widgets.
    """

    tool_context = ctx.deps.tool_context()
    return _create_or_reuse(
        ctx,
        "dashboard",
        name,
        lambda: shared_dashboards.create_dashboard(tool_context, name)[
            "created_dashboard"
        ],
    )


def create_builder(
    ctx: RunContext[AssistantDeps],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="Name of the application, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    theme: Annotated[
        ThemeName | None,
        Field(description="Theme to start with. The default is baserow."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create one new application.

    WHEN to use: User wants a new application, app or website, which always means an application builder. Not for a database, automation or dashboard unless the user names one. For several, call this once per application.
    WHAT it does: Creates the application, or reuses one with exactly this name.
    RETURNS: created_builders and reused_builders, one of them holding the application with id, name, type.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates.
    THEME: Pick a theme matching the app purpose — baserow (clean light, default), eclipse (dark, dashboards/analytics), ivory (warm light, blogs/portfolios).
    NAME: Pick a sensible name yourself. Never call ask_user only to get a name.
    ASK FIRST: A bare request with no purpose, such as "create an app for my team", needs ask_user about what it should manage before creating anything; who it is for is not a purpose. A request that says what the application is ("a website", "a project tracker") or asks for an empty one is enough to create it.
    NOT FOR APP RECORDS: Creating the application does not authorize creating a database or tables for the records it shows, unless the user asked for new data storage or an example, demo, or sample app. Call list_tables and, if nothing matches, ask the user instead.
    """

    tool_context = ctx.deps.tool_context()
    result = _create_or_reuse(
        ctx,
        "application",
        name,
        lambda: shared_builders.create_builder(tool_context, name, theme)[
            "created_builder"
        ],
    )
    for reused in result["reused_builders"]:
        result.update(helpers.reused_builder_report(ctx.deps.user, reused, theme))
    return result


def switch_mode(
    ctx: RunContext[AssistantDeps],
    mode: Annotated[
        Literal["database", "application", "automation", "dashboard", "explain"],
        Field(
            description=(
                "Target mode: 'database' for table/field/view/row ops, "
                "'application' for page/element/data-source ops, "
                "'automation' for workflow/node ops, "
                "'dashboard' for widget ops, "
                "'explain' for answering Baserow questions."
            )
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    Switch between domain modes (database, application, automation, dashboard, explain).

    WHEN to use: Task needs tools from a different domain, or user asks a how-to question (→ "explain").
    WHAT it does: Changes the available toolset to the target domain's tools.
    RETURNS: Confirmation of mode switch.
    DO NOT USE when: Already in the requested mode.
    """

    target = AgentMode(mode)
    if ctx.deps.mode == target:
        return f"Already in {target.value} mode."

    ctx.deps.mode = target
    if target == AgentMode.EXPLAIN:
        return (
            "Switched to explain mode. "
            "Call search_user_docs now to answer the user's question from the Baserow documentation."
        )
    return f"Switched to {target.value} mode."


# The tool that updates each application type, by the type list_builders shows.
_UPDATE_TOOLS = {
    "database": "update_database",
    "application": "update_builder",
    "automation": "update_automation",
    "dashboard": "update_dashboard",
}


def _application_not_found(
    ctx: RunContext[AssistantDeps], application_id: int
) -> ToolInputError:
    """
    The error for an ID that isn't an application of the type a tool updates. When
    the ID is another type of application, the error names the tool for it.
    """

    application = (
        shared_applications.visible_applications(ctx.deps.tool_context())
        .filter(id=application_id)
        .first()
    )
    if application is not None:
        model_type = application.get_type().type
        for builder_type, tool in _UPDATE_TOOLS.items():
            if APPLICATION_TYPES[builder_type] == model_type:
                return ToolInputError(
                    f"Application with ID {application_id} is not of this type: "
                    f"list_builders shows it as {builder_type}. Use {tool} for it."
                )
    return ToolInputError(
        f"Application with ID {application_id} not found in this workspace. "
        "Use list_builders to find valid application IDs."
    )


def update_database(
    ctx: RunContext[AssistantDeps],
    database_id: Annotated[
        int,
        Field(description="ID of the database, from list_builders or create_database."),
    ],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="New name, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Rename a database.

    WHEN to use: User wants to rename a database.
    RETURNS: id, name, and changed, which is false when it already had that name.
    """

    try:
        result = shared_databases.update_database(
            ctx.deps.tool_context(), database_id, name
        )
    except ApplicationDoesNotExist as exc:
        raise _application_not_found(ctx, database_id) from exc
    return {**result["updated_database"], "changed": result["changed"]}


def update_automation(
    ctx: RunContext[AssistantDeps],
    automation_id: Annotated[
        int,
        Field(
            description="ID of the automation, from list_builders or create_automation."
        ),
    ],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="New name, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Rename an automation.

    WHEN to use: User wants to rename an automation.
    RETURNS: id, name, and changed, which is false when it already had that name.
    """

    try:
        result = shared_automations.update_automation(
            ctx.deps.tool_context(), automation_id, name
        )
    except ApplicationDoesNotExist as exc:
        raise _application_not_found(ctx, automation_id) from exc
    return {**result["updated_automation"], "changed": result["changed"]}


def update_dashboard(
    ctx: RunContext[AssistantDeps],
    dashboard_id: Annotated[
        int,
        Field(
            description="ID of the dashboard, from list_builders or create_dashboard."
        ),
    ],
    name: Annotated[
        shared_applications.ApplicationName,
        Field(description="New name, at most 160 characters."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Rename a dashboard.

    WHEN to use: User wants to rename a dashboard.
    RETURNS: id, name, and changed, which is false when it already had that name.
    """

    try:
        result = shared_dashboards.update_dashboard(
            ctx.deps.tool_context(), dashboard_id, name
        )
    except ApplicationDoesNotExist as exc:
        raise _application_not_found(ctx, dashboard_id) from exc
    return {**result["updated_dashboard"], "changed": result["changed"]}


def update_builder(
    ctx: RunContext[AssistantDeps],
    builder_id: Annotated[
        int,
        Field(
            description="ID of the application, from list_builders or create_builder."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    name: Annotated[
        shared_applications.ApplicationName | None,
        Field(description="New name, at most 160 characters."),
    ] = None,
    login_page_id: Annotated[
        int | None,
        Field(description="ID of the page to use as the login page."),
    ] = None,
) -> dict[str, Any]:
    """\
    Update an application: its name or its login page.

    WHEN to use: User wants to rename an application or set its login page.
    WHAT it does: Updates what is set and leaves the rest.
    RETURNS: id, name, login_page_id, and changed, which is false when there was nothing to change.
    HOW: For a login page, use setup_user_source first (which creates the login page), then call this if you need to change it.
    """

    try:
        result = shared_builders.update_builder(
            ctx.deps.tool_context(), builder_id, name, login_page_id
        )
    except ApplicationDoesNotExist as exc:
        raise _application_not_found(ctx, builder_id) from exc
    return {**result["updated_builder"], "changed": result["changed"]}


def ask_user(
    ctx: RunContext[AssistantDeps],
    question: Annotated[
        str,
        Field(
            description=(
                "The question to put to the user, phrased so a single short "
                "reply answers it. Cover every unknown in one question."
            )
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    Ask the user for a requirement you cannot look up, then stop.

    WHEN to use: A change request refers to existing data, fields, or users no list_* tool result matches, a new build never says what it is for, or reusing an exact-name resource would require changes to that existing resource the user has not authorized.
    WHAT it does: Records the question; you deliver it as your final answer.
    RETURNS: Instructions for delivering the question.
    DO NOT USE when: The user asks a product/how-to question (answer it using search_user_docs), a sensible first version can be built with defaults (see `<intent>`), a list_* tool can answer it, or you only want permission to continue work already authorized.
    Before asking about a CTA destination, inspect the app's pages: use an existing Home page as the default and state that choice. Draft presentation copy yourself.
    Before asking for a tool prerequisite, inspect its schema with search_tools. Never ask for an integration ID that the workflow tool does not accept; it handles integration references itself.
    """

    ctx.deps.pending_question = question
    return (
        "Question recorded. Deliver it now: restate this question verbatim as "
        "your final answer and stop — do not create, guess, or build anything "
        "until the user replies."
    )


TOOL_FUNCTIONS = [
    list_builders,
    search_workspace,
    list_audit_log,
    create_database,
    create_automation,
    create_dashboard,
    create_builder,
    update_database,
    update_automation,
    update_dashboard,
    update_builder,
    switch_mode,
    ask_user,
]
core_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)

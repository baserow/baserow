from typing import Annotated, Any, Literal

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import AwareDatetime, Field
from pydantic_ai import ModelRetry, RunContext
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.actions import (
    CreateApplicationActionType,
    UpdateApplicationActionType,
)
from baserow.core.tools import applications as shared_applications
from baserow.core.tools import search as shared_search
from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    require_payload,
    validation_messages,
)
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset
from baserow_enterprise.audit_log import tools as shared_audit_log

from . import helpers
from .types import BuilderItem, BuilderItemCreate, BuilderUpdate

# Kuma's builder types and the application types they are.
_APPLICATION_TYPES = {
    "database": "database",
    "application": "builder",
    "automation": "automation",
    "dashboard": "dashboard",
}
_BUILDER_TYPES = {value: key for key, value in _APPLICATION_TYPES.items()}


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
        types=[_APPLICATION_TYPES[t] for t in builder_types or _APPLICATION_TYPES],
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


def create_builders(
    ctx: RunContext[AssistantDeps],
    builders: Annotated[
        list[BuilderItemCreate],
        Field(description="List of builders to create, each with a name and type."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Create a new database, application, or automation.

    WHEN to use: User wants a new database, application, or automation created in the workspace.
    WHAT it does: Creates missing builders and reuses an exact name-and-type match in the workspace.
    RETURNS: Created and reused builders with id, name, type.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates.
    THEME (applications only): Pick a theme matching the app purpose — baserow (clean light, default), eclipse (dark, dashboards/analytics), ivory (warm light, blogs/portfolios).
    ASK FIRST: An application needs a purpose — what it manages or shows. For a bare request such as "create an app for my team", call ask_user before creating anything. A request that names the builder or asks for an empty one (e.g. "create an empty automation called X") is enough to create it.
    NOT FOR APP RECORDS: Never create a database to hold records an app should show unless the user asked for new data storage or an example, demo, or sample app. Call list_tables and, if nothing matches, ask the user instead.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    require_payload("create_builders", "builders", builders)
    requested_builders, conflicting_names = helpers.canonical_builder_requests(builders)
    if conflicting_names:
        names = ", ".join(conflicting_names)
        raise ModelRetry(
            f"Conflicting builder definitions use the same name and type: {names}. "
            "Submit one definition per builder."
        )

    existing_builders = {
        (builder.type, builder.name): builder.model_dump()
        for builder in helpers.list_builder_items(user, workspace)
    }

    created_builders = []
    reused_builders = []
    reused_requests = []
    with transaction.atomic():
        for builder in requested_builders:
            tool_helpers.raise_if_cancelled()
            key = (builder.type, builder.name)
            if existing := existing_builders.get(key):
                reused_builders.append(existing)
                reused_requests.append((builder, existing))
                continue

            tool_helpers.update_status(
                _("Creating %(builder_type)s %(builder_name)s...")
                % {"builder_type": builder.type, "builder_name": builder.name}
            )
            application = CreateApplicationActionType.do(
                user, workspace, builder.get_orm_type(), name=builder.name
            )
            builder.post_creation_hook(user, application)
            created_builder = BuilderItem(
                id=application.id,
                name=application.name,
                type=builder.type,
            ).model_dump()
            created_builders.append(created_builder)
            existing_builders[key] = created_builder

    result = {
        "created_builders": created_builders,
        "reused_builders": reused_builders,
    }
    result.update(helpers.reused_builder_report(user, reused_requests))
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


def update_builder(
    ctx: RunContext[AssistantDeps],
    builder_id: Annotated[
        int,
        Field(
            description="ID of the builder to update, as returned by list_builders or create_builders."
        ),
    ],
    update: Annotated[
        BuilderUpdate,
        Field(description="Settings to change. Set only the fields you want changed."),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Update an application's settings (name, login page, etc.).

    WHEN to use: User wants to rename an application, set a login page, or change application-level settings.
    WHAT it does: Updates the specified application's settings. Fields are type-specific.
    RETURNS: Updated application info.
    HOW: For setting a login page on a builder app, use setup_user_source first (which creates the login page), then call this if you need to change it.
    """

    user = ctx.deps.user

    app = helpers.get_application(user, ctx.deps.workspace, builder_id)
    ctx.deps.tool_helpers.update_status(
        _("Updating %(app_name)s...") % {"app_name": app.name}
    )

    requested_changes = update.to_update_kwargs(app)
    changes = {
        name: value
        for name, value in requested_changes.items()
        if getattr(app, name) != value
    }
    if changes:
        try:
            app = UpdateApplicationActionType.do(user, app, **changes)
        except DRFValidationError as exc:
            # The builder refuses a login page it doesn't own.
            raise ToolInputError(
                f"{validation_messages(exc)} Use list_pages to find valid page IDs. "
                "No changes were applied."
            ) from exc

    result: dict[str, Any] = {
        "id": app.id,
        "name": app.name,
        "changed": bool(changes),
    }
    if hasattr(app, "login_page_id"):
        result["login_page_id"] = app.login_page_id
    return result


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
    create_builders,
    update_builder,
    switch_mode,
    ask_user,
]
core_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)

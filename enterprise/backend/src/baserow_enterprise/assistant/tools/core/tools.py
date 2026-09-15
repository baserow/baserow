from typing import Annotated, Any, Literal

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.actions import CreateApplicationActionType
from baserow.core.service import CoreService
from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps
from baserow_enterprise.assistant.tools.shared import require_payload

from . import helpers
from .types import BuilderItem, BuilderItemCreate, BuilderUpdate


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
) -> dict[str, Any]:
    """\
    List databases, applications, automations, dashboards in the workspace.

    WHEN to use: You need to find databases, applications, automations, or dashboards in the workspace. Call this before creating builders to avoid duplicates.
    WHAT it does: Lists all builders the user can access, optionally filtered by type. Max 20 results.
    RETURNS: Dict of builders grouped by type, each with id, name, type.
    DO NOT USE when: You already know the builder ID you need.
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    tool_helpers.update_status(
        _("Listing %(builder_types)ss...")
        % {
            "builder_types": builder_types[0]
            if builder_types and len(builder_types) == 1
            else "builder"
        }
    )

    builders_by_type = {}
    for builder in helpers.list_builder_items(user, workspace):
        if not builder_types or builder.type in builder_types:
            builders_by_type.setdefault(builder.type, []).append(builder.model_dump())

    if not builders_by_type:
        return {}

    total = sum(len(builders) for builders in builders_by_type.values())
    max_items = 20
    if total > max_items:
        truncated = {}
        remaining = max_items
        for builder_type, builders in builders_by_type.items():
            truncated[builder_type] = builders[:remaining]
            remaining -= len(truncated[builder_type])
            if remaining <= 0:
                break
        return {
            **truncated,
            "_info": f"Showing {max_items} of {total} builders. "
            "Use builder_types to filter.",
        }

    return builders_by_type


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
        Literal["database", "application", "automation", "explain"],
        Field(
            description=(
                "Target mode: 'database' for table/field/view/row ops, "
                "'application' for page/element/data-source ops, "
                "'automation' for workflow/node ops, "
                "'explain' for answering Baserow questions."
            )
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> str:
    """\
    Switch between domain modes (database, application, automation, explain).

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

    from baserow.core.handler import CoreHandler

    user = ctx.deps.user

    app = CoreService().get_application(user, builder_id).specific
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
        CoreHandler().update_application(user, app, **changes)
        app.refresh_from_db()

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

    WHEN to use: The request names data, fields, or users no list_* tool result matches, or never says what it is for.
    WHAT it does: Records the question; you deliver it as your final answer.
    RETURNS: Instructions for delivering the question.
    DO NOT USE when: A sensible first version can be built with defaults (see `<intent>`), a list_* tool can answer it, or you only want permission to continue — build and iterate.
    """

    ctx.deps.pending_question = question
    return (
        "Question recorded. Deliver it now: restate this question verbatim as "
        "your final answer and stop — do not create, guess, or build anything "
        "until the user replies."
    )


TOOL_FUNCTIONS = [list_builders, create_builders, update_builder, switch_mode, ask_user]
core_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)

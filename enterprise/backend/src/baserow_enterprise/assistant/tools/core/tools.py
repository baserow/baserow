from typing import Annotated, Any, Literal

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.actions import CreateApplicationActionType
from baserow.core.service import CoreService
from baserow_enterprise.assistant.deps import AgentMode, AssistantDeps

from .types import BuilderItem, BuilderItemCreate, BuilderUpdate, builder_type_registry


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

    applications_qs = CoreService().list_applications_in_workspace(
        user, workspace, specific=False
    )

    builders = {}
    for app in applications_qs:
        try:
            item = builder_type_registry.from_django_orm(app)
        except KeyError:
            continue
        if not builder_types or item.type in builder_types:
            builders.setdefault(item.type, []).append(item.model_dump())

    if not builders:
        return {}

    total = sum(len(v) for v in builders.values())
    max_items = 20
    if total > max_items:
        truncated = {}
        remaining = max_items
        for btype, items in builders.items():
            truncated[btype] = items[:remaining]
            remaining -= len(truncated[btype])
            if remaining <= 0:
                break
        return {
            **truncated,
            "_info": f"Showing {max_items} of {total} builders. "
            "Use builder_types to filter.",
        }

    return builders


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
    WHAT it does: Creates one or more builders with the specified names and types.
    RETURNS: List of created builders with id, name, type.
    DO NOT USE when: A builder with that name may already exist — check with list_builders first.
    HOW: Pick a unique, descriptive name. Check existing builders with list_builders to avoid duplicates.
    THEME (applications only): Pick a theme matching the app purpose — baserow (clean light, default), eclipse (dark, dashboards/analytics), ivory (warm light, blogs/portfolios).
    """

    user = ctx.deps.user
    workspace = ctx.deps.workspace
    tool_helpers = ctx.deps.tool_helpers

    created_builders = []
    with transaction.atomic():
        for builder in builders:
            tool_helpers.raise_if_cancelled()
            tool_helpers.update_status(
                _("Creating %(builder_type)s %(builder_name)s...")
                % {"builder_type": builder.type, "builder_name": builder.name}
            )
            builder_orm_instance = CreateApplicationActionType.do(
                user, workspace, builder.get_orm_type(), name=builder.name
            )
            builder.post_creation_hook(user, builder_orm_instance)
            created_builders.append(
                BuilderItem(
                    id=builder_orm_instance.id,
                    name=builder_orm_instance.name,
                    type=builder.type,
                ).model_dump()
            )

    return {"created_builders": created_builders}


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
    update: Annotated[
        BuilderUpdate, Field(description="Application settings to update.")
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

    app = CoreService().get_application(user, update.builder_id).specific
    ctx.deps.tool_helpers.update_status(
        _("Updating %(app_name)s...") % {"app_name": app.name}
    )

    update_kwargs = update.to_update_kwargs(app)
    if update_kwargs:
        CoreHandler().update_application(user, app, **update_kwargs)
        app.refresh_from_db()

    result: dict[str, Any] = {"id": app.id, "name": app.name}
    if hasattr(app, "login_page_id"):
        result["login_page_id"] = app.login_page_id
    return result


TOOL_FUNCTIONS = [list_builders, create_builders, update_builder, switch_mode]
core_toolset = FunctionToolset(TOOL_FUNCTIONS, max_retries=3)

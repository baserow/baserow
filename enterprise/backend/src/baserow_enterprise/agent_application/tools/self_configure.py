from typing import Annotated, Any, Optional

from asgiref.sync import sync_to_async
from pydantic import Field
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.exceptions import PermissionException
from baserow.core.generative_ai.registries import generative_ai_model_type_registry
from baserow.core.handler import CoreHandler

from ..deps import AgentRunDeps

# Tool types a chat can toggle; configurable tool types (services) carry too
# much schema surface to be managed from a conversation.
TOGGLEABLE_TOOL_TYPES = ["workspace", "workspace_search", "web_search"]

_THOUGHT = Annotated[str, Field(description="Brief reasoning for calling this tool.")]


def _chat_user(ctx: RunContext[AgentRunDeps]):
    """
    Self-configuration always acts as the human in the conversation, so
    normal RBAC decides whether they may reconfigure the agent.
    """

    user = ctx.deps.chat.user
    if user is None:
        raise PermissionException()
    return user


def _permission_error() -> dict:
    return {
        "error": "The user in this conversation is not allowed to change the "
        "agent's configuration."
    }


async def update_own_instructions(
    ctx: RunContext[AgentRunDeps],
    instructions: Annotated[
        str, Field(description="The new full instructions for this agent.")
    ],
    thought: _THOUGHT,
) -> dict:
    """
    Replaces this agent's instructions. Use when the user asks you to change
    what you should do, or during setup to write your own instructions.
    """

    from ..service import AgentApplicationService

    def update():
        user = _chat_user(ctx)
        AgentApplicationService().update_agent(
            user, ctx.deps.agent.id, instructions=instructions
        )
        ctx.deps.agent.instructions = instructions
        return {"success": True}

    try:
        return await sync_to_async(update)()
    except PermissionException:
        return _permission_error()


async def list_available_models(
    ctx: RunContext[AgentRunDeps], thought: _THOUGHT
) -> dict:
    """
    Lists the generative AI models available in this workspace, per provider
    type. Use before changing your own model.
    """

    def list_models():
        return generative_ai_model_type_registry.get_enabled_models_per_type(
            ctx.deps.workspace
        )

    return {"models": await sync_to_async(list_models)()}


async def update_own_model(
    ctx: RunContext[AgentRunDeps],
    ai_generative_ai_type: Annotated[
        str, Field(description="The provider type, e.g. 'openai' or 'anthropic'.")
    ],
    ai_generative_ai_model: Annotated[
        str, Field(description="The model identifier, must be enabled.")
    ],
    thought: _THOUGHT,
) -> dict:
    """
    Changes the AI model this agent uses, starting from the next conversation
    turn. The model must be one of the workspace's enabled models.
    """

    from ..service import AgentApplicationService

    def update():
        enabled = generative_ai_model_type_registry.get_enabled_models_per_type(
            ctx.deps.workspace
        )
        if ai_generative_ai_model not in enabled.get(ai_generative_ai_type, []):
            return {
                "error": f"The model {ai_generative_ai_model} is not enabled "
                f"for provider {ai_generative_ai_type}. Use "
                "list_available_models to see the options."
            }
        user = _chat_user(ctx)
        AgentApplicationService().update_agent(
            user,
            ctx.deps.agent.id,
            ai_generative_ai_type=ai_generative_ai_type,
            ai_generative_ai_model=ai_generative_ai_model,
        )
        return {"success": True}

    try:
        return await sync_to_async(update)()
    except PermissionException:
        return _permission_error()


async def add_own_trigger(
    ctx: RunContext[AgentRunDeps],
    service_type: Annotated[
        str,
        Field(
            description=(
                "The trigger service type: local_baserow_rows_created, "
                "local_baserow_rows_updated, local_baserow_rows_deleted, "
                "periodic, or http_trigger."
            )
        ),
    ],
    thought: _THOUGHT,
    table_name: Annotated[
        Optional[str],
        Field(
            description=(
                "For the row based triggers: the name of the table to watch. "
                "It is matched against the tables the user can see."
            )
        ),
    ] = None,
    table_id: Annotated[
        Optional[int],
        Field(description="The table to watch, when the exact id is known."),
    ] = None,
    interval: Annotated[
        Optional[str],
        Field(
            description=("For the periodic trigger: MINUTE, HOUR, DAY, WEEK, or MONTH.")
        ),
    ] = None,
    hour: Annotated[
        Optional[int], Field(description="For the periodic trigger: the hour.")
    ] = None,
    minute: Annotated[
        Optional[int], Field(description="For the periodic trigger: the minute.")
    ] = None,
) -> dict:
    """
    Adds a trigger so this agent runs automatically. An agent can have
    multiple triggers; use list_own_triggers to see the existing ones.
    """

    from baserow.contrib.database.table.handler import TableHandler
    from baserow.contrib.integrations.local_baserow.models import (
        LocalBaserowIntegration,
    )

    from ..operations import UpdateAgentTriggerOperationType
    from ..realtime import broadcast_configuration_updated
    from ..triggers.handler import AgentTriggerHandler

    def resolve_table(user, workspace) -> int | dict:
        # The table is resolved through the tables the conversation's user
        # can see, so the agent can configure a trigger by table name during
        # setup, before it has any workspace access of its own.
        tables = list(TableHandler().list_workspace_tables(user, workspace))

        if table_id is not None:
            if any(t.id == table_id for t in tables):
                return table_id
        elif table_name is not None:
            matches = [t for t in tables if t.name.lower() == table_name.lower()]
            if len(matches) == 1:
                return matches[0].id
            if len(matches) > 1:
                return {
                    "error": f"Multiple tables are named {table_name}: "
                    f"{[(t.id, t.name) for t in matches]}. Retry with table_id."
                }
        else:
            return {"error": "Provide table_name or table_id for this trigger."}

        available = [(t.id, t.name) for t in tables]
        return {"error": f"The table was not found. Available tables: {available}."}

    def set_trigger():
        user = _chat_user(ctx)
        application = ctx.deps.agent.application
        CoreHandler().check_permissions(
            user,
            UpdateAgentTriggerOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        service_values: dict[str, Any] = {}
        if service_type.startswith("local_baserow_"):
            resolved = resolve_table(user, application.workspace)
            if isinstance(resolved, dict):
                return resolved
            service_values["table_id"] = resolved
            integration = LocalBaserowIntegration.objects.filter(
                application=application
            ).first()
            if integration is not None:
                service_values["integration_id"] = integration.id
        if interval is not None:
            service_values["interval"] = interval
        if hour is not None:
            service_values["hour"] = hour
        if minute is not None:
            service_values["minute"] = minute

        trigger = AgentTriggerHandler().create_trigger(
            user, application, service_type, service_values=service_values
        )
        broadcast_configuration_updated(application)
        return {"success": True, "trigger_id": trigger.id}

    try:
        return await sync_to_async(set_trigger)()
    except PermissionException:
        return _permission_error()
    except Exception as exc:
        return {"error": f"Could not add the trigger: {exc}"}


async def list_own_triggers(ctx: RunContext[AgentRunDeps], thought: _THOUGHT) -> dict:
    """
    Lists this agent's configured triggers.
    """

    from ..triggers.handler import AgentTriggerHandler

    def list_triggers():
        application = ctx.deps.agent.application
        return {
            "triggers": [
                {
                    "id": trigger.id,
                    "service_type": trigger.service.specific.get_type().type,
                    "enabled": trigger.enabled,
                }
                for trigger in AgentTriggerHandler().list_triggers(application)
            ]
        }

    return await sync_to_async(list_triggers)()


async def remove_own_trigger(
    ctx: RunContext[AgentRunDeps],
    trigger_id: Annotated[int, Field(description="The id of the trigger to remove.")],
    thought: _THOUGHT,
) -> dict:
    """
    Removes one of this agent's triggers.
    """

    from ..exceptions import AgentTriggerDoesNotExist
    from ..operations import UpdateAgentTriggerOperationType
    from ..realtime import broadcast_configuration_updated
    from ..triggers.handler import AgentTriggerHandler

    def remove():
        user = _chat_user(ctx)
        application = ctx.deps.agent.application
        CoreHandler().check_permissions(
            user,
            UpdateAgentTriggerOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )
        trigger = AgentTriggerHandler().get_trigger(trigger_id)
        if trigger.application_id != application.id:
            raise AgentTriggerDoesNotExist()
        AgentTriggerHandler().delete_trigger(trigger)
        broadcast_configuration_updated(application)
        return {"success": True}

    try:
        return await sync_to_async(remove)()
    except PermissionException:
        return _permission_error()
    except AgentTriggerDoesNotExist:
        return {"error": f"The trigger {trigger_id} does not exist for this agent."}


async def enable_own_tools(
    ctx: RunContext[AgentRunDeps],
    types: Annotated[
        list[str],
        Field(
            description=(
                "The tool types to enable: workspace (Baserow tools acting "
                "as the agent identity), workspace_search, web_search."
            )
        ),
    ],
    thought: _THOUGHT,
) -> dict:
    """
    Enables built-in tools for this agent, effective from the next
    conversation turn.
    """

    from ..models import AgentTool
    from ..operations import CreateAgentToolOperationType
    from ..realtime import broadcast_configuration_updated

    def enable():
        user = _chat_user(ctx)
        application = ctx.deps.agent.application
        CoreHandler().check_permissions(
            user,
            CreateAgentToolOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )

        invalid = [t for t in types if t not in TOGGLEABLE_TOOL_TYPES]
        if invalid:
            return {
                "error": f"Unknown tool types {invalid}. Valid types: "
                f"{TOGGLEABLE_TOOL_TYPES}."
            }

        for tool_type in types:
            AgentTool.objects.get_or_create(
                agent=ctx.deps.agent, type=tool_type, defaults={"config": {}}
            )
        broadcast_configuration_updated(application)
        return {"success": True}

    try:
        return await sync_to_async(enable)()
    except PermissionException:
        return _permission_error()


async def disable_own_tools(
    ctx: RunContext[AgentRunDeps],
    types: Annotated[list[str], Field(description="The tool types to disable.")],
    thought: _THOUGHT,
) -> dict:
    """
    Disables built-in tools for this agent, effective from the next
    conversation turn.
    """

    from ..models import AgentTool
    from ..operations import DeleteAgentToolOperationType
    from ..realtime import broadcast_configuration_updated

    def disable():
        user = _chat_user(ctx)
        application = ctx.deps.agent.application
        CoreHandler().check_permissions(
            user,
            DeleteAgentToolOperationType.type,
            workspace=application.workspace,
            context=application.application_ptr,
        )
        AgentTool.objects.filter(
            agent=ctx.deps.agent,
            type__in=[t for t in types if t in TOGGLEABLE_TOOL_TYPES],
        ).delete()
        broadcast_configuration_updated(application)
        return {"success": True}

    try:
        return await sync_to_async(disable)()
    except PermissionException:
        return _permission_error()


SELF_CONFIGURE_TOOL_FUNCTIONS = [
    update_own_instructions,
    list_available_models,
    update_own_model,
    add_own_trigger,
    list_own_triggers,
    remove_own_trigger,
    enable_own_tools,
    disable_own_tools,
]


def build_self_configure_toolset() -> FunctionToolset:
    return FunctionToolset(SELF_CONFIGURE_TOOL_FUNCTIONS, max_retries=3)

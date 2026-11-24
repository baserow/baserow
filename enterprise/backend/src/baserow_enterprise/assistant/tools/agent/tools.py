"""
Kuma tools that build, edit and test Agents through the services and actions the
Agent Builder's own API uses. Kuma never makes an Agent run by itself: triggers
are added turned off and only the user turns one on, and a tool that changes data
asks first until the user says otherwise in the Agent's Configuration.
"""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from django.conf import settings
from django.db import transaction

from pydantic import BaseModel, Field, ValidationError
from pydantic_ai import RunContext

from baserow.contrib.agent.action_tools.actions import (
    CreateAgentActionActionType,
    UpdateAgentActionActionType,
)
from baserow.contrib.agent.action_tools.exceptions import (
    AgentActionLimitReached,
    AgentActionTypeNotAvailable,
)
from baserow.contrib.agent.action_tools.service import AgentActionService
from baserow.contrib.agent.actions import (
    CreateAgentConversationActionType,
    UpdateAgentConfigurationActionType,
)
from baserow.contrib.agent.application_types import AgentApplicationType
from baserow.contrib.agent.constants import AgentReadinessState
from baserow.contrib.agent.exceptions import (
    AgentNotReady,
    AgentRunAsSubjectDoesNotExist,
)
from baserow.contrib.agent.models import AgentMessage, AgentReplyStatus
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.triggers.actions import (
    CreateAgentTriggerActionType,
    UpdateAgentTriggerActionType,
)
from baserow.contrib.agent.triggers.exceptions import (
    AgentTriggerNoAccess,
    AgentTriggerTypeNotAvailable,
)
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.agent.triggers.trigger_types import ROWS_TRIGGER_TYPES
from baserow.contrib.integrations.mcp.models import MCPServerTool
from baserow.core.chat_runs.exceptions import ChatRunLimitReached
from baserow.core.datetime import get_timezones
from baserow.core.formula.literals import wrap_static_string
from baserow.core.identities.actions import CreateIdentityActionType
from baserow.core.identities.exceptions import IdentityRoleDoesNotExist
from baserow.core.identities.handler import IdentityHandler
from baserow.core.models import Workspace
from baserow.core.services.exceptions import ServiceMisconfigured
from baserow.core.subjects import UserSubjectType
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import (
    create_application,
    update_application,
    visible_applications,
)
from baserow.core.tools.errors import format_validation_error
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset
from baserow_enterprise.assistant.types import AgentNavigationType

AGENT_TYPE = AgentApplicationType.type
SCHEDULE_TRIGGER = "periodic"
TRIGGER_TYPES = (*ROWS_TRIGGER_TYPES, "http_trigger", SCHEDULE_TRIGGER)
ACTION_TYPES = ("smtp_email", "http_request")
TEST_TITLE_PREFIX = "Test: "
# How long get_agent_test_result waits for the Agent to finish replying.
# Agent replies run on the same queue as Kuma's run, so the wait is kept short
# to not hold a worker the reply may need.
TEST_RESULT_WAIT_SECONDS = 10
TEST_RESULT_POLL_SECONDS = 1


@contextmanager
def _readable_errors() -> Iterator[None]:
    """
    Turn the Agent's own refusals into errors the model can explain or act on,
    instead of exceptions that end Kuma's run.

    :raises ToolInputError: For each refusal of the Agent's services.
    """

    try:
        yield
    except AgentNotReady as exc:
        raise ToolInputError(
            "The Agent isn't ready to reply: it needs instructions and an "
            "enabled model.",
            hint="Read get_agent for what is missing and set it with "
            "apply_agent_setup; models come from list_agent_tools. If no model is "
            "enabled, tell the user to enable one in the workspace's generative AI "
            "settings.",
        ) from exc
    except AgentTriggerNoAccess as exc:
        raise ToolInputError(
            "The Agent's identity can't read what this trigger watches.",
            hint="Run the Agent as an identity with access to the table, or "
            "watch a table it can read.",
        ) from exc
    except AgentTriggerTypeNotAvailable as exc:
        raise ToolInputError(
            f"The trigger type {exc} isn't available for this Agent.",
            hint="Use a trigger type from list_agent_tools.",
        ) from exc
    except (AgentActionTypeNotAvailable, AgentActionLimitReached) as exc:
        message = (
            str(exc)
            if isinstance(exc, AgentActionLimitReached)
            else f"The action type {exc} isn't available for this Agent."
        )
        raise ToolInputError(message) from exc
    except AgentRunAsSubjectDoesNotExist as exc:
        raise ToolInputError(
            "The identity to run as does not exist in this workspace or is trashed.",
            hint="Use an identity from get_agent or list_agents, or create one "
            "with new_identity.",
        ) from exc
    except ChatRunLimitReached as exc:
        raise ToolInputError(
            "The Agent is already running as many replies as it can.",
            hint="Tell the user to try the test again once one of them is done.",
        ) from exc
    except IdentityRoleDoesNotExist as exc:
        raise ToolInputError(
            "The new identity's role doesn't exist in this workspace.",
            hint="Use a role uid from list_agent_tools; MEMBER where the others "
            "don't exist.",
        ) from exc
    except ServiceMisconfigured as exc:
        raise ToolInputError(str(exc)) from exc
    except ValidationError as exc:
        raise ToolInputError(format_validation_error(exc)) from exc


class NewIdentity(BaseModel):
    name: str = Field(description="The identity's name, usually the Agent's name.")
    role: str = Field(
        description=(
            "The workspace role uid. BUILDER when the Agent may change data, "
            "VIEWER when it only reads; MEMBER where those roles don't exist."
        )
    )


class Schedule(BaseModel):
    interval: Literal["MINUTE", "HOUR", "DAY", "WEEK", "MONTH"] = "DAY"
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description="The minute past the hour; for MINUTE, every how many minutes.",
    )
    day_of_week: int | None = Field(
        default=None, ge=0, le=6, description="0 is Monday, for WEEK."
    )
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    timezone: str | None = Field(
        default=None,
        description="The IANA timezone hour and minute are in. Defaults to the "
        "user's timezone.",
    )


class TriggerSpec(BaseModel):
    type: Literal[TRIGGER_TYPES] = Field(  # type: ignore[valid-type]
        description=(
            "periodic runs on a schedule; local_baserow_rows_created/updated/"
            "deleted run when rows of table_id change; http_trigger runs on a "
            "webhook request."
        )
    )
    table_id: int | None = Field(
        default=None, description="The watched table, for a row trigger."
    )
    schedule: Schedule | None = Field(default=None, description="For periodic.")
    message: str = Field(
        default="",
        description="Leave blank so each run opens with the event, such as the "
        "rows that changed. Text here replaces the event, and the Agent no longer "
        "knows which rows changed.",
    )


class ActionSpec(BaseModel):
    type: Literal[ACTION_TYPES] = Field(  # type: ignore[valid-type]
        description="smtp_email sends an email; http_request calls a URL."
    )
    name: str = Field(description="The tool name the Agent calls, snake_case.")
    description: str = Field(default="", description="When the Agent should use it.")


class AgentSetup(BaseModel):
    """An Agent's setup, or the part of it to change. Unset values stay as they are."""

    name: str | None = Field(default=None, description="Required to create.")
    instructions: str | None = Field(
        default=None,
        description="What the Agent does, naming the real tables and fields.",
    )
    run_as_identity_id: int | None = Field(
        default=None, description="An existing identity the Agent acts as."
    )
    new_identity: NewIdentity | None = Field(
        default=None, description="Create an identity for the Agent to act as."
    )
    allowed_tools: list[str] | None = Field(
        default=None,
        description="Every tool the Agent may call, from list_agent_tools. A "
        "newly allowed tool that changes data asks first.",
    )
    provider_type: str | None = Field(
        default=None,
        description="With model_identifier, a model from list_agent_tools. Unset "
        "on a new Agent picks the first enabled model.",
    )
    model_identifier: str | None = None
    web_search_enabled: bool | None = None
    web_fetch_enabled: bool | None = Field(
        default=None,
        description="Only false: the user turns web fetch on in the Agent's "
        "Configuration.",
    )
    add_triggers: list[TriggerSpec] = Field(
        default_factory=list,
        description="Added turned off: the user turns a trigger on in the "
        "Agent's Configuration.",
    )
    turn_off_triggers: list[int] = Field(
        default_factory=list, description="The trigger_id of each trigger to turn off."
    )
    add_actions: list[ActionSpec] = Field(
        default_factory=list,
        description="Added turned off: the user enters credentials and the "
        "recipient or URL in the Agent's Configuration, then turns them on.",
    )


def _agent(ctx: RunContext[AssistantDeps], agent_id: int):
    agent = (
        visible_applications(ctx.deps.tool_context(), [AGENT_TYPE])
        .filter(id=agent_id)
        .first()
    )
    if agent is None:
        raise ToolInputError(
            f"Agent {agent_id} does not exist in this workspace.",
            hint="Call list_agents to read the Agent IDs.",
        )
    return agent.specific


def _user_timezone(user) -> str:
    """The user's timezone from their profile, or UTC when they have none."""

    return getattr(getattr(user, "profile", None), "timezone", None) or "UTC"


def _schedule_values(service) -> dict[str, Any] | None:
    """The schedule of a periodic trigger's service, in the form Schedule takes."""

    if getattr(service, "interval", None) is None:
        return None
    return {
        field: getattr(service, field)
        for field in (
            "interval",
            "hour",
            "minute",
            "day_of_week",
            "day_of_month",
            "timezone",
        )
    }


def _read_setup(user, agent) -> dict[str, Any]:
    """The Agent's current setup, in the form apply_agent_setup takes."""

    configuration = AgentService().get_configuration(user, agent.id)
    run_as = configuration.run_as
    triggers = AgentTriggerService().list_triggers(user, agent.id)
    actions = AgentActionService().list_actions(user, agent.id)
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "readiness": str(configuration.readiness),
        "readiness_errors": {
            field: str(code) for field, code in configuration.errors.items()
        },
        "instructions": configuration.instructions,
        "provider_type": configuration.provider_type,
        "model_identifier": configuration.model_identifier,
        "run_as": {"identity_id": run_as.subject_id, "name": run_as.name}
        if run_as.subject_id
        else None,
        "allowed_tools": configuration.allowed_tools,
        "ask_first_tools": configuration.ask_first_tools,
        "web_search_enabled": configuration.web_search_enabled,
        "web_fetch_enabled": configuration.web_fetch_enabled,
        "triggers": [
            {
                "trigger_id": trigger.id,
                "type": trigger.service.get_type().type,
                "name": trigger.name,
                "enabled": trigger.enabled,
                "table_id": getattr(trigger.service.specific, "table_id", None),
                "schedule": _schedule_values(trigger.service.specific),
            }
            for trigger in triggers
        ],
        "actions": [
            {
                "action_id": action.id,
                "type": action.service.get_type().type,
                "name": action.name,
                "enabled": action.enabled,
                "ask_first": action.ask_first,
            }
            for action in actions
        ],
    }


def _enabled_models(workspace: Workspace) -> list[dict[str, str]]:
    """The models an Agent of the workspace can reply with, as the Agent UI lists."""

    return [
        {"provider_type": provider_type, "model_identifier": identifier}
        for provider_type, identifiers in AgentApplicationType._enabled_models(
            workspace
        ).items()
        for identifier in identifiers
    ]


def _check_model(
    workspace: Workspace, current: dict[str, Any] | None, setup: AgentSetup
) -> None:
    """
    :param workspace: The chat's workspace.
    :param current: The Agent's setup now, or None for a new Agent.
    :param setup: The proposed change.
    :raises ToolInputError: When the change sets a model that isn't enabled for
        Agents in the workspace.
    """

    if not setup.provider_type and not setup.model_identifier:
        return
    provider_type = setup.provider_type or (current or {}).get("provider_type")
    model_identifier = setup.model_identifier or (current or {}).get("model_identifier")
    enabled = _enabled_models(workspace)
    if {"provider_type": provider_type, "model_identifier": model_identifier} in (
        enabled
    ):
        return
    if not enabled:
        raise ToolInputError(
            "No model is enabled for Agents in this workspace.",
            hint="Leave provider_type and model_identifier out, and tell the user "
            "to enable a model in the workspace's generative AI settings.",
        )
    raise ToolInputError(
        f"The model {model_identifier!r} of provider {provider_type!r} isn't "
        "enabled for Agents in this workspace.",
        hint="Pick provider_type and model_identifier together from: "
        + json.dumps(enabled),
    )


def _changes_data(name: str) -> bool:
    return (
        name in agent_tool_type_registry.get_types()
        and agent_tool_type_registry.get(name).changes_data
    )


def _identity_label(workspace: Workspace, identity_id: int) -> str:
    """
    :param workspace: The chat's workspace, which the identity is looked up in.
    :param identity_id: The identity the Agent would run as.
    :return: The identity's name and role, for a refusal Kuma passes on.
    """

    identity = IdentityHandler().get_queryset(workspace).filter(id=identity_id).first()
    if identity is None:
        return f"identity {identity_id}"
    role = IdentityHandler.get_role_uid(identity)
    return f'the identity "{identity.first_name}" with the {role} role'


def _runs_by_itself(current: dict[str, Any], setup: AgentSetup) -> bool:
    """
    :param current: The Agent's setup now.
    :param setup: The proposed change.
    :return: Whether a trigger still starts the Agent after the change.
    """

    off = set(setup.turn_off_triggers)
    return any(
        trigger["enabled"] and trigger["trigger_id"] not in off
        for trigger in current["triggers"]
    )


def _acts_without_asking(current: dict[str, Any], setup: AgentSetup) -> bool:
    """
    :param current: The Agent's setup now.
    :param setup: The proposed change.
    :return: Whether, after the change, the Agent can open web pages or has a
        tool, action or MCP tool that changes data without asking first.
    """

    if current["web_fetch_enabled"] and setup.web_fetch_enabled is not False:
        return True

    allowed = (
        setup.allowed_tools
        if setup.allowed_tools is not None
        else current["allowed_tools"]
    )
    # A tool Kuma allows asks first, so only the ones the user freed count.
    asking = set(current["ask_first_tools"])
    if any(
        _changes_data(name) and name in current["allowed_tools"] and name not in asking
        for name in allowed
    ):
        return True
    # Actions are added turned off, so only the Agent's current ones count.
    if any(a["enabled"] and not a["ask_first"] for a in current["actions"]):
        return True
    return MCPServerTool.objects.filter(
        integration__application_id=current["agent_id"],
        integration__trashed=False,
        enabled=True,
        removed=False,
        changes_data=True,
        ask_first=False,
    ).exists()


def _unattended_changes(
    workspace: Workspace, current: dict[str, Any] | None, setup: AgentSetup
) -> list[str]:
    """
    Nobody watches an Agent a trigger starts, so Kuma doesn't change who it acts
    as, or what steers the web pages it opens and its unasked changes to data.

    :param workspace: The chat's workspace.
    :param current: The Agent's setup now, or None for a new Agent.
    :param setup: The proposed change.
    :return: In plain words, each part of the change that isn't made while a
        trigger starts the Agent. Empty when the whole change can be made.
    """

    if current is None or not _runs_by_itself(current, setup):
        return []
    changes = []
    current_identity = (current["run_as"] or {}).get("identity_id")
    if setup.new_identity:
        changes.append(
            f'run it as a new identity "{setup.new_identity.name}" with the '
            f"{setup.new_identity.role} role"
        )
    elif setup.run_as_identity_id and setup.run_as_identity_id != current_identity:
        changes.append(
            "run it as " + _identity_label(workspace, setup.run_as_identity_id)
        )
    if (
        setup.instructions is not None
        and setup.instructions != current["instructions"]
        and _acts_without_asking(current, setup)
    ):
        changes.append(
            "change its instructions, as it opens web pages or changes data "
            "without asking first"
        )
    return changes


def _ask_first(setup: AgentSetup, current: dict[str, Any] | None):
    """
    :param setup: The proposed change.
    :param current: The Agent's setup now, or None for a new Agent.
    :return: The ask first tools the change saves, or None to keep them: a tool
        the Agent already had keeps the user's choice, and a newly allowed tool
        that changes data asks first.
    """

    if setup.allowed_tools is None:
        return None
    before = set((current or {}).get("allowed_tools") or [])
    before_asking = set((current or {}).get("ask_first_tools") or [])
    return [
        name
        for name in setup.allowed_tools
        if (name in before and name in before_asking)
        or (name not in before and _changes_data(name))
    ]


def _check_schedule(schedule: Schedule) -> None:
    """
    :param schedule: A periodic trigger's schedule, with its timezone.
    :raises ToolInputError: When the periodic trigger would refuse it.
    """

    minimum = settings.INTEGRATIONS_PERIODIC_MINUTE_MIN
    if schedule.interval == "MINUTE" and schedule.minute < minimum:
        raise ToolInputError(
            f"For a MINUTE schedule, minute must be {minimum} or more.",
            hint="For MINUTE, minute is every how many minutes the Agent runs.",
        )
    if schedule.timezone not in get_timezones():
        raise ToolInputError(
            f"{schedule.timezone!r} is not a timezone.",
            hint="Use an IANA timezone name, such as Europe/Amsterdam or "
            "America/Los_Angeles.",
        )


def _with_schedule_timezones(setup: AgentSetup, timezone: str) -> AgentSetup:
    """
    Give each new periodic trigger a schedule in the user's timezone unless it
    names one, so the saved trigger runs at the time the user meant.

    :param setup: The proposed change.
    :param timezone: The user's timezone.
    :return: The change, with a schedule and timezone on every periodic trigger.
    :raises ToolInputError: When a schedule can't be saved.
    """

    triggers = []
    for spec in setup.add_triggers:
        if spec.type == SCHEDULE_TRIGGER:
            schedule = spec.schedule or Schedule()
            if not schedule.timezone:
                schedule = schedule.model_copy(update={"timezone": timezone})
            _check_schedule(schedule)
            spec = spec.model_copy(update={"schedule": schedule})
        triggers.append(spec)
    return setup.model_copy(update={"add_triggers": triggers})


def _trigger_values(spec: TriggerSpec) -> dict[str, Any]:
    if spec.type in ROWS_TRIGGER_TYPES:
        if not spec.table_id:
            raise ToolInputError(
                f"A {spec.type} trigger needs table_id.",
                hint="Call list_tables to read the table ID.",
            )
        return {"table_id": spec.table_id}
    if spec.type == SCHEDULE_TRIGGER:
        return spec.schedule.model_dump(exclude_none=True)
    return {}


def _apply(user, workspace, agent, setup: AgentSetup, ask_first) -> Any:
    """Apply the setup through the actions the Agent's Configuration uses."""

    run_as_id = setup.run_as_identity_id
    if setup.new_identity:
        identity = CreateIdentityActionType.do(
            user,
            workspace,
            name=setup.new_identity.name[:150],
            role_uid=setup.new_identity.role,
        )
        run_as_id = identity.id
    values: dict[str, Any] = {}
    for field in (
        "instructions",
        "provider_type",
        "model_identifier",
        "web_search_enabled",
        "web_fetch_enabled",
    ):
        value = getattr(setup, field)
        if value is not None:
            values[field] = value
    if run_as_id:
        values["run_as_subject_type"] = UserSubjectType.type
        values["run_as_subject_id"] = run_as_id
    if setup.allowed_tools is not None:
        values["allowed_tools"] = setup.allowed_tools
        values["ask_first_tools"] = ask_first or []
    if agent is None:
        if not setup.name:
            raise ToolInputError("A new Agent needs a name.")
        agent = create_application(
            _tool_ctx(user, workspace), AGENT_TYPE, setup.name
        ).specific
        if "provider_type" not in values:
            provider, model = AgentApplicationType._default_model(
                AgentApplicationType._enabled_models(workspace)
            )
            if provider:
                values["provider_type"] = provider
                values["model_identifier"] = model
    elif setup.name is not None:
        update_application(_tool_ctx(user, workspace), agent, name=setup.name)
    if values:
        UpdateAgentConfigurationActionType.do(user, agent.id, **values)
    for spec in setup.add_triggers:
        CreateAgentTriggerActionType.do(
            user,
            agent.id,
            spec.type,
            message=wrap_static_string(spec.message) if spec.message else "",
            enabled=False,
            service=_trigger_values(spec),
        )
    for trigger_id in setup.turn_off_triggers:
        UpdateAgentTriggerActionType.do(user, agent.id, trigger_id, enabled=False)
    for spec in setup.add_actions:
        action = CreateAgentActionActionType.do(
            user,
            agent.id,
            spec.type,
            name=spec.name,
            description=spec.description,
        )
        if action.enabled:
            UpdateAgentActionActionType.do(user, agent.id, action.id, enabled=False)
    return agent


def _undo(
    previous: dict[str, Any] | None, after: dict[str, Any], setup: AgentSetup
) -> dict[str, Any]:
    """
    :param previous: The Agent's setup before the change, or None for a new Agent.
    :param after: The Agent's setup after the change.
    :param setup: The change that was applied.
    :return: The change that puts back what can be put back, in the form
        apply_agent_setup takes, and in plain words what stays.
    """

    stays = []
    if setup.new_identity:
        stays.append(f'the identity "{setup.new_identity.name}" stays in the workspace')
    if previous is None:
        stays.append(
            f'the Agent "{after["name"]}" itself: the user can delete it from the '
            "sidebar"
        )
        return {"setup": {}, "cannot_undo": stays}

    change: dict[str, Any] = {}
    for field in (
        "name",
        "instructions",
        "provider_type",
        "model_identifier",
        "web_search_enabled",
        "web_fetch_enabled",
    ):
        if previous[field] == after[field]:
            continue
        if field == "web_fetch_enabled" and previous[field]:
            stays.append(
                "web fetch stays off: the user turns it on in the Agent's Configuration"
            )
            continue
        change[field] = "" if previous[field] is None else previous[field]
    if previous["allowed_tools"] != after["allowed_tools"]:
        change["allowed_tools"] = previous["allowed_tools"]
        stays += [
            f"{name} asks first now: the user turns that off in the Agent's "
            "Configuration"
            for name in previous["allowed_tools"]
            if name not in after["allowed_tools"]
            and _changes_data(name)
            and name not in previous["ask_first_tools"]
        ]
    if previous["run_as"] != after["run_as"]:
        if previous["run_as"]:
            change["run_as_identity_id"] = previous["run_as"]["identity_id"]
        else:
            stays.append(f'the Agent keeps running as "{after["run_as"]["name"]}"')
    enabled_before = {t["trigger_id"]: t["enabled"] for t in previous["triggers"]}
    for trigger in after["triggers"]:
        before = enabled_before.get(trigger["trigger_id"])
        if before is None:
            stays.append(f'the trigger "{trigger["name"]}" stays, turned off')
        elif before and not trigger["enabled"]:
            stays.append(
                f'the trigger "{trigger["name"]}" stays turned off: the user turns '
                "it on in the Agent's Configuration"
            )
    action_ids = {action["action_id"] for action in previous["actions"]}
    stays += [
        f'the action "{action["name"]}" stays, turned off'
        for action in after["actions"]
        if action["action_id"] not in action_ids
    ]
    return {"setup": change, "cannot_undo": stays}


def _tool_ctx(user, workspace) -> ToolContext:
    return ToolContext(user=user, workspace=workspace)


def list_agents(
    ctx: RunContext[AssistantDeps],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the Agents in the workspace with their triggers and tools.

    WHEN to use: Before creating an Agent (to reuse one with the same purpose) and to find the Agent to edit or test.
    RETURNS: Each Agent's ID, name, readiness, triggers, tools and actions.
    """

    user = ctx.deps.user
    return {
        "agents": [
            _read_setup(user, agent.specific)
            for agent in visible_applications(ctx.deps.tool_context(), [AGENT_TYPE])
        ]
    }


def get_agent(
    ctx: RunContext[AssistantDeps],
    agent_id: Annotated[int, Field(description="The Agent's ID from list_agents.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Read one Agent's full setup, in the form apply_agent_setup takes.

    WHEN to use: Before editing an Agent. Its run_as, triggers and actions are read only: to change them use run_as_identity_id, add_triggers and turn_off_triggers of apply_agent_setup.
    """

    return _read_setup(ctx.deps.user, _agent(ctx, agent_id))


def list_agent_tools(
    ctx: RunContext[AssistantDeps],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the tools an Agent in this workspace can be given, the models it can reply with, and the role uids a new identity can have.

    WHEN to use: Before choosing allowed_tools or a model. Give an Agent the smallest set of tools that does the job. An Agent needs one of the listed models to reply; when none is listed, no model is enabled for Agents in the workspace.
    """

    tools = AgentService().get_available_tools(ctx.deps.user, ctx.deps.workspace.id)
    return {
        "tools": [tool for tool in tools if not tool["deactivated"]],
        "models": _enabled_models(ctx.deps.workspace),
        "trigger_types": list(TRIGGER_TYPES),
        "action_types": list(ACTION_TYPES),
        "identity_roles": ["BUILDER", "EDITOR", "VIEWER", "MEMBER"],
    }


def apply_agent_setup(
    ctx: RunContext[AssistantDeps],
    setup: Annotated[AgentSetup, Field(description="The setup, or what to change.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
    agent_id: Annotated[
        int | None,
        Field(description="The Agent to edit, or null to create a new Agent."),
    ] = None,
) -> dict[str, Any]:
    """\
    Create an Agent, or edit one, in a single call that carries the whole change.

    WHEN to use: The user asks to build, change or revert an Agent. Put every part of the request in one call.
    HOW: Read list_agent_tools first; for an edit read get_agent. Grant the read tools the Agent needs to find its data, such as list_tables and list_table_rows, next to any tool that changes it. Default to read-only tools. Never ask for API keys, passwords or SMTP credentials: actions are added turned off for the user to configure.
    LIMITS: You can't make an Agent run by itself. A trigger is added turned off and you can't turn one on: tell the user to turn it on in the Agent's Configuration once they've checked the Agent. A newly allowed tool that changes data asks first, and only the user turns that off or turns web fetch on, both in the Configuration. While a trigger is on, a change to the Agent's identity or, when it opens web pages or changes data without asking, its instructions is refused: ask the user whether to turn the triggers off in the same call with turn_off_triggers, or to make the change in the Configuration.
    REVERT: To undo a change, call this tool with the revert.setup of that change's result, and tell the user what its revert.cannot_undo lists: added triggers and actions stay turned off, and a created Agent or identity stays.
    RETURNS: The Agent's setup before and after the change, and how to revert it.
    """

    user, workspace = ctx.deps.user, ctx.deps.workspace
    agent = _agent(ctx, agent_id) if agent_id else None
    current = _read_setup(user, agent) if agent else None
    setup = _with_schedule_timezones(setup, _user_timezone(user))
    _check_model(workspace, current, setup)
    if agent is None and not setup.name:
        raise ToolInputError("A new Agent needs a name.")
    if setup.web_fetch_enabled and not (current or {}).get("web_fetch_enabled"):
        raise ToolInputError(
            "Not applied. Kuma doesn't let an Agent open web pages.",
            hint="Leave web_fetch_enabled out and tell the user to turn web fetch "
            "on in the Agent's Configuration.",
        )
    has_identity = bool(
        setup.new_identity or setup.run_as_identity_id or (current or {}).get("run_as")
    )
    if setup.allowed_tools and not has_identity:
        raise ToolInputError(
            "Not applied. An Agent needs an identity to act as before it can "
            "have tools.",
            hint="Set run_as_identity_id or new_identity in the same call.",
        )
    refused = _unattended_changes(workspace, current, setup)
    if refused:
        raise ToolInputError(
            "Not applied. A trigger starts this Agent by itself, so Kuma doesn't "
            + "; ".join(refused)
            + ".",
            hint="Ask the user whether to turn its triggers off in the same call "
            "with turn_off_triggers, which they turn back on in the Agent's "
            "Configuration, or to make the change there themselves.",
        )
    ask_first = _ask_first(setup, current)
    with _readable_errors(), transaction.atomic():
        agent = _apply(user, workspace, agent, setup, ask_first)
    after = _read_setup(user, agent)
    ctx.deps.tool_helpers.navigate_to(
        AgentNavigationType(type="agent", agent_id=agent.id, agent_name=agent.name)
    )
    next_steps = (
        "Tell the user what the Agent does now. Name every trigger and action "
        "that is turned off and say the Agent doesn't run by itself until they "
        "turn the trigger on in the Agent's Configuration, where credentials for "
        "actions are entered too."
    )
    if after["readiness"] == AgentReadinessState.READY:
        next_steps += (
            " Offer a test: test_agent runs the Agent in a test conversation where "
            "every change asks first, while adding rows yourself changes the "
            "user's data."
        )
    else:
        missing = ", ".join(after["readiness_errors"]) or "its configuration"
        next_steps += (
            f" The Agent is saved but not ready, so it can't reply or run: {missing} "
            "is missing or unavailable. Say so plainly. "
            + (
                "Set the missing values with apply_agent_setup; models come from "
                "list_agent_tools."
                if _enabled_models(workspace)
                else "No model is enabled for Agents in this workspace: tell the "
                "user to enable one in the workspace's generative AI settings."
            )
        )
    return {
        "changed": after != current,
        "created": current is None,
        "previous_setup": current,
        "setup": after,
        "revert": _undo(current, after, setup),
        "next_steps": next_steps,
    }


def test_agent(
    ctx: RunContext[AssistantDeps],
    agent_id: Annotated[int, Field(description="The Agent to test.")],
    prompt: Annotated[
        str,
        Field(
            description="The message the test opens with. To test a row trigger, "
            "give a row from list_rows with its id, or say the row is a sample that "
            "isn't saved so the Agent says what it would do instead of looking it "
            "up."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Start a test conversation with an Agent. Every tool that changes data, and every action, asks first in it, so the test changes nothing without the user's say-so.

    WHEN to use: Whenever the user asks to test or try an Agent. Only a test shows what the Agent itself does: adding rows or doing its work with other tools shows your own work instead.
    RETURNS: The test conversation's ID. The Agent replies in the background: read the reply with get_agent_test_result.
    """

    agent = _agent(ctx, agent_id)
    with _readable_errors():
        result = CreateAgentConversationActionType.do(
            ctx.deps.user,
            agent.id,
            uuid4(),
            uuid4(),
            prompt,
            is_test=True,
            title=f"{TEST_TITLE_PREFIX}{prompt}",
        )
    return {
        "agent_id": agent.id,
        "conversation_uuid": str(result.conversation.uuid),
        "next_steps": "Call get_agent_test_result with this conversation_uuid to "
        "read the Agent's reply.",
    }


def get_agent_test_result(
    ctx: RunContext[AssistantDeps],
    agent_id: Annotated[int, Field(description="The tested Agent.")],
    conversation_uuid: Annotated[
        UUID, Field(description="The conversation_uuid test_agent returned.")
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Read the reply of a test conversation: its status, text, the tools it called and the calls waiting for approval.

    WHEN to use: After test_agent. It waits up to 10 seconds for the reply. When the status is still queued or running, call it once more; if it is still not done, tell the user to follow it in the test conversation.
    """

    agent_id = _agent(ctx, agent_id).id
    deadline = time.monotonic() + TEST_RESULT_WAIT_SECONDS
    while True:
        # The user can stop Kuma while it waits for the reply.
        ctx.deps.tool_helpers.raise_if_cancelled()
        conversation, messages = AgentService().list_messages(
            ctx.deps.user, agent_id, conversation_uuid
        )
        reply = (
            messages.filter(role=AgentMessage.Role.ASSISTANT).order_by("-id").first()
        )
        settled = reply is not None and reply.status not in (
            AgentReplyStatus.QUEUED,
            AgentReplyStatus.RUNNING,
        )
        if settled or time.monotonic() >= deadline:
            break
        time.sleep(TEST_RESULT_POLL_SECONDS)
    if reply is None:
        return {"status": AgentReplyStatus.QUEUED}
    return {
        "status": reply.status,
        "error_code": reply.error_code,
        "text": reply.content,
        "steps": [
            {
                key: step.get(key)
                for key in ("name", "status", "input", "error")
                if step.get(key) is not None
            }
            for step in (reply.steps or [])
            if isinstance(step, dict)
        ],
        "waiting_for_approval": [
            approval.tool_name
            for approval in reply.approvals.all()
            if approval.status == "pending"
        ],
        "is_test": conversation.is_test,
    }


TOOL_FUNCTIONS = [
    list_agents,
    get_agent,
    list_agent_tools,
    apply_agent_setup,
    test_agent,
    get_agent_test_result,
]
agent_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)

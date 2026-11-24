"""
Kuma tools that build, edit and test Agents through the services and actions the
Agent Builder's own API uses. Kuma never makes an Agent run by itself: triggers
are added turned off and only the user turns one on, a tool that changes data
asks first until the user says otherwise in the Agent's Configuration, and a new
identity gets the lowest role that covers the Agent's tools.
"""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field, ValidationError
from pydantic_ai import RunContext

from baserow.contrib.agent.action_tools.actions import (
    CreateAgentActionActionType,
    DeleteAgentActionActionType,
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
from baserow.contrib.agent.handler import AgentHandler
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentMessage,
    AgentReplyStatus,
)
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.service import AgentService
from baserow.contrib.agent.triggers.actions import (
    CreateAgentTriggerActionType,
    DeleteAgentTriggerActionType,
    UpdateAgentTriggerActionType,
)
from baserow.contrib.agent.triggers.exceptions import (
    AgentTriggerNoAccess,
    AgentTriggerTypeNotAvailable,
)
from baserow.contrib.agent.triggers.service import AgentTriggerService
from baserow.contrib.integrations.mcp.models import MCPServerTool
from baserow.core.chat_runs.exceptions import ChatRunLimitReached
from baserow.core.datetime import get_timezones
from baserow.core.exceptions import PermissionException
from baserow.core.formula.literals import wrap_static_string
from baserow.core.handler import CoreHandler
from baserow.core.identities.actions import CreateIdentityActionType
from baserow.core.identities.exceptions import IdentityRoleDoesNotExist
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.operations import CreateIdentityOperationType
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.identities.service import IdentityService
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

from .types import (
    ACTION_TYPES,
    SCHEDULE_TRIGGER,
    TRIGGER_TYPES,
    WEEKDAYS,
    AgentSetup,
    Schedule,
)

AGENT_TYPE = AgentApplicationType.type
# The lowest workspace role an identity needs for a tool, by what the tool does.
ROW_TOOLS = frozenset({"create_rows", "update_rows", "delete_rows"})
ROLES_BY_REACH = ("VIEWER", "COMMENTER", "EDITOR", "BUILDER", "ADMIN")
# Where roles need a licence the workspace lacks, members are builders.
ROLE_WITHOUT_ROLES = "MEMBER"
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
            hint="Use an identity from list_agent_tools, or create one with "
            "new_identity when it says the user can.",
        ) from exc
    except ChatRunLimitReached as exc:
        raise ToolInputError(
            "The Agent is already running as many replies as it can.",
            hint="Tell the user to try the test again once one of them is done.",
        ) from exc
    except IdentityRoleDoesNotExist as exc:
        raise ToolInputError(
            "The new identity's role doesn't exist in this workspace.",
            hint="Use an existing identity from list_agent_tools instead.",
        ) from exc
    except PermissionException as exc:
        raise ToolInputError(
            "Refused: the user's role in this workspace doesn't allow this. "
            "Building or changing an Agent needs the Builder role. Nothing was "
            "changed.",
            hint="Tell the user what they can't do; an admin can change their role.",
        ) from exc
    except ServiceMisconfigured as exc:
        raise ToolInputError(str(exc)) from exc
    except ValidationError as exc:
        raise ToolInputError(format_validation_error(exc)) from exc


def _agent(ctx: RunContext[AssistantDeps], agent_id: int) -> AgentApplication:
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


def _user_timezone(user: AbstractUser) -> str:
    """The user's timezone from their profile, or UTC when they have none."""

    return getattr(getattr(user, "profile", None), "timezone", None) or "UTC"


def _schedule_values(service: Any) -> dict[str, Any] | None:
    """The schedule of a periodic trigger's service, in the form Schedule takes."""

    if getattr(service, "interval", None) is None:
        return None
    values = {
        field: getattr(service, field)
        for field in ("interval", "hour", "minute", "day_of_month", "timezone")
    }
    day = service.day_of_week
    values["day_of_week"] = WEEKDAYS[day] if day is not None else None
    return values


def _read_setup(user: AbstractUser, agent: AgentApplication) -> dict[str, Any]:
    """The Agent's current setup: what apply_agent_setup changes."""

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
        "run_as": {
            "identity_id": run_as.subject_id,
            "name": run_as.name,
            "role": _identity_role(agent.workspace, run_as.subject_id),
        }
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


def _identity_role(workspace: Workspace, identity_id: int) -> str | None:
    """
    :param workspace: The chat's workspace, which the identity is looked up in.
    :param identity_id: An identity.
    :return: The identity's workspace role uid, or None when it isn't there.
    """

    identity = IdentityHandler().get_queryset(workspace).filter(id=identity_id).first()
    return IdentityHandler.get_role_uid(identity) if identity else None


def _identity_options(user: AbstractUser, workspace: Workspace) -> dict[str, Any]:
    """
    :param user: The chat's user.
    :param workspace: The chat's workspace.
    :return: Whether the user's role lets them create an identity, and the
        identities they may make an Agent act as.
    """

    can_create = CoreHandler().check_permissions(
        user,
        CreateIdentityOperationType.type,
        workspace=workspace,
        context=workspace,
        raise_permission_exceptions=False,
    )
    can_select = IdentityService().check_can_bind(
        user, workspace, raise_permission_exceptions=False
    )
    selectable = (
        [
            {
                "identity_id": identity.id,
                "name": identity.first_name,
                "role": IdentityHandler.get_role_uid(identity),
            }
            for identity in IdentityHandler().get_queryset(
                workspace, for_selection=True
            )
        ]
        if can_select
        else []
    )
    return {"can_create": can_create, "selectable": selectable}


def _check_identity(
    user: AbstractUser,
    workspace: Workspace,
    current: dict[str, Any] | None,
    setup: AgentSetup,
) -> None:
    """
    :param user: The chat's user.
    :param workspace: The chat's workspace.
    :param current: The Agent's setup now, or None for a new Agent.
    :param setup: The proposed change.
    :raises ToolInputError: When the user's role doesn't let them give the Agent
        the identity the change asks for, saying what they can do instead.
    """

    current_id = ((current or {}).get("run_as") or {}).get("identity_id")
    changes_identity = setup.new_identity or (
        setup.run_as_identity_id and setup.run_as_identity_id != current_id
    )
    if not changes_identity:
        return
    options = _identity_options(user, workspace)
    if setup.new_identity and not options["can_create"]:
        if options["selectable"]:
            raise ToolInputError(
                "Not applied. Only a workspace admin can create an identity.",
                hint="Ask the user which of these the Agent should act as and send "
                "it as run_as_identity_id, or they ask an admin for a new one: "
                + json.dumps(options["selectable"]),
            )
        raise ToolInputError(
            "Not applied. Only a workspace admin can create an identity, and the "
            "user may not choose one for an Agent either.",
            hint="Tell the user they need the Builder role to build Agents, and an "
            "admin to create the identity.",
        )
    if not setup.new_identity and not options["selectable"]:
        raise ToolInputError(
            "Not applied. The user may not choose the identity an Agent acts as.",
            hint="Tell the user they need the Builder role in the workspace.",
        )


def _lowest_role(workspace: Workspace, tools: list[str]) -> str:
    """
    :param workspace: The chat's workspace.
    :param tools: The tools the Agent is allowed after the change.
    :return: The lowest workspace role that covers the tools: one that reads, one
        that changes rows, or one that changes tables and fields.
    """

    changing = [name for name in tools if _changes_data(name)]
    if any(name not in ROW_TOOLS for name in changing):
        wanted = "BUILDER"
    elif changing:
        wanted = "EDITOR"
    else:
        wanted = "VIEWER"
    for role in ROLES_BY_REACH[ROLES_BY_REACH.index(wanted) :]:
        if role != "ADMIN" and identity_extension_type_registry.role_uid_exists(
            role, workspace
        ):
            return role
    return ROLE_WITHOUT_ROLES


def _role_warning(run_as: dict[str, Any] | None, needed: str) -> str | None:
    """
    :param run_as: The identity the Agent acts as after the change.
    :param needed: The lowest role that covers the Agent's tools.
    :return: What to tell the user when the identity's role is below it.
    """

    role = (run_as or {}).get("role")
    if role not in ROLES_BY_REACH or needed not in ROLES_BY_REACH:
        return None
    if ROLES_BY_REACH.index(role) >= ROLES_BY_REACH.index(needed):
        return None
    return (
        f'The identity "{run_as["name"]}" has the {role} role, but the Agent\'s '
        f"tools need {needed}: its calls will be refused until an admin raises the "
        "role or the Agent acts as another identity."
    )


def _runs_by_itself(current: dict[str, Any], setup: AgentSetup) -> bool:
    """
    :param current: The Agent's setup now.
    :param setup: The proposed change.
    :return: Whether a trigger still starts the Agent after the change.
    """

    off = {*setup.turn_off_triggers, *setup.remove_triggers}
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

    # A tool Kuma allows asks first, so only the ones the user freed count.
    asking = set(current["ask_first_tools"])
    if any(
        _changes_data(name) and name not in asking and name not in setup.revoke_tools
        for name in current["allowed_tools"]
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


def _unattended_changes(current: dict[str, Any] | None, setup: AgentSetup) -> list[str]:
    """
    Nobody watches an Agent a trigger starts, so Kuma doesn't change who it acts
    as, or what steers the web pages it opens and its unasked changes to data:
    its instructions and what it reads on the web.

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
        changes.append(f'run it as a new identity "{setup.new_identity.name}"')
    elif setup.run_as_identity_id and setup.run_as_identity_id != current_identity:
        changes.append("run it as another identity")
    if (
        setup.web_search_enabled
        and not current["web_search_enabled"]
        and _acts_without_asking(current, setup)
    ):
        changes.append(
            "let it search the web, as it opens web pages or changes data without "
            "asking first"
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


def _tools_after(current: dict[str, Any] | None, setup: AgentSetup) -> list[str]:
    """
    :param current: The Agent's setup now, or None for a new Agent.
    :param setup: The proposed change.
    :return: Every tool the Agent is allowed after the change: the tools the
        change doesn't name stay.
    :raises ToolInputError: When a granted tool doesn't exist.
    """

    known = agent_tool_type_registry.get_types()
    unknown = [name for name in setup.grant_tools if name not in known]
    if unknown:
        raise ToolInputError(
            f"These tools don't exist: {', '.join(unknown)}.",
            hint="Use tool names from list_agent_tools.",
        )
    allowed = (current or {}).get("allowed_tools") or []
    kept = [name for name in allowed if name not in setup.revoke_tools]
    return kept + [name for name in setup.grant_tools if name not in kept]


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
            schedule: Schedule = spec.schedule
            if not schedule.timezone:
                schedule = schedule.model_copy(update={"timezone": timezone})
            _check_schedule(schedule)
            spec = spec.model_copy(update={"schedule": schedule})
        triggers.append(spec)
    return setup.model_copy(update={"add_triggers": triggers})


def _apply(
    user: AbstractUser,
    workspace: Workspace,
    agent: AgentApplication | None,
    setup: AgentSetup,
    tools: list[str] | None,
    role_tools: list[str],
) -> AgentApplication:
    """
    Apply the setup through the actions the Agent's Configuration uses.

    :param user: The chat's user.
    :param workspace: The chat's workspace.
    :param agent: The Agent to change, or None to create one.
    :param setup: The change.
    :param tools: Every tool the Agent is allowed after the change, or None to
        leave its tools as they are.
    :param role_tools: The tools a new identity's role has to cover.
    :return: The Agent.
    """

    run_as_id = setup.run_as_identity_id
    if setup.new_identity:
        identity = CreateIdentityActionType.do(
            user,
            workspace,
            name=setup.new_identity.name,
            role_uid=_lowest_role(workspace, role_tools),
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
    if tools is not None:
        # Without ask first values the handler keeps each kept tool's setting
        # and makes a newly allowed tool that changes data ask first.
        values["allowed_tools"] = tools
    if agent is None:
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
    for trigger_id in setup.remove_triggers:
        DeleteAgentTriggerActionType.do(user, agent.id, trigger_id)
    for spec in setup.add_triggers:
        CreateAgentTriggerActionType.do(
            user,
            agent.id,
            spec.type,
            message=wrap_static_string(spec.message) if spec.message else "",
            enabled=False,
            service=spec.service_values(),
        )
    for trigger_id in setup.turn_off_triggers:
        if trigger_id not in setup.remove_triggers:
            UpdateAgentTriggerActionType.do(user, agent.id, trigger_id, enabled=False)
    for action_id in setup.remove_actions:
        DeleteAgentActionActionType.do(user, agent.id, action_id)
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
    granted = [n for n in after["allowed_tools"] if n not in previous["allowed_tools"]]
    revoked = [n for n in previous["allowed_tools"] if n not in after["allowed_tools"]]
    if granted:
        change["revoke_tools"] = granted
    if revoked:
        change["grant_tools"] = revoked
        stays += [
            f"{name} asks first now: the user turns that off in the Agent's "
            "Configuration"
            for name in revoked
            if _changes_data(name) and name not in previous["ask_first_tools"]
        ]
    if previous["run_as"] != after["run_as"]:
        if previous["run_as"]:
            change["run_as_identity_id"] = previous["run_as"]["identity_id"]
        else:
            stays.append(f'the Agent keeps running as "{after["run_as"]["name"]}"')
    enabled_before = {t["trigger_id"]: t["enabled"] for t in previous["triggers"]}
    kept = {t["trigger_id"] for t in after["triggers"]}
    stays += [
        f'the trigger "{trigger["name"]}" stays deleted: the user restores it from '
        "the trash"
        for trigger in previous["triggers"]
        if trigger["trigger_id"] not in kept
    ]
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
    kept_actions = {action["action_id"] for action in after["actions"]}
    stays += [
        f'the action "{action["name"]}" stays deleted: the user restores it from '
        "the trash"
        for action in previous["actions"]
        if action["action_id"] not in kept_actions
    ]
    stays += [
        f'the action "{action["name"]}" stays, turned off'
        for action in after["actions"]
        if action["action_id"] not in action_ids
    ]
    return {"setup": change, "cannot_undo": stays}


def _tool_ctx(user: AbstractUser, workspace: Workspace) -> ToolContext:
    return ToolContext(user=user, workspace=workspace)


def _summary(user: AbstractUser, agent: AgentApplication) -> dict[str, Any]:
    """
    :param user: The chat's user.
    :param agent: An Agent the user can see.
    :return: What tells Agents apart, without their instructions. Only the ID
        and name when the user may talk to the Agent but not read its setup.
    """

    try:
        setup = _read_setup(user, agent)
    except PermissionException:
        return {"agent_id": agent.id, "name": agent.name}
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "readiness": setup["readiness"],
        "run_as": setup["run_as"],
        "allowed_tools": setup["allowed_tools"],
        "triggers": [
            {key: trigger[key] for key in ("trigger_id", "type", "enabled")}
            for trigger in setup["triggers"]
        ],
        "actions": [action["name"] for action in setup["actions"]],
    }


def list_agents(
    ctx: RunContext[AssistantDeps],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the Agents in the workspace: a summary of each, without instructions.

    WHEN to use: Before creating an Agent (to reuse one with the same purpose) and to find the Agent the user names, to edit or test it. Read the full setup of one with get_agent.
    RETURNS: Each Agent's ID, name, readiness, identity, tools, triggers and action names.
    """

    ctx.deps.tool_helpers.update_status(_("Listing agents..."))
    user = ctx.deps.user
    return {
        "agents": [
            _summary(user, agent.specific)
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
    Read one Agent's full setup: instructions, model, identity, tools, triggers and actions.

    WHEN to use: Before editing an Agent. The result shows what is saved; apply_agent_setup takes changes to it: grant_tools and revoke_tools for allowed_tools, run_as_identity_id for run_as, add_triggers, turn_off_triggers and remove_triggers for triggers, add_actions and remove_actions for actions.
    """

    agent = _agent(ctx, agent_id)
    ctx.deps.tool_helpers.update_status(
        _("Reading agent %(name)s...") % {"name": agent.name}
    )
    with _readable_errors():
        return _read_setup(ctx.deps.user, agent)


def list_agent_tools(
    ctx: RunContext[AssistantDeps],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List what an Agent in this workspace can be given: the tools, the models it can reply with, the trigger and action types, and the identities it can act as.

    WHEN to use: Before building or changing an Agent. Give an Agent the smallest set of tools that does the job. An Agent needs one of the listed models to reply; when none is listed, no model is enabled for Agents in the workspace.
    IDENTITIES: identities.selectable are the ones the user may pick with run_as_identity_id. Only when identities.can_create is true can new_identity be used; its role is set for you, the lowest that covers the Agent's tools.
    """

    ctx.deps.tool_helpers.update_status(_("Listing what an agent can use..."))
    user, workspace = ctx.deps.user, ctx.deps.workspace
    with _readable_errors():
        tools = AgentService().get_available_tools(user, workspace.id)
    return {
        "tools": [tool for tool in tools if not tool["deactivated"]],
        "models": _enabled_models(workspace),
        "trigger_types": list(TRIGGER_TYPES),
        "action_types": list(ACTION_TYPES),
        "identities": _identity_options(user, workspace),
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
    ASK: Only when you can't tell which table the Agent works on, ask the user that one question with ask_user. Otherwise build straight away: how the Agent reads its event or decides goes in its instructions, not in a question.
    HOW: Read list_agent_tools first; for an edit find the Agent with list_agents and read it with get_agent. Grant the read tools the Agent needs to find its data, such as list_tables and list_table_rows, next to any tool that changes it. Default to read-only tools. An Agent with tools needs an identity: run_as_identity_id, or new_identity when the user can create one. Never ask for API keys, passwords or SMTP credentials: actions are added turned off for the user to configure.
    LIMITS: You can't make an Agent run by itself. A trigger is added turned off and you can't turn one on: tell the user to turn it on in the Agent's Configuration once they've checked the Agent. A tool you grant that changes data asks first, every time it is called, and only the user turns that off or turns web fetch on, both in the Configuration. While a trigger is on, a change to the Agent's identity or, when it opens web pages or changes data without asking, its instructions is refused: ask the user whether to turn the triggers off in the same call with turn_off_triggers, or to make the change in the Configuration.
    REVERT: To undo a change, call this tool with the revert.setup of that change's result, and tell the user what its revert.cannot_undo lists: added triggers and actions stay turned off, and a created Agent or identity stays.
    RETURNS: The Agent's setup before and after the change, and how to revert it.
    """

    user, workspace = ctx.deps.user, ctx.deps.workspace
    agent = _agent(ctx, agent_id) if agent_id is not None else None
    ctx.deps.tool_helpers.update_status(
        _("Changing agent %(name)s...") % {"name": agent.name}
        if agent
        else _("Building agent %(name)s...") % {"name": setup.name or ""}
    )
    with _readable_errors():
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
    tools_after = _tools_after(current, setup)
    tools = tools_after if setup.grant_tools or setup.revoke_tools else None
    gets_identity = setup.new_identity or setup.run_as_identity_id
    if agent and gets_identity and not (current or {}).get("run_as"):
        # An imported Agent's tools wait for an identity. Sent as its tools, the
        # ones that change data come on asking first, like any tool Kuma allows.
        waiting = AgentHandler().get_pending_tool_configuration(agent)["allowed_tools"]
        if waiting:
            tools = tools_after = [
                name
                for name in (*waiting, *tools_after)
                if name not in setup.revoke_tools
            ]
            tools = tools_after = list(dict.fromkeys(tools))
    has_identity = bool(
        setup.new_identity or setup.run_as_identity_id or (current or {}).get("run_as")
    )
    if tools and not has_identity:
        raise ToolInputError(
            "Not applied. An Agent needs an identity to act as before it can "
            "have tools.",
            hint="Set run_as_identity_id or new_identity in the same call; "
            "list_agent_tools says which the user can use.",
        )
    _check_identity(user, workspace, current, setup)
    refused = _unattended_changes(current, setup)
    if refused:
        raise ToolInputError(
            "Not applied. A trigger starts this Agent by itself, so Kuma doesn't "
            + "; ".join(refused)
            + ".",
            hint="Ask the user whether to turn its triggers off in the same call "
            "with turn_off_triggers, which they turn back on in the Agent's "
            "Configuration, or to make the change there themselves.",
        )
    with _readable_errors(), transaction.atomic():
        agent = _apply(user, workspace, agent, setup, tools, tools_after)
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
    # An imported Agent's tools wait for an identity, then come on as set up.
    before_tools = (current or {}).get("allowed_tools") or []
    turned_on = [
        {"name": name, "asks_first": name in after["ask_first_tools"]}
        for name in after["allowed_tools"]
        if name not in before_tools and name not in setup.grant_tools
    ]
    if turned_on:
        next_steps += (
            " The Agent now acts as an identity, which turned on the tools it was "
            "set up with: name each one in tools_turned_on and whether it asks "
            "first."
        )
    warning = _role_warning(
        after["run_as"], _lowest_role(workspace, after["allowed_tools"])
    )
    if warning:
        next_steps += f" Tell the user: {warning}"
    if after["readiness"] == AgentReadinessState.READY:
        next_steps += (
            " You can offer a test, which runs the Agent in a test conversation "
            "where every change asks first. Only start one when the user asks."
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
        "tools_turned_on": turned_on,
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

    WHEN to use: Only when the user asks to test or try an Agent. Only a test shows what the Agent itself does: adding rows or doing its work with other tools shows your own work instead.
    RETURNS: The test conversation's ID and title. The Agent replies in the background: read the reply with get_agent_test_result.
    """

    agent = _agent(ctx, agent_id)
    ctx.deps.tool_helpers.update_status(
        _("Testing agent %(name)s...") % {"name": agent.name}
    )
    with _readable_errors():
        result = CreateAgentConversationActionType.do(
            ctx.deps.user,
            agent.id,
            uuid4(),
            uuid4(),
            prompt,
            is_test=True,
            title=_("Test: %(prompt)s") % {"prompt": prompt},
        )
    ctx.deps.tool_helpers.navigate_to(
        AgentNavigationType(type="agent", agent_id=agent.id, agent_name=agent.name)
    )
    return {
        "agent_id": agent.id,
        "conversation_uuid": str(result.conversation.uuid),
        "conversation_title": result.conversation.title,
        "next_steps": "Call get_agent_test_result with this conversation_uuid to "
        "read the Agent's reply.",
    }


def _after_test(status: str, waiting: list[str], title: str) -> str:
    """
    :param status: The status of the Agent's reply.
    :param waiting: The tools whose calls wait for the user's decision.
    :param title: The test conversation's title, which the user finds it by.
    :return: What Kuma tells the user for this end of a test.
    """

    where = f'the conversation "{title}" on the Agent\'s page'
    if status in (AgentReplyStatus.QUEUED, AgentReplyStatus.RUNNING):
        return (
            "The Agent is still replying. Call this tool once more; if it still "
            f"isn't done, tell the user to follow the reply in {where}."
        )
    if waiting:
        return (
            f"The Agent wants to call {', '.join(waiting)} and waits for the "
            f"user's decision. That is decided in {where}, not in this chat: tell "
            "the user to approve or reject it there. Don't ask them to approve it "
            "here."
        )
    if status == AgentReplyStatus.COMPLETED:
        return (
            "Report the Agent's reply as it is. If the reply asks a question, pass "
            f"the question on: the user answers it in {where}. Don't answer it "
            "yourself."
        )
    return (
        "The Agent's reply didn't complete. Tell the user the error, and that the "
        f"details are in {where}."
    )


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
    Read the reply of a test conversation: its status, text, the tools it called and the calls waiting for the user's decision.

    WHEN to use: After test_agent. It waits up to 10 seconds for the reply. Do what next_steps says for the state the test is in.
    """

    agent_id = _agent(ctx, agent_id).id
    ctx.deps.tool_helpers.update_status(_("Waiting for the agent's reply..."))
    deadline = time.monotonic() + TEST_RESULT_WAIT_SECONDS
    while True:
        # The user can stop Kuma while it waits for the reply.
        ctx.deps.tool_helpers.raise_if_cancelled()
        with _readable_errors():
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
        return {
            "status": AgentReplyStatus.QUEUED,
            "next_steps": _after_test(AgentReplyStatus.QUEUED, [], conversation.title),
        }
    waiting = [
        approval.tool_name
        for approval in reply.approvals.all()
        if approval.status == "pending"
    ]
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
        "waiting_for_approval": waiting,
        "is_test": conversation.is_test,
        "conversation_title": conversation.title,
        "next_steps": _after_test(reply.status, waiting, conversation.title),
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

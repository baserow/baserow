from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _

from loguru import logger
from pydantic_ai.exceptions import AgentRunError

from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    ServiceFilterTarget,
    describe_filter_state,
    describe_table,
    prepare_service_filters,
    resolve_service_filter_target,
    save_service_filter_operations,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterState,
    ServiceFilterValidationError,
)
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.exceptions import ServiceFilterGenerationFailed

from .agent import ServiceFilterAgentDeps, run_service_filter_agent
from .prompts import format_service_filter_prompt

if TYPE_CHECKING:
    from baserow_enterprise.assistant.model_profiles import (
        ResolvedAssistantModelProfile,
    )


@dataclass
class ServiceFilterRequestResult:
    target_kind: str
    target_id: int
    target_name: str
    changed: bool
    summary: str
    state: FilterState


def _formula_examples(user: AbstractUser, target: ServiceFilterTarget) -> Any | None:
    """
    Example data for what the target's formula values can read, so the agent sees
    the shape of the page parameters, user or previous node outputs.
    """

    if target.kind == "builder_data_source":
        from baserow_enterprise.assistant.tools.builder.agents import (
            BuilderFormulaContext,
        )

        context = BuilderFormulaContext(target.owner.page)
        context.load_data_source_filter_context()
        return context
    if target.kind == "automation_node":
        from baserow_enterprise.assistant.tools.automation.agents import (
            WorkflowExamples,
        )

        return WorkflowExamples(user).context_for(target.owner)
    return None


def _describe_examples(formula_examples: Any | None) -> dict[str, Any] | None:
    if formula_examples is None:
        return None
    return {
        "example_data": formula_examples.get_formula_context(),
        "metadata": formula_examples.get_context_metadata(),
    }


def run_service_filter_request(
    ctx: ToolContext,
    kind: str,
    target_id: int,
    instructions: str,
    model_profile: "ResolvedAssistantModelProfile",
    table_id: int | None = None,
) -> ServiceFilterRequestResult:
    """
    Adds, updates and deletes the filters of a Local Baserow service as described
    by the instructions, and saves them through the owner's undoable action.

    :param ctx: Who the request runs for, the workspace the target must belong
        to, and where progress is reported.
    :param kind: The kind of object owning the service.
    :param target_id: The id of that object.
    :param instructions: What to change, in the user's words.
    :param model_profile: The Kuma model profile to run on.
    :param table_id: The table picked in the editor. When the target's service has
        no table yet, the filters are made for it and it's saved with them.
    :raises ServiceFilterTargetDoesNotExist: When the target can't be found.
    :raises ServiceFilterTargetNotSupported: When its service can't be filtered.
    :raises ServiceFilterGenerationFailed: When no valid changes could be made, or
        they no longer apply because the filters were changed meanwhile.
    :raises PermissionException: When the user can't update the target.
    :return: What changed, and the resulting filters.
    """

    target = resolve_service_filter_target(ctx, kind, target_id, table_id=table_id)
    prepared = prepare_service_filters(ctx, target)
    table, filter_type_sets = describe_table(prepared)
    prompt = format_service_filter_prompt(
        target_name=target.name,
        table=table,
        filter_type_sets=filter_type_sets,
        current_filters=describe_filter_state(prepared.state, prepared.fields),
        formula_data_description=target.target_type.describe_formula_values(),
        formula_data=_describe_examples(_formula_examples(ctx.user, target)),
        timezone=ctx.timezone or "UTC",
        allow_filter_groups=target.target_type.supports_filter_groups,
        request=instructions,
    )

    ctx.update_status(_("Updating the filters of %(name)s...") % {"name": target.name})

    try:
        changes = run_service_filter_agent(
            prompt,
            ServiceFilterAgentDeps(prepared.state, prepared.validation),
            model_profile,
        )
    except (AgentRunError, TimeoutError) as exc:
        logger.warning("[assistant] service filter generation failed: {}", exc)
        raise ServiceFilterGenerationFailed(str(exc)) from exc

    try:
        changed, state = save_service_filter_operations(
            ctx, prepared, changes.operations
        )
    except ServiceFilterValidationError as exc:
        # The filters were changed meanwhile, and the changes no longer apply.
        logger.warning("[assistant] service filters changed during generation")
        raise ServiceFilterGenerationFailed(str(exc)) from exc
    return ServiceFilterRequestResult(
        target_kind=target.kind,
        target_id=target.owner.id,
        target_name=target.name,
        changed=changed,
        summary=changes.summary,
        state=state,
    )

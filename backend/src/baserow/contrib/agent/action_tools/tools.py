"""Bind configured actions to Agent tools."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from asgiref.sync import sync_to_async
from pydantic import ValidationError
from pydantic_ai import RunContext, Tool, ToolReturn
from pydantic_ai.exceptions import ApprovalRequired, ModelRetry

from baserow.contrib.agent.models import AgentAction
from baserow.contrib.agent.registries import (
    failed_call,
    input_shower,
    shield_tool_call,
)
from baserow.core.cache import local_cache
from baserow.core.db import with_usable_db_connection
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError

from .exceptions import AgentActionCallNotPrepared
from .inputs import build_input_model
from .registries import AgentActionType, agent_action_type_registry

RESOLVED_VALUES_METADATA_KEY = "resolved_values"
"""Where a held call keeps the values its approver reads, in the paused run."""


def get_approval_key(action: AgentAction) -> str:
    """
    :param action: The action, with its specific service.
    :return: A digest of what the model is told and of the configuration a call
        is sent with, its integration included, so an approval only applies while
        the action stays the same.
    """

    service = action.service
    integration = service.integration if service.integration_id else None
    payload = json.dumps(
        [
            action.id,
            action.name,
            action.description,
            action.inputs,
            ServiceHandler().export_service(service),
            integration
            and IntegrationHandler().export_integration(integration.specific),
        ],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class BoundActionTool:
    """
    One enabled action, offered to the model as a tool named after it. A call is
    resolved once: the values people read are the values it sends, also when it
    waits for approval in between.
    """

    action: AgentAction
    action_type: AgentActionType
    approval_key: str

    changes_data = True

    @classmethod
    def from_action(cls, action: AgentAction) -> "BoundActionTool":
        """
        Read everything a call needs now, as replies run outside a sync context.

        :param action: The action, with its agent and workspace.
        :return: The tool of the action as it is now.
        """

        action.service = action.service.specific
        return cls(
            action,
            agent_action_type_registry.get(action.service.get_type().type),
            get_approval_key(action),
        )

    @property
    def type(self) -> str:
        """
        :return: The name the model calls the action by.
        """

        return self.action.name

    @property
    def ask_first(self) -> bool:
        """
        :return: Whether each call waits for approval.
        """

        return self.action.ask_first

    @property
    def presentation_type(self) -> str:
        """
        :return: The stable type that presents the action's steps, whatever its name.
        """

        return self.action_type.type

    def get_step_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        :param arguments: The call's arguments.
        :return: Nothing: the step shows the resolved values once prepared.
        """

        return {}

    def get_tool(self, ctx: ToolContext) -> Tool:
        """
        :param ctx: Who the reply's other tools act for. An action acts through
            its own service instead.
        :return: The tool, whose input schema and validation are the action's inputs.
        """

        model = build_input_model(self.action.inputs)

        def validate(run_ctx: RunContext, /, **arguments: Any) -> None:
            try:
                model.model_validate(arguments)
            except ValidationError as exc:
                raise ModelRetry(str(exc)) from exc

        async def call(run_ctx: RunContext, /, **arguments: Any) -> ToolReturn:
            approved_values = None
            if run_ctx.tool_call_approved:
                approved_values = (run_ctx.tool_call_metadata or {}).get(
                    RESOLVED_VALUES_METADATA_KEY
                )
                if approved_values is None:
                    return failed_call(self, AgentActionCallNotPrepared())
            return await shield_tool_call(
                sync_to_async(self._call)(
                    arguments, input_shower(run_ctx), approved_values
                )
            )

        return Tool.from_schema(
            call,
            name=self.type,
            description=self.action.description,
            json_schema=model.model_json_schema(),
            takes_ctx=True,
            sequential=True,
            args_validator=validate,
        )

    def _prepare(
        self, arguments: dict[str, Any], show_input: Callable[[dict[str, Any]], None]
    ) -> dict[str, Any]:
        """
        Resolve a call once and show it.

        :param arguments: The validated arguments.
        :param show_input: Adds the readable request to the call's step.
        :return: The resolved values the call sends.
        :raises ToolInputError: When the arguments don't resolve to valid values.
        """

        try:
            resolved_values = self.action_type.prepare(self.action, arguments)
        except (
            InvalidContextContentDispatchException,
            InvalidContextDispatchException,
        ) as exc:
            raise ToolInputError(str(exc)) from exc
        show_input(self.action_type.get_preview(self.action, resolved_values))
        return resolved_values

    @with_usable_db_connection
    def hold_call(
        self,
        ctx: ToolContext,
        arguments: dict[str, Any],
        show_input: Callable[[dict[str, Any]], None],
    ) -> ToolReturn:
        """
        Hold a call for approval, keeping the resolved values its approver reads
        in the paused run so that the approved call sends exactly those.

        :param ctx: Who the reply's other tools act for, unused by an action.
        :param arguments: The validated arguments.
        :param show_input: Adds the readable request to the call's step.
        :return: The failure when the call can't be prepared: it then never
            waits nor runs.
        :raises ApprovalRequired: Otherwise, with the resolved values.
        """

        try:
            with local_cache.context():
                resolved_values = self._prepare(arguments, show_input)
        except Exception as exc:
            return failed_call(self, exc)
        raise ApprovalRequired(metadata={RESOLVED_VALUES_METADATA_KEY: resolved_values})

    @with_usable_db_connection
    def _call(
        self,
        arguments: dict[str, Any],
        show_input: Callable[[dict[str, Any]], None],
        approved_values: dict[str, Any] | None,
    ) -> ToolReturn:
        """
        Send a call, and answer an error the model can explain instead of failing
        the reply.

        :param arguments: The validated arguments.
        :param show_input: Adds the readable request to the call's step.
        :param approved_values: The values resolved when the call was held, for
            an approved call. Any other call is resolved now.
        :return: The service's result, or an ``error`` with its code as metadata.
        """

        try:
            with local_cache.context():
                if approved_values is None:
                    resolved_values = self._prepare(arguments, show_input)
                else:
                    resolved_values = approved_values
                    show_input(
                        self.action_type.get_preview(self.action, resolved_values)
                    )
                result = self.action_type.dispatch(self.action, resolved_values)
                return ToolReturn(return_value=result.data)
        except Exception as exc:
            return failed_call(self, exc)

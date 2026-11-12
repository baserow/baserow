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
from baserow.core.services.exceptions import (
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError

from .inputs import build_input_model
from .registries import AgentActionType, agent_action_type_registry


def get_approval_key(action: AgentAction) -> str:
    """
    :param action: The action, with its specific service.
    :return: A digest of what the model is told and what a call sends, so an
        approval only applies while the action stays the same.
    """

    payload = json.dumps(
        [
            action.id,
            action.name,
            action.description,
            action.inputs,
            ServiceHandler().export_service(action.service),
        ],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class BoundActionTool:
    """One enabled action, offered to the model as a tool named after it."""

    action: AgentAction
    action_type: AgentActionType
    approval_key: str

    changes_data = True

    @classmethod
    def from_action(cls, action: AgentAction) -> "BoundActionTool":
        """Read everything a call needs now, as replies run outside a sync context."""

        action.service = action.service.specific
        return cls(
            action,
            agent_action_type_registry.get(action.service.get_type().type),
            get_approval_key(action),
        )

    @property
    def type(self) -> str:
        return self.action.name

    @property
    def ask_first(self) -> bool:
        return self.action.ask_first

    @property
    def presentation_type(self) -> str:
        return self.action_type.type

    def get_step_input(self, arguments: dict[str, Any]) -> dict:
        # Values become readable once the service formulas are resolved.
        return {}

    def get_tool(self, ctx: ToolContext) -> Tool:
        model = build_input_model(self.action.inputs)

        def validate(run_ctx: RunContext, **arguments: Any) -> None:
            try:
                model.model_validate(arguments)
            except ValidationError as exc:
                raise ModelRetry(str(exc)) from exc

        async def call(run_ctx: RunContext, **arguments: Any) -> ToolReturn:
            return await shield_tool_call(
                sync_to_async(self._call)(arguments, input_shower(run_ctx))
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

    def _show_preview(
        self, arguments: dict[str, Any], show_input: Callable[[dict], None]
    ) -> None:
        try:
            show_input(self.action_type.get_preview(self.action, arguments))
        except (
            InvalidContextContentDispatchException,
            InvalidContextDispatchException,
        ) as exc:
            raise ToolInputError(str(exc)) from exc

    @with_usable_db_connection
    def hold_call(
        self,
        ctx: ToolContext,
        arguments: dict[str, Any],
        show_input: Callable[[dict], None],
    ) -> ToolReturn:
        try:
            with local_cache.context():
                self._show_preview(arguments, show_input)
        except Exception as exc:
            return failed_call(self, exc)
        raise ApprovalRequired()

    @with_usable_db_connection
    def _call(
        self, arguments: dict[str, Any], show_input: Callable[[dict], None]
    ) -> ToolReturn:
        try:
            with local_cache.context():
                self._show_preview(arguments, show_input)
                result = self.action_type.dispatch(self.action, arguments)
                return ToolReturn(return_value=result.data)
        except Exception as exc:
            return failed_call(self, exc)

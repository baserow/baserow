from abc import ABC, abstractmethod
from typing import Any, TypedDict

from pydantic_core import to_jsonable_python

from baserow.contrib.agent.models import AgentAction
from baserow.contrib.agent.previews import StepPreview, cut
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry
from baserow.core.services.types import DispatchResult

from .data_providers import AgentActionDispatchContext
from .formulas import get_formula_errors
from .inputs import AgentActionInput, build_input_model


class AgentActionDefaults(TypedDict):
    """What a new action of a type starts with. It is seeded once."""

    name: str
    description: str
    inputs: list[AgentActionInput]
    service: dict[str, Any]


class AgentActionType(Instance, ABC):
    """
    Offers an existing action service type as an Agent action, under the service
    type's name. The service owns its configuration and delivery. A type only
    supplies the starter of a new action and the request people read.
    """

    @property
    def service_type(self) -> ServiceType:
        """
        :return: The type of the service an action of this type owns.
        """

        return service_type_registry.get(self.type)

    def is_available(self, workspace: Workspace) -> bool:
        """
        :param workspace: The Agent's workspace.
        :return: Whether the service type can be used in that workspace.
        """

        return not self.service_type.is_deactivated(workspace)

    @abstractmethod
    def get_defaults(self) -> AgentActionDefaults:
        """
        Seed a new action. Bind the service formulas to the inputs by ID, with
        literal ``get('tool_input.<id>')`` paths, so a rename keeps the binding
        and a deleted input is detected without resolving the formula.

        :return: The starter name, instructions, inputs and service values.
        """

    @abstractmethod
    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Select what people read about a call, before they approve it and after it
        ran: an explicit allowlist of resolved values and fixed settings, in
        reading order. Never include credentials.

        :param service: The action's specific service.
        :param resolved_values: The service's resolved formulas, by field.
        :return: The readable request, by field.
        """

    def get_configuration_errors(self, action: AgentAction) -> dict[str, str]:
        """
        Check the saved configuration without resolving a formula or contacting
        the integration. An action with errors is not offered to the model.

        :param action: The action, with its agent and workspace.
        :return: An error code by field, empty when the action can be called.
        """

        service = action.service.specific
        errors = ServiceHandler().get_configuration_errors(service, action.agent_id)
        errors.update(get_formula_errors(service, action.inputs))
        if not self.is_available(action.agent.workspace):
            errors["type"] = "unavailable"
        return errors

    def prepare(self, action: AgentAction, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve the action's formulas once for a call, without any effect. The
        result is what people read and exactly what the call sends, also when it
        first waits for approval.

        :param action: The action called.
        :param arguments: The call's arguments, by input name.
        :return: The service's resolved formulas by field, as JSON values.
        """

        self.service_type.raise_if_deactivated(action.agent.workspace)
        values = (
            build_input_model(action.inputs)
            .model_validate(arguments)
            .model_dump(by_alias=True)
        )
        dispatch_context = AgentActionDispatchContext(
            workspace=action.agent.workspace,
            tool_inputs={item["id"]: values[item["name"]] for item in action.inputs},
        )
        return to_jsonable_python(
            self.service_type.resolve_service_formulas(
                action.service.specific, dispatch_context
            )
        )

    def get_preview(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        :param action: The action called.
        :param resolved_values: What ``prepare`` returned for the call.
        :return: The step input: the bounded ``values`` of the readable request,
            and ``truncated`` when part of it was left out.
        """

        values = self.get_preview_values(action.service.specific, resolved_values)
        bounded = cut(values)
        return StepPreview(names=bounded, truncated=bounded != values).to_input()

    def dispatch(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> DispatchResult:
        """
        Send a prepared call through the action's service, whose integration must
        belong to the Agent. The formulas are not resolved again.

        :param action: The action called.
        :param resolved_values: What ``prepare`` returned for the call.
        :return: The result of the service.
        """

        self.service_type.raise_if_deactivated(action.agent.workspace)
        service = action.service.specific
        return ServiceHandler().dispatch_service(
            service,
            AgentActionDispatchContext(
                workspace=action.agent.workspace,
                resolved_values={service.id: resolved_values},
            ),
            application_id=action.agent_id,
        )


class AgentActionTypeRegistry(Registry[AgentActionType]):
    name = "agent_action"


agent_action_type_registry = AgentActionTypeRegistry()

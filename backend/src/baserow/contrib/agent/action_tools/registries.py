from abc import ABC, abstractmethod
from typing import Any, TypedDict

from pydantic_core import to_jsonable_python

from baserow.contrib.agent.constants import ACTION_MAX_RESULT_CHARACTERS
from baserow.contrib.agent.models import AgentAction
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.models import Workspace
from baserow.core.registry import Instance, Registry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType, service_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.tools.results import fit_result
from baserow.core.types import Subject

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
    type's name unless ``service_type_name`` says otherwise. The service owns its
    configuration and delivery. A type only supplies the starter of a new action
    and whatever an Agent needs that the service type doesn't give.
    """

    service_type_name: str | None = None
    """The service type, when it isn't named like this type because types share it."""

    changes_data: bool = True
    """Whether a call acts on anything; a type that only reads sets it to False."""

    filters_read_inputs: bool = False
    """
    Whether the filter values of the type's service may read the call's inputs,
    which the editor then offers there.
    """

    acts_as_run_identity: bool = False
    """
    Whether a call acts as the Agent's run identity, like its triggers and
    workspace tools, instead of through an integration, which it then never has.
    """

    @property
    def service_type(self) -> ServiceType:
        """
        :return: The type of the service an action of this type owns.
        """

        return service_type_registry.get(self.service_type_name or self.type)

    def is_usable(self, workspace: Workspace) -> bool:
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

    def get_preview_values(
        self, service: Service, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Select what people read about a call, before they approve it and after it
        ran, in reading order. Never include credentials: a type whose formulas
        can hold one selects what is shown.

        :param service: The action's specific service.
        :param resolved_values: The service's resolved formulas, by field.
        :return: The readable request, by field: every resolved value by default.
        """

        return resolved_values

    def get_configuration_errors(
        self, action: AgentAction, identity: Subject | None = None
    ) -> dict[str, str]:
        """
        Check the saved configuration without resolving a formula or contacting
        the integration. An action with errors is not offered to the model.

        :param action: The action, with its agent and workspace.
        :param identity: The Agent's run identity, or None when it has none it can
            act as.
        :return: An error code by field, empty when the action can be called.
        """

        service = action.service.specific
        errors = ServiceHandler().get_configuration_errors(service, action.agent_id)
        errors.update(get_formula_errors(self.get_formulas(service), action.inputs))
        if not self.is_usable(action.agent.workspace):
            errors["type"] = "unavailable"
        if self.acts_as_run_identity and identity is None:
            errors["run_as"] = "required"
        return errors

    def get_formulas(self, service: Service) -> dict[str, BaserowFormulaObject]:
        """
        :param service: The action's specific service.
        :return: The formulas a call resolves, by service field.
        """

        return {
            formula.key: formula.formula
            for formula in self.service_type.formulas_to_resolve(service)
        }

    def get_configuration_errors_by_action(
        self, actions: list[AgentAction], identity: Subject | None = None
    ) -> dict[int, dict[str, str]]:
        """
        Check many actions of this type at once, for a type whose checks cost
        less together, like a permission check of each action's table.

        :param actions: Actions of this type, of one Agent, with their specific
            services.
        :param identity: The Agent's run identity, or None when it has none it can
            act as.
        :return: The errors of each action, by action id.
        """

        return {
            action.id: self.get_configuration_errors(action, identity)
            for action in actions
        }

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
        dispatch_context = AgentActionDispatchContext(
            workspace=action.agent.workspace,
            tool_inputs=self._get_tool_inputs(action, arguments),
        )
        return to_jsonable_python(
            self.service_type.resolve_service_formulas(
                action.service.specific, dispatch_context
            )
        )

    def _get_tool_inputs(
        self, action: AgentAction, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        :param action: The action called.
        :param arguments: The call's arguments, by input name.
        :return: The validated arguments by input ID, as formulas read them.
        """

        values = (
            build_input_model(action.inputs)
            .model_validate(arguments)
            .model_dump(by_alias=True)
        )
        return {item["id"]: values[item["name"]] for item in action.inputs}

    def get_held_values(
        self, action: AgentAction, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Select what a call waiting for approval keeps in the paused run.

        :param action: The action called.
        :param resolved_values: What ``prepare`` returned for the call.
        :return: The values kept, all of them unless the type hides some from
            the approver: those shouldn't be stored where the approval waits.
        """

        return resolved_values

    def complete_held_values(
        self,
        action: AgentAction,
        arguments: dict[str, Any],
        held_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Rebuild the values an approved call sends from what was kept.

        :param action: The action called, unchanged since the call was held.
        :param arguments: The call's arguments.
        :param held_values: What ``get_held_values`` kept.
        :return: The values to send.
        """

        return held_values

    def get_preview(
        self,
        action: AgentAction,
        resolved_values: dict[str, Any],
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        :param action: The action called.
        :param resolved_values: What ``prepare`` returned for the call.
        :param arguments: The call's arguments, by input name.
        :return: The step input: the readable request as the type selected it.
            Limiting what a call sends and what its preview shows is up to the type.
        """

        return {
            "values": self.get_preview_values(action.service.specific, resolved_values)
        }

    def get_tool_result(self, action: AgentAction, result: DispatchResult) -> Any:
        """
        :param action: The action called.
        :param result: What the service's dispatch returned.
        :return: What the model reads about the call, kept in the conversation:
            the service's result, cut to ``ACTION_MAX_RESULT_CHARACTERS`` as it's
            resent in every later turn.
        """

        return fit_result(to_jsonable_python(result.data), ACTION_MAX_RESULT_CHARACTERS)

    def dispatch(
        self,
        action: AgentAction,
        resolved_values: dict[str, Any],
        identity: Subject | None = None,
        arguments: dict[str, Any] | None = None,
    ) -> DispatchResult:
        """
        Send a prepared call through the action's service, whose integration must
        belong to the Agent. The formulas are not resolved again.

        :param action: The action called.
        :param resolved_values: What ``prepare`` returned for the call.
        :param identity: The Agent's run identity, which a type that acts as it
            sends the call as.
        :param arguments: The call's arguments, by input name, for the formulas a
            service only resolves while it is sent, like the filters of a table.
        :return: The result of the service.
        """

        self.service_type.raise_if_deactivated(action.agent.workspace)
        service = action.service.specific
        return ServiceHandler().dispatch_service(
            service,
            AgentActionDispatchContext(
                workspace=action.agent.workspace,
                tool_inputs=(
                    {}
                    if arguments is None
                    else self._get_tool_inputs(action, arguments)
                ),
                resolved_values={service.id: resolved_values},
                actor=identity if self.acts_as_run_identity else None,
            ),
            application_id=action.agent_id,
        )


class AgentActionTypeRegistry(Registry[AgentActionType]):
    name = "agent_action"


agent_action_type_registry = AgentActionTypeRegistry()

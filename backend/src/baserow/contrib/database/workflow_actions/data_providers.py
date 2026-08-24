from typing import TYPE_CHECKING, Any, Dict, List

from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType
from baserow.core.services.types import DispatchResult
from baserow.core.utils import get_value_at_path
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist
from baserow.core.workflow_actions.models import WorkflowAction

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class PreviousActionDataProviderType(DataProviderType):
    """
    Exposes what the earlier actions of a click returned, so a later action can
    use them (ADR 006 section 4).

    Results live on the dispatch context for the length of one request. The
    builder keys them into the cache because its browser dispatches one action
    at a time, and automation reads them from workflow history; a button runs
    its whole sequence in one call, so neither is needed here.
    """

    type = "previous_action"

    # In the context's cache rather than on the context itself: `clone()`
    # rebuilds through `__init__` and only copies the cache dict, so this is
    # what every clone shares.
    CACHE_KEY = "previous_action_results"

    # The actions those results came from, so a path can be prepared without
    # looking the action up again.
    ACTIONS_CACHE_KEY = "previous_action_instances"

    def post_dispatch(
        self,
        dispatch_context: "DatabaseDispatchContext",
        workflow_action: WorkflowAction,
        dispatch_result: DispatchResult,
    ) -> None:
        """
        Keeps what an action returned, so the actions after it can read it.

        :param dispatch_context: The context this dispatch runs in.
        :param workflow_action: The action that just ran.
        :param dispatch_result: What it returned.
        """

        results = dispatch_context.cache.get(self.CACHE_KEY)
        if results is None:
            # A context with no holder, such as an AI prompt's, has no sequence.
            return

        results[workflow_action.id] = dispatch_result.data
        dispatch_context.cache[self.ACTIONS_CACHE_KEY][workflow_action.id] = (
            workflow_action
        )

    def import_path(
        self, path: List[str], id_mapping: Dict[str, Any], **kwargs
    ) -> List[str]:
        """
        Points a reference at the imported copy of the action it names, and
        hands the rest of the path to that action's service.

        :param path: The action id, then the path into its result.
        :param id_mapping: The mapping built by the import.
        :return: The updated path.
        """

        from baserow.contrib.database.workflow_actions.handler import (
            DatabaseWorkflowActionHandler,
        )

        action_id, *rest = path

        if "database_workflow_actions" not in id_mapping:
            return [str(action_id), *rest]

        try:
            action_id = id_mapping["database_workflow_actions"][int(action_id)]
            workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
                action_id
            )
        except (KeyError, ValueError, WorkflowActionDoesNotExist):
            # An action outside this import. Left as it is, like the builder
            # and automation leave theirs.
            return [str(action_id), *rest]

        service = getattr(workflow_action, "service", None)
        if service is not None:
            rest = service.specific.get_type().import_path(rest, id_mapping)

        return [str(action_id), *rest]

    def get_data_chunk(
        self, dispatch_context: "DatabaseDispatchContext", path: List[str]
    ) -> Any:
        """
        Reads a value out of what an earlier action of this click returned.

        :param dispatch_context: The context this dispatch runs in.
        :param path: The action id, then the path into its result.
        :raises InvalidFormulaContext: When the action is not one that has
            already run in this click.
        :return: The value at that path.
        """

        action_id, *rest = path

        try:
            action_id = int(action_id)
        except (TypeError, ValueError):
            # A client id that escaped the editor's substitution.
            raise InvalidFormulaContext(
                f'"{action_id}" is not a workflow action id.'
            ) from None

        results = dispatch_context.cache.get(self.CACHE_KEY) or {}

        if action_id not in results:
            # Not this button's action, or it sits after this one. Fail the
            # click rather than resolve to nothing.
            raise InvalidFormulaContext(
                "The previous action has not run in this click."
            )

        result = results[action_id]
        workflow_action = (
            dispatch_context.cache.get(self.ACTIONS_CACHE_KEY) or {}
        ).get(action_id)
        if not rest:
            return result

        service = getattr(workflow_action, "service", None)

        if service is None:
            # A frontend-only action returns nothing to prepare a path through.
            return get_value_at_path(result, rest)

        service = service.specific
        service_type = service.get_type()

        if service_type.returns_list:
            if not isinstance(result, dict) or "results" not in result:
                raise InvalidFormulaContext(
                    "The previous action returned nothing to read."
                )
            result = result["results"]
            if len(rest) >= 2:
                index, *after = rest
                prepared_path = [
                    index,
                    *service_type.prepare_value_path(service, after),
                ]
            else:
                prepared_path = rest
            return get_value_at_path(result, prepared_path)

        # Turns `field_<id>` into the field name the result is keyed by, since
        # it was serialized with `user_field_names`.
        prepared_path = service_type.prepare_value_path(service, rest)

        if not isinstance(result, dict):
            # An action that produced no row, a delete for instance. Reading a
            # path out of it is a configuration error, not an empty value.
            raise InvalidFormulaContext("The previous action returned nothing to read.")

        if prepared_path[0] not in result:
            # The field was deleted after the reference was written. Failing
            # here is what stops the click writing a blank over real data.
            raise InvalidFormulaContext(
                f'"{rest[0]}" is not in the previous action\'s result.'
            )

        return get_value_at_path(result, prepared_path)

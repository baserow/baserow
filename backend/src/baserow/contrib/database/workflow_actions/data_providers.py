from typing import TYPE_CHECKING, Any, List

from baserow.core.formula.exceptions import InvalidFormulaContext
from baserow.core.formula.registries import DataProviderType
from baserow.core.services.types import DispatchResult
from baserow.core.utils import get_value_at_path
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

    # The dispatch context holds each action's result under this key, keyed by
    # action id. Placed in `self.cache` rather than on the context itself
    # because `clone()` rebuilds the context through `__init__` and only copies
    # the cache dict, so this is what every clone ends up sharing.
    CACHE_KEY = "previous_action_results"

    # The actions those results came from, keyed the same way. Kept so a path
    # can be prepared through the action's own service without looking the
    # action up again, which would be a query per formula reference.
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
            # A context that never made a holder, such as an AI prompt's, has
            # no sequence to chain and nothing to keep.
            return

        results[workflow_action.id] = dispatch_result.data
        dispatch_context.cache[self.ACTIONS_CACHE_KEY][workflow_action.id] = (
            workflow_action
        )

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
            # A client id that escaped the editor's substitution, or a path
            # written by hand.
            raise InvalidFormulaContext(
                f'"{action_id}" is not a workflow action id.'
            ) from None

        results = dispatch_context.cache.get(self.CACHE_KEY) or {}

        if action_id not in results:
            # Either the action does not belong to this button, or it sits
            # after this one and has not run. Both are configuration errors,
            # so fail the click rather than resolve to nothing.
            raise InvalidFormulaContext(
                "The previous action has not run in this click."
            )

        result = results[action_id]
        workflow_action = (
            dispatch_context.cache.get(self.ACTIONS_CACHE_KEY) or {}
        ).get(action_id)
        service = getattr(workflow_action, "service", None)

        if service is None:
            # A frontend-only action returns nothing to prepare a path through.
            return get_value_at_path(result, rest)

        service = service.specific
        service_type = service.get_type()

        if service_type.returns_list:
            result = result["results"]
            if len(rest) >= 2:
                index, *after = rest
                prepared_path = [
                    index,
                    *service_type.prepare_value_path(service, after),
                ]
            else:
                prepared_path = rest
        else:
            # Turns `field_<id>` into the field name the result is keyed by,
            # since it was serialized with `user_field_names`.
            prepared_path = service_type.prepare_value_path(service, rest)

        return get_value_at_path(result, prepared_path)

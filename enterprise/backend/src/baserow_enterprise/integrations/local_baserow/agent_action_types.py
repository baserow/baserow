from typing import Any
from uuid import uuid4

from baserow.contrib.agent.action_tools.formulas import reads_only_inputs
from baserow.contrib.agent.action_tools.registries import (
    AgentActionDefaults,
    AgentActionType,
)
from baserow.contrib.agent.constants import ACTION_MAX_RESULT_CHARACTERS
from baserow.contrib.agent.models import AgentAction
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.types import DispatchResult
from baserow.core.tools.results import fit_values, json_length
from baserow.core.types import Subject
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowSemanticSearch,
)
from baserow_enterprise.integrations.local_baserow.service_types import ROW_PROPERTY


class LocalBaserowSemanticSearchAgentActionType(AgentActionType):
    """
    Finds the rows of a table that match the meaning of what the model looks for,
    as the Agent's run identity.
    """

    type = "local_baserow_semantic_search"
    changes_data = False
    acts_as_run_identity = True

    def get_defaults(self) -> AgentActionDefaults:
        input_id = str(uuid4())
        return {
            "name": "semantic_search",
            "description": "Search the table for the rows that match the meaning "
            "of what you look for, also when they use other words. Phrase the "
            "query in natural language, as a short description of what you look "
            "for, rather than as keywords.",
            "inputs": [
                {
                    "id": input_id,
                    "name": "query",
                    "type": "string",
                    "description": "What to look for, in natural language.",
                    "required": True,
                }
            ],
            "service": {
                "search_query": BaserowFormulaObject.create(
                    f"get('tool_input.{input_id}')", mode="simple"
                )
            },
        }

    def get_preview_values(
        self, service: LocalBaserowSemanticSearch, resolved_values: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "table": service.table.name if service.table_id else None,
            "search_query": resolved_values.get("search_query", ""),
            "max_results": self.service_type.get_max_result_limit(service),
        }

    def get_tool_result(self, action: AgentAction, result: DispatchResult) -> Any:
        """
        :return: The rows found, best match first, as long as they fit in
            ``ACTION_MAX_RESULT_CHARACTERS``, as the model reads
            them in every later turn. The first row that doesn't fit is cut to
            the space left, and the rows after it are left out, so the best
            matches stay whole.
        """

        results = []
        space = ACTION_MAX_RESULT_CHARACTERS
        for item in result.data["results"]:
            size = json_length(item)
            if size > space:
                row = item[ROW_PROPERTY]
                # What the rest of the result takes, as the row's JSON is part of it.
                row_space = space - (size - json_length(row))
                cut_row = fit_values(row, row_space)
                if cut_row is not None:
                    results.append({**item, ROW_PROPERTY: cut_row})
                return {**result.data, "results": results, "truncated": True}
            results.append(item)
            space -= size
        return {**result.data, "results": results}

    def get_configuration_errors(
        self, action: AgentAction, identity: Subject | None = None
    ) -> dict[str, str]:
        """
        Also require a table the run identity can read, with a field that can be
        searched, and fixed filter values, as filters are resolved when the call
        is sent, without its inputs.

        :param action: The action, with its agent and workspace.
        :param identity: The Agent's run identity, or None when it has none it can
            act as.
        :return: An error code by field, empty when the action can be called.
        """

        return self.get_configuration_errors_by_action([action], identity)[action.id]

    def get_configuration_errors_by_action(
        self, actions: list[AgentAction], identity: Subject | None = None
    ) -> dict[int, dict[str, str]]:
        """
        Check whether the identity can read the actions' tables in one permission
        check, so that it doesn't cost a query per action.
        """

        if not actions:
            return {}
        readable_table_ids = self.service_type.get_subject_readable_table_ids(
            [action.service.specific for action in actions],
            identity,
            actions[0].agent.workspace,
        )
        return {
            action.id: self._get_configuration_errors(
                action, identity, readable_table_ids
            )
            for action in actions
        }

    def _get_configuration_errors(
        self,
        action: AgentAction,
        identity: Subject | None,
        readable_table_ids: set[int],
    ) -> dict[str, str]:
        """
        :param action: The action, with its agent and workspace.
        :param identity: The Agent's run identity, or None.
        :param readable_table_ids: The ids of the tables the identity may read.
        :return: An error code by field, empty when the action can be called.
        """

        errors = super().get_configuration_errors(action, identity)
        service = action.service.specific
        if not service.table_id:
            errors["table_id"] = "required"
        elif identity is not None:
            if service.table_id not in readable_table_ids:
                errors["table_id"] = "unavailable"
            elif not self._has_fields_to_search(service):
                errors["search_field_ids"] = "unavailable"
        if not self._are_filters_fixed(service):
            errors["filters"] = "fixed_value"
        return errors

    def _has_fields_to_search(self, service: LocalBaserowSemanticSearch) -> bool:
        """
        :param service: The action's service, with a table in reach.
        :return: Whether a call would find a field to search in, so that an action
            that would always fail isn't offered to the model.
        """

        try:
            self.service_type.get_fields_to_search(service)
        except ServiceImproperlyConfiguredDispatchException:
            return False
        return True

    def _are_filters_fixed(self, service: LocalBaserowSemanticSearch) -> bool:
        """
        :param service: The action's service.
        :return: Whether every filter value can be resolved without reading
            anything, so not even the call's inputs.
        """

        return all(
            reads_only_inputs(BaserowFormulaObject.to_formula(service_filter.value), [])
            for service_filter in service.service_filters_with_untrashed_fields
        )

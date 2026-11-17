from typing import Any
from uuid import uuid4

from baserow.contrib.agent.action_tools.formulas import reads_only_inputs
from baserow.contrib.agent.action_tools.registries import (
    AgentActionDefaults,
    AgentActionType,
)
from baserow.contrib.agent.models import AgentAction
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowSemanticSearch,
)


class LocalBaserowSemanticSearchAgentActionType(AgentActionType):
    """
    Finds the rows of a table that match the meaning of what the model looks for,
    through a Local Baserow integration of the Agent.
    """

    type = "local_baserow_semantic_search"
    changes_data = False

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

    def get_configuration_errors(self, action: AgentAction) -> dict[str, str]:
        """
        Also require the integration and the table the search reads through, as
        an Agent has no user to read with, and fixed filter values, as filters are
        resolved when the call is sent, without its inputs.

        :param action: The action, with its agent and workspace.
        :return: An error code by field, empty when the action can be called.
        """

        errors = super().get_configuration_errors(action)
        service = action.service.specific
        if not service.integration_id:
            errors["integration_id"] = "required"
        if not service.table_id:
            errors["table_id"] = "required"
        elif "integration_id" not in errors and not self._is_table_in_reach(service):
            errors["table_id"] = "unavailable"
        if not self._are_filters_fixed(service):
            errors["filters"] = "invalid"
        return errors

    def _is_table_in_reach(self, service: LocalBaserowSemanticSearch) -> bool:
        """
        :param service: The action's service, with a table.
        :return: Whether the table is neither trashed nor outside the workspace
            of the integration.
        """

        return not TrashHandler.item_has_a_trashed_parent(
            service.table, check_item_also=True
        ) and self.service_type.is_table_in_integration_workspace(service)

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

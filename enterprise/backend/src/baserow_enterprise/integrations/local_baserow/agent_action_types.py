from typing import Any
from uuid import uuid4

from baserow.contrib.agent.action_tools.action_types import (
    LocalBaserowAgentActionType,
)
from baserow.contrib.agent.action_tools.registries import AgentActionDefaults
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


class LocalBaserowSemanticSearchAgentActionType(LocalBaserowAgentActionType):
    """
    Finds the rows of a table that match the meaning of what the model looks for,
    as the Agent's run identity.
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

    def _get_configuration_errors(
        self,
        action: AgentAction,
        identity: Subject | None,
        readable_table_ids: set[int],
    ) -> dict[str, str]:
        """
        Also require a field that can be searched, so that an action that would
        always fail isn't offered to the model.
        """

        errors = super()._get_configuration_errors(action, identity, readable_table_ids)
        if "table_id" not in errors and identity is not None:
            try:
                self.service_type.get_fields_to_search(action.service.specific)
            except ServiceImproperlyConfiguredDispatchException:
                errors["search_field_ids"] = "unavailable"
        return errors

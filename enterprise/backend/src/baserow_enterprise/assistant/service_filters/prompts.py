import json
from typing import Any

from baserow.contrib.integrations.local_baserow.service_filters.guides import (
    FILTERS_COMBINE_GUIDE,
    OPERATIONS_GUIDE,
    VALUES_GUIDE,
)

_KUMA_RULES = """\
## Rules

- Only change what the request asks for. Leave every other filter and group as it
  is; don't delete and recreate a filter to change it, update it.
- When the request sets a condition on a field that an existing filter already
  constrains the same way (e.g. "Amount greater than 50" while "Amount higher_than
  10" exists, or "status is Done" while "Status is Todo" exists), update that filter
  instead of adding another one. Two filters comparing the same field the same way
  are almost never what the user wants.
- Only add a filter next to such an existing one when the request clearly asks for
  an additional condition, e.g. "also", "as well", "and also", or a range like
  "between 10 and 50".
- A condition on a field without a filter is added next to the existing filters:
  "filter by X", "only show X" and "add a filter" never remove the filters on other
  fields. Remove filters only when the request explicitly says so, e.g. "remove",
  "instead", "replace", "clear", "only this filter".
- Never touch a filter the request isn't about: don't change its field, type or
  value, and don't delete it.
- When several filter types fit, pick the one matching the request most precisely.
- When the request can't be done with the available fields, filter types or data,
  return no operations and explain why in the summary. Never guess a field.
- The summary is one short sentence in the language of the request, e.g. "Added a
  filter showing only rows where Status is Done."
- Use the given timezone in date filters, and only read the available data listed
  below in formula values.

Examples, with an existing filter 7 "Amount higher_than 10":
- "only show amounts over 50" → update_filter 7 with value "50".
- "only show done tasks" → add_filter on Status. Filter 7 is left as it is.
- "also only amounts below 1000" → add_filter "Amount lower_than 1000".
- "only show done tasks instead" → delete_filter 7, then add_filter on Status.
- "remove the amount filter" → delete_filter 7.
"""

SERVICE_FILTER_AGENT_INSTRUCTIONS = "\n".join(
    (
        "You change the filters of a data source reading rows from a Baserow "
        "table. You receive the table's fields, the current filters and a request, "
        "and you answer with the operations turning the current filters into the "
        "requested ones.\n",
        FILTERS_COMBINE_GUIDE,
        OPERATIONS_GUIDE,
        _KUMA_RULES,
        VALUES_GUIDE,
    )
)


def format_service_filter_prompt(
    *,
    target_name: str,
    table: dict[str, Any],
    filter_type_sets: dict[str, list[str]],
    current_filters: dict[str, Any],
    formula_data_description: str,
    formula_data: dict[str, Any] | None,
    timezone: str,
    request: str,
    allow_filter_groups: bool = True,
) -> str:
    """
    Builds the prompt describing the data source and the request.

    :param target_name: The name of the data source or node.
    :param table: The table and its fields.
    :param filter_type_sets: The compatible filter types, keyed by the set name the
        fields refer to.
    :param current_filters: The current filters and groups.
    :param formula_data_description: Which data formula values can read.
    :param formula_data: Example data and metadata formula values can read, if any.
    :param timezone: The timezone to use in date filters.
    :param request: The user's request.
    :param allow_filter_groups: Whether filter groups can be used.
    :return: The prompt.
    """

    sections = [
        f"## Data source\n\n{target_name}",
        f"## Table and fields\n\n{json.dumps(table, default=str)}",
        (
            "## Compatible filter types\n\nEach field's `filter_types` names one of "
            f"these sets:\n\n{json.dumps(filter_type_sets)}"
        ),
        f"## Current filters\n\n{json.dumps(current_filters, default=str)}",
        f"## Available data for formula values\n\n{formula_data_description}",
    ]
    if formula_data:
        sections.append(json.dumps(formula_data, default=str))
    if not allow_filter_groups:
        sections.append(
            "## Filter groups\n\nNot available for this data source: only add "
            "filters at the top level, combined with the top level filter type."
        )
    sections.append(f"## Timezone\n\n{timezone}")
    sections.append(f"## Request\n\n{request}")
    return "\n\n".join(sections)

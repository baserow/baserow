"""
How service filters work, written for the clients changing them. Shared by the tool
descriptions and the prompts built on them, so every client reads the same rules.
"""

FILTERS_COMBINE_GUIDE = """\
## How filters combine

- Filters at the top level (group null) are combined with the top level filter type:
  AND means all must match, OR means any must match.
- A group combines its own filters and nested groups with the group's filter type,
  and counts as one condition at the level it belongs to.
- To express "A and (B or C)": keep the top level as AND, add filter A at the top
  level, add a group with filter type OR, and add B and C to that group.
"""

OPERATIONS_GUIDE = """\
## Operations

- add_filter: field_id, type, value, value_is_formula, group.
- update_filter: filter_id plus only the properties that change.
- delete_filter: filter_id.
- add_group: group_id (a new unique reference, e.g. "new_group_1"), filter_type,
  parent_group. Then add its filters with add_filter and `group` set to the
  reference.
- update_group: group_id, filter_type.
- delete_group: group_id. Deleting a group also deletes its filters and nested groups.
- set_filter_type: filter_type of the top level.

Only use field ids of the table, and only a filter type compatible with the field.
"""

VALUES_GUIDE = """\
## Values

Raw values (value_is_formula false), by filter type:

- Text filters (equal, contains, starts_with, ...): the text.
- Number filters (higher_than, lower_than, length_is_lower_than, ...): a number.
- boolean: "1" for true, "0" for false.
- Select filters (single_select_equal, single_select_is_any_of,
  multiple_select_has, ...): the select option id, or several ids separated by
  commas for the "is any of" / "is none of" types. Never the option label.
- link_row_has / link_row_has_not: a row id of the linked table. link_row_contains:
  text.
- Date filters (date_is, date_is_before, date_is_after, date_is_within, ...):
  "{timezone}?{value}?{operator}". The operator is one of today, yesterday,
  tomorrow, one_week_ago, one_month_ago, one_year_ago, this_week, this_month,
  this_year, next_week, next_month, next_year, nr_days_ago, nr_weeks_ago,
  nr_months_ago, nr_years_ago, nr_days_from_now, nr_weeks_from_now,
  nr_months_from_now, nr_years_from_now, exact_date. The value is a YYYY-MM-DD date
  for exact_date, a number for the nr_* operators, and empty otherwise. Examples:
  "Europe/London?2024-05-01?exact_date", "UTC?7?nr_days_ago", "UTC??today".
- empty, not_empty, is_even_and_whole, has_empty_value, has_not_empty_value: no
  value.

Formula values (value_is_formula true) compute the value when the data source runs,
for example from a page parameter. Only use them for dynamic data, and only read the
data the data source's formula values can read, with get('<path>'), e.g.
get('page_parameter.id'). Wrap static parts in quotes and combine with concat(), e.g.
for a date filter: concat('UTC?', get('page_parameter.date'), '?exact_date').
"""

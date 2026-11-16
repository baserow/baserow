from baserow_enterprise.assistant.tools.shared.formula_prompt import FORMULA_LANGUAGE

GENERATE_FORMULA_PROMPT = (
    FORMULA_LANGUAGE
    + """
## Context: Automation Workflows

In automation formulas, data is accessed through the previous_node structure:
- Each node's context_metadata gives its formula_path. Read its data with get('<formula_path>.<field_name>'). A node that outputs a list of rows, such as a row trigger, has a formula_path ending in .0 (its first, and usually only, row); other nodes are read without an index.
- A node that creates or updates a row (node_type local_baserow_create_row or local_baserow_update_row) outputs that one row. Its `id` is the ID of the row it created or updated, so "the row created by <node>" is get('<its formula_path>.id'), never the trigger's row.

**Example 1 - String Fields:**
Input:
fields_to_resolve: {
    "ai_prompt": "Determine the priority level based on {{ trigger.title }} and {{ trigger.due_date }}. Choices are: High, Medium, Low.",
}
context: {"previous_node": {"1": [{"title": "Finish report", "due_date": "2025-11-08"}]}}
context_metadata: {
    "1": {"id": 1, "ref": "trigger", "formula_path": "previous_node.1.0", "field_1": {"name": "title", "type": "string"}, "field_2": {"name": "due_date", "type": "date"}},
    "today": "2025-11-07"
}
feedback: ""
Output:
generated_formula: {
    "ai_prompt": "concat(
        'Determine the priority level based on ',
        get('previous_node.1.0.title'),
        ' and ',
        get('previous_node.1.0.due_date'),
        '. Choices are: High, Medium, Low.'
    )"
}
**Example 2 - Router Conditions:**
Input:
fields_to_resolve: {
    "condition_1": "Check if {{ trigger.amount }} is greater than 1000",
}
context: {"previous_node": {"1": [{"amount": 1500}]}},
context_metadata: {
    "1": {"id": 1, "ref": "trigger", "formula_path": "previous_node.1.0", "field_1": {"name": "amount", "type": "number"}},
}
feedback: ""
Output:
generated_formula: {
    "condition_1": "greater_than(get('previous_node.1.0.amount'), 1000)"
}

**Task:**

You are given:
* **fields_to_resolve** — a dictionary where each key identifies a field (a name, or a field ID whose value describes the field) and each value contains instructions to generate a formula.
* **context** — a dictionary containing the available data.
* **context_metadata** — a dictionary describing the structure and types within the context.
* **feedback** — optional information with reported formula errors from previous runs.

**Goal:**
Generate a dictionary called **generated_formula**, where:

* Keys are copied exactly from **fields_to_resolve**, including field IDs such as `892`.
* Values are valid formulas that can be used in the automation node.

**Rules:**

1. Feel free to skip fields whose description starts with `[optional]`.
2. Exclude any field if you cannot generate a valid formula for it.
3. If **feedback** is provided, use it to refine or correct the generated formulas.
4. Strive to produce the most accurate and useful formulas possible based on the provided context and metadata.
"""
)

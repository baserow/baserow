"""
Builder-specific formula generation prompt.

Used by ``agents.py`` to configure the formula generator agent.
"""

from baserow_enterprise.assistant.tools.shared.formula_prompt import FORMULA_LANGUAGE

BUILDER_FORMULA_PROMPT = (
    FORMULA_LANGUAGE
    + """\

## Context: Application Builder

In builder formulas, data is accessed through these providers:

| Provider | Path format | Description |
|---|---|---|
| data_source | `data_source.<id>.field_<field_id>` | Single-row data source field |
| data_source (list) | `data_source.<id>.0.field_<field_id>` | First item of a list data source |
| data_source_context | `data_source_context.<id>.total_count` | List data source metadata |
| current_record | `current_record.field_<field_id>` | Current row inside repeat/table elements |
| page_parameter | `page_parameter.<param_name>` | URL page parameters |
| form_data | `form_data.<element_id>` | Form input values |
| user | `user.email`, `user.id`, `user.username`, `user.role`, `user.is_authenticated` | Current user info |

**Rules:**
1. Use context_metadata to find correct data source IDs and field IDs
2. Always use field_<id> format (e.g., field_123), NOT field names
3. For list data sources, access first item with .0 or use current_record inside collection elements
4. Skip fields marked with [optional] if no suitable data exists
5. If **feedback** is provided, use it to refine or correct the generated formulas
6. Return valid formulas that evaluate against the provided context

**Example:**
Input:
fields_to_resolve: {"value": "the product name from the products data source"}
context: {"data_source.5": [{"id": 1, "field_123": "Widget A", "field_124": 29.99}]}
context_metadata: {"data_source.5": {"name": "Products", "returns_list": true, "fields": {"field_123": {"id": 123, "name": "Name", "type": "text"}, "field_124": {"id": 124, "name": "Price", "type": "number"}}}}
Output:
generated_formulas: {"value": "get('data_source.5.0.field_123')"}
"""
)

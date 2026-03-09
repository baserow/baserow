"""
Prompt strings and templates for database sub-agents.
"""

# ---------------------------------------------------------------------------
# Agent instructions
# ---------------------------------------------------------------------------

FORMULA_AGENT_INSTRUCTIONS = (
    "Generates a Baserow formula based on the provided description and table schema. "
    "Always validate the formula using the get_formula_type tool before returning it."
)

SAMPLE_ROW_AGENT_INSTRUCTIONS = (
    "Create 5 realistic sample rows for each table using the "
    "create_rows tools provided. "
    "IMPORTANT: Fill EVERY field for every row. Do NOT leave any field "
    "empty or null unless the data genuinely requires it. "
    "Insertion order: start with tables that have NO link_row fields, "
    "so you have real row IDs to reference. "
    "Then create rows in dependent tables, using those IDs in link_row fields. "
    "Reply with a short summary when done."
)

# ---------------------------------------------------------------------------
# Prompt formatters
# ---------------------------------------------------------------------------


def format_formula_fixer_prompt(
    field_name: str,
    original_formula: str,
    schema: list[dict],
    formula_docs: str,
) -> str:
    return (
        f"Fix this formula for field '{field_name}': {original_formula}\n\n"
        f"Tables schema: {schema}\n\n"
        f"Formula documentation: {formula_docs}"
    )


def format_formula_generation_prompt(
    description: str,
    schema: list[dict],
    formula_docs: str,
) -> str:
    return (
        f"Description: {description}\n\n"
        f"Tables schema: {schema}\n\n"
        f"Formula documentation: {formula_docs}"
    )


def format_sample_rows_prompt(table_info: str, data_brief: str | None = None) -> str:
    prompt = (
        f"Create 5 sample rows for each of these tables:\n{table_info}"
        "\n\nREMINDER: Fill ALL fields for every row — especially link_row "
        "(relationship) fields. Use the row IDs returned by previous "
        "create_rows calls as values for link_row fields in dependent tables."
    )
    if data_brief:
        prompt += f"\n\nUser instructions for the data: {data_brief}"
    return prompt

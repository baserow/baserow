"""
Prompt strings and templates for database sub-agents.
"""

# ---------------------------------------------------------------------------
# Agent instructions
# ---------------------------------------------------------------------------

FORMULA_AGENT_INSTRUCTIONS = """\
You write Baserow formulas. `get_formula_type` compiles a formula against the real
table and returns its type, or an error explaining what is wrong. It is the only
authority on what the formula language can and cannot do — your memory is not.

For every field you are asked to produce:
1. Read the field types out of the schema in the prompt before writing anything. A
   field's type decides which functions will accept it.
2. Write a candidate formula, using only functions listed in the Function Reference
   of the formula documentation and obeying its Hard Rules.
3. When an argument's type is not one the function accepts, convert it rather than
   abandoning the approach. `totext(x)` accepts a value of any type. `tonumber(x)`
   accepts text, so `tonumber(totext(x))` reads a number out of a value of another
   type. `join(x, ', ')` collapses a list of values — a link, lookup or other array
   — into one string. `when_empty(x, fallback)` supplies a default. The Function
   Reference lists what each function accepts.
4. Call `get_formula_type` on that candidate. Never return a formula you have not
   validated in this run.
5. If it errors, the message names the problem and the fields available. Fix that
   specific argument and validate again.

Never state that Baserow "does not support" a conversion, a function or a field
type. If you believe a request cannot be expressed, prove it: at least one of your
validated attempts must have tried converting the argument types, and
`get_formula_type` must have rejected it. A belief that something is unsupported is
not a result.

Only then set `is_formula_valid=false`, and put the verbatim text of the last
`get_formula_type` rejection into `error_message`, together with the formulas you
tried. Do not paraphrase it and do not invent a reason — that text is what the
caller sees. A validated formula that covers most of the request is better than
refusing outright.
"""

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

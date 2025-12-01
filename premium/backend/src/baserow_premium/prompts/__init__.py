from functools import cache
from importlib.resources import read_text

INSTRUCTIONS = """
In the JSON below, you will fine the fields of the table where the formula is created.
When referencing a field using the `field` function, you're only allowed to reference these fields, the ones that are in the table. Field names can't be made up.
Below an array of the fields in the table in JSON format, where each item represents a field with some additional options.

```
{table_schema_json}
```

You're a Baserow formula generator, and you're only responding with the correct formula.
The formula you're generating can only contain function and operators available to the Baserow formula, not any other formula language.
It can only reference fields in the JSON described above, not other fields.

Generate a Baserow formula based on the following input: "{user_prompt}".
"""


@cache
def get_generate_formula_prompt():
    return "------------------".join(
        [
            get_formula_docs(),
            INSTRUCTIONS,
        ]
    )


@cache
def get_formula_docs():
    return read_text("baserow_premium.prompts", "formula_docs.md")

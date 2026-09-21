import ast
import re
from pathlib import Path

import pytest

from baserow.contrib.database.formula.registries import formula_function_registry
from baserow_premium.fields import handler as ai_field_handler
from baserow_premium.prompts import get_formula_docs, get_generate_formula_prompt

PROMPT_BUILDER = "get_generate_formula_prompt"
FUNCTION_REFERENCE_HEADING = "## Function Reference"
INLINE_CODE = re.compile(r"`([^`\n]+)`")
FUNCTION_CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")

# Parsed straight from the grammar as references, so they never reach the registry.
GRAMMAR_FUNCTIONS = frozenset({"field", "lookup"})


def _handler_format_keys() -> set[str]:
    """The keyword names the AI field handler passes when formatting the prompt."""

    handler_path = Path(ai_field_handler.__file__)
    for node in ast.walk(ast.parse(handler_path.read_text())):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        builder = node.func.value
        if (
            node.func.attr == "format"
            and isinstance(builder, ast.Call)
            and getattr(builder.func, "id", None) == PROMPT_BUILDER
        ):
            return {keyword.arg for keyword in node.keywords if keyword.arg is not None}

    pytest.fail(
        f"No `{PROMPT_BUILDER}().format(...)` call found in {handler_path}. Either the "
        "prompt is no longer formatted there, in which case this guard must follow the "
        "new consumer, or it is formatted with **kwargs and the keys can no longer be "
        "derived statically."
    )


def _registered_function_names() -> set[str]:
    return set(formula_function_registry.registry.keys()) | GRAMMAR_FUNCTIONS


def _documented_function_names(docs: str) -> set[str]:
    """The names in the first column of every Function Reference table."""

    _, heading, reference = docs.partition(FUNCTION_REFERENCE_HEADING)
    assert heading, (
        f"'{FUNCTION_REFERENCE_HEADING}' heading is gone from formula_docs.md, so this "
        "guard can no longer find the documented functions."
    )

    names = set()
    for line in reference.splitlines():
        if not line.startswith("|"):
            continue
        cell = line.split("|")[1].strip()
        if not cell or cell == "Functions" or set(cell) <= set("-: "):
            continue
        # Operator rows read "add `+`"; the function name is what precedes the operator.
        names.add(cell.split("`")[0].strip())
    return names


def _function_names_called_in_docs(docs: str) -> set[str]:
    """The names used in call form inside inline code, such as the Hard Rules examples.

    Only call form counts. The doc also names Excel functions like `countif` in prose,
    precisely to say they do not exist in Baserow.
    """

    return {
        match.group(1)
        for span in INLINE_CODE.findall(docs)
        for match in FUNCTION_CALL.finditer(span)
    }


def test_generate_formula_prompt_formats_with_the_keys_the_handler_passes():
    keys = _handler_format_keys()
    assert keys, f"{PROMPT_BUILDER}() is formatted without any keyword argument."

    values = {key: f"<<{key} sentinel>>" for key in keys}
    try:
        formatted = get_generate_formula_prompt().format(**values)
    except (KeyError, IndexError, ValueError) as exc:
        pytest.fail(
            f"{PROMPT_BUILDER}().format({', '.join(sorted(keys))}) raised "
            f"{type(exc).__name__}: {exc}. The prompt is the formula docs concatenated "
            "with INSTRUCTIONS, so a brace introduced anywhere in either piece is read "
            "as a placeholder and breaks AI formula generation at runtime."
        )

    for key, sentinel in sorted(values.items()):
        assert sentinel in formatted, (
            f"The prompt no longer substitutes '{key}'. The handler still passes it, so "
            "that data never reaches the model."
        )


def test_formula_docs_contain_no_literal_brace():
    docs = get_formula_docs()
    offenders = [
        f"line {number}: {line.strip()}"
        for number, line in enumerate(docs.splitlines(), start=1)
        if "{" in line or "}" in line
    ]

    assert not offenders, (
        "formula_docs.md must contain no literal brace: "
        f"{PROMPT_BUILDER}() concatenates it into a str.format() template that "
        f"{Path(ai_field_handler.__file__).name} formats, so every brace is read as a "
        "placeholder and an unknown one raises KeyError for every AI formula "
        "generation. Do not escape them as "
        "{{ }} either: the assistant reads the same file unformatted through "
        "get_formula_docs(), and the model would then see the doubled braces. Reword "
        "the text instead. Offending lines:\n" + "\n".join(offenders)
    )


def test_function_reference_only_documents_registered_functions():
    documented = _documented_function_names(get_formula_docs())
    assert len(documented) > 50, (
        f"Only {len(documented)} functions were parsed out of the Function Reference "
        "tables, so their layout changed and this guard checks almost nothing."
    )

    unknown = sorted(documented - _registered_function_names())
    assert not unknown, (
        f"The Function Reference documents {unknown}, which are not registered in "
        "backend/src/baserow/contrib/database/formula/ast/function_defs.py. A document "
        "whose job is to stop the model inventing functions must not invent any itself."
    )


def test_functions_used_in_doc_examples_are_registered():
    called = _function_names_called_in_docs(get_formula_docs())
    assert len(called) > 10, (
        f"Only {len(called)} called functions were parsed out of formula_docs.md, so "
        "the inline code examples changed shape and this guard checks almost nothing."
    )

    unknown = sorted(called - _registered_function_names())
    assert not unknown, (
        f"formula_docs.md shows {unknown} being called in its rules and examples, but "
        "they are not registered in "
        "backend/src/baserow/contrib/database/formula/ast/function_defs.py. Every "
        "formula the doc demonstrates must actually compile."
    )

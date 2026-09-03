"""Turn UI-added ("foreign") Phoenix dataset examples into ready-to-paste eval code.

`sync_datasets` preserves examples added from the Phoenix UI (a dataset
editor row, or a trace span's "Add Example to Dataset") instead of deleting
them. This module is the other half of that workflow: it reads a dataset's
foreign examples back out and formats them as a starting point for promoting
them to code — a `_register_docs_case` call for `kuma-docs` (docs.py's real
registration helper), or a commented JSON block for every other dataset,
where scenario and checks still have to be written by hand.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from phoenix.client import Client

_DOCS_HEADER = (
    "# Paste these into "
    "enterprise/backend/src/baserow_enterprise/assistant/evals/datasets/docs.py,\n"
    "# adjust the id and keywords, then `just b eval-sync` adopts them.\n"
)

_OTHER_HEADER = (
    "# UI-added examples for dataset {dataset!r} have no ready-made\n"
    "# registration helper here. Write a scenario + checks for each by hand,\n"
    "# register it with EvalCase, then `just b eval-sync` adopts them.\n"
)


def _is_foreign(example: dict[str, Any]) -> bool:
    return not bool(example.get("metadata", {}).get("case_id"))


def _kebab_slug(prompt: str, word_count: int = 6) -> str:
    words = re.findall(r"[A-Za-z0-9]+", prompt)[:word_count]
    return "-".join(word.lower() for word in words) or "example"


def _docs_snippet(example: dict[str, Any]) -> str:
    prompt = example.get("input", {}).get("prompt", "")
    metadata = example.get("metadata", {})
    keywords = metadata.get("expected_keywords") or ["TODO-keyword"]
    source_patterns = metadata.get("expected_source_patterns") or [
        "TODO-source-pattern"
    ]
    slug = _kebab_slug(prompt)
    reference_answer = example.get("output", {}).get("reference_answer")
    reference_line = (
        f"    reference_answer={reference_answer!r},\n" if reference_answer else ""
    )

    return (
        "_register_docs_case(\n"
        f"    {slug!r},  # -> docs/{slug} — TODO verify id\n"
        "    (\n"
        f"        {prompt!r}\n"
        "    ),\n"
        f"    {source_patterns!r},\n"
        f"    {keywords!r},\n"
        f"{reference_line}"
        ")\n"
    )


def _json_block(example: dict[str, Any]) -> str:
    body = json.dumps(
        {"input": example.get("input"), "metadata": example.get("metadata")},
        indent=2,
    )
    commented = "\n".join(f"# {line}" for line in body.splitlines())
    return f"{commented}\n# Write a scenario + checks for this example by hand.\n"


def export_foreign_examples(client: "Client", dataset_name: str) -> str:
    """Format every foreign (UI-added) example of a dataset as pasteable code."""

    dataset = client.datasets.get_dataset(dataset=dataset_name)
    foreign = [ex for ex in dataset.examples if _is_foreign(ex)]

    if not foreign:
        return f"# No UI-added examples found in dataset {dataset_name!r}.\n"

    if dataset_name == "kuma-docs":
        header = _DOCS_HEADER
        snippets = [_docs_snippet(example) for example in foreign]
    else:
        header = _OTHER_HEADER.format(dataset=dataset_name)
        snippets = [_json_block(example) for example in foreign]

    return header + "\n" + "\n\n".join(snippets) + "\n"

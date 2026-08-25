from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from baserow_enterprise.assistant.evals.registry import cases_by_dataset
from baserow_enterprise.assistant.evals.types import EvalCase

if TYPE_CHECKING:
    from phoenix.client import Client


def build_dataset_examples(cases: list[EvalCase]) -> list[dict[str, Any]]:
    """Build the Phoenix example payload for a dataset's cases.

    Sorted by case id so repeated syncs produce a deterministic payload.
    """

    return [
        {
            "id": case.id,
            "input": {"prompt": case.prompt},
            "output": (
                {"reference_answer": case.reference_answer}
                if case.reference_answer
                else {}
            ),
            "metadata": {
                **case.metadata,
                "case_id": case.id,
                "scenario": case.scenario,
                "mode": case.mode.value,
                "max_iters": case.max_iters,
                "max_tool_errors": case.max_tool_errors,
                "requires_knowledge_base": case.requires_knowledge_base,
                "check_names": case.metadata.get("check_names", []),
            },
        }
        for case in sorted(cases, key=lambda c: c.id)
    ]


def _is_code_owned(example: dict[str, Any]) -> bool:
    return bool(example.get("metadata", {}).get("case_id"))


def _fetch_existing_examples(
    client: "Client", dataset_name: str
) -> list[dict[str, Any]]:
    """Current Phoenix examples for a dataset, or `[]` if it doesn't exist yet."""

    try:
        dataset = client.datasets.get_dataset(dataset=dataset_name)
    except ValueError:
        return []
    return list(dataset.examples)


def _merge_foreign_examples(
    code_examples: list[dict[str, Any]], existing_examples: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int, int]:
    """Combine code cases with UI-added ("foreign") examples still on Phoenix.

    A foreign example is preserved verbatim — its fetched `id` is re-included
    (without `node_id`) so `create_dataset` matches and PATCHes it in place
    instead of deleting it — unless a code case's prompt has since adopted
    it, in which case the code case supersedes it.
    """

    code_prompts = {ex["input"].get("prompt", "").strip() for ex in code_examples}
    kept: list[dict[str, Any]] = []
    adopted = 0

    for example in existing_examples:
        if _is_code_owned(example):
            continue
        prompt = example.get("input", {}).get("prompt", "")
        if isinstance(prompt, str) and prompt.strip() in code_prompts:
            adopted += 1
            continue
        kept.append(
            {
                "id": example["id"],
                "input": example["input"],
                "output": example["output"],
                "metadata": example["metadata"],
            }
        )

    return code_examples + kept, len(kept), adopted


def _preserve_live_reference_answers(
    code_examples: list[dict[str, Any]], existing_examples: list[dict[str, Any]]
) -> int:
    """Keep a Phoenix-UI-curated reference answer when the code case sets none.

    `build_dataset_examples` regenerates every code-owned example's `output`
    fresh each sync, which would silently wipe a `reference_answer` someone
    curated directly on the Phoenix example. Matched by `case_id` (mirrors
    `_is_code_owned`), not by prompt, since these are the same example, not
    an adoption. When the live output is non-empty and the code case sets no
    reference answer, the live output wins; when code sets one, code wins.
    """

    live_output_by_case_id = {
        case_id: example["output"]
        for example in existing_examples
        if (case_id := example.get("metadata", {}).get("case_id"))
        and example.get("output")
    }
    preserved = 0
    for example in code_examples:
        if example["output"]:
            continue
        live_output = live_output_by_case_id.get(example["metadata"]["case_id"])
        if live_output:
            example["output"] = live_output
            preserved += 1
    return preserved


def sync_datasets(client: "Client") -> dict[str, int]:
    """Push every registered dataset to Phoenix, preserving UI-added examples.

    `create_dataset` replaces a dataset's examples wholesale (action=update),
    so code cases removed from the registry are deleted on Phoenix too. UI-added
    examples (no `case_id` in their metadata) are fetched first and merged back
    in so they survive the upload, unless a code case has since adopted them.
    """

    counts: dict[str, int] = {}
    for dataset_name, cases in cases_by_dataset().items():
        code_examples = build_dataset_examples(cases)
        existing = _fetch_existing_examples(client, dataset_name)
        preserved = _preserve_live_reference_answers(code_examples, existing)
        examples, kept, adopted = _merge_foreign_examples(code_examples, existing)

        client.datasets.create_dataset(name=dataset_name, examples=examples)
        counts[dataset_name] = len(examples)
        logger.info(
            f"Synced Phoenix dataset '{dataset_name}': {len(code_examples)} code "
            f"cases, {kept} foreign kept, {adopted} adopted, {preserved} references "
            f"preserved ({len(examples)} total)"
        )
    return counts

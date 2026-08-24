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
            "output": {},
            "metadata": {
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


def sync_datasets(client: "Client") -> dict[str, int]:
    """Push every registered dataset to Phoenix as a full-state upsert.

    `create_dataset` replaces a dataset's examples wholesale (action=update),
    so cases removed from the registry are deleted on Phoenix too.
    """

    counts: dict[str, int] = {}
    for dataset_name, cases in cases_by_dataset().items():
        examples = build_dataset_examples(cases)
        client.datasets.create_dataset(name=dataset_name, examples=examples)
        counts[dataset_name] = len(examples)
        logger.info(
            f"Synced Phoenix dataset '{dataset_name}' ({len(examples)} examples)"
        )
    return counts

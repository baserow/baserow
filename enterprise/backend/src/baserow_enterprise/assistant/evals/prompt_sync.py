from __future__ import annotations

import hashlib
from collections import Counter
from typing import TYPE_CHECKING

from loguru import logger

from baserow_enterprise.assistant.onboarding import ONBOARDING_SUGGESTIONS_INSTRUCTIONS
from baserow_enterprise.assistant.prompts import AGENT_SYSTEM_PROMPT
from baserow_enterprise.assistant.tools.automation.prompts import (
    GENERATE_FORMULA_PROMPT,
)
from baserow_enterprise.assistant.tools.builder.prompts import BUILDER_FORMULA_PROMPT
from baserow_enterprise.assistant.tools.database.prompts import (
    FORMULA_AGENT_INSTRUCTIONS,
    SAMPLE_ROW_AGENT_INSTRUCTIONS,
)
from baserow_enterprise.assistant.tools.search_user_docs.tools import (
    SEARCH_DOCS_INSTRUCTIONS,
)

if TYPE_CHECKING:
    from phoenix.client import Client
    from phoenix.client.types.prompts import PromptVersion

# Load-bearing agent instructions only; per-request formatter fragments are skipped.
SYNCED_PROMPTS: dict[str, str] = {
    "kuma-system-prompt": AGENT_SYSTEM_PROMPT,
    "kuma-database-formula-agent": FORMULA_AGENT_INSTRUCTIONS,
    "kuma-database-sample-rows-agent": SAMPLE_ROW_AGENT_INSTRUCTIONS,
    "kuma-builder-formula-agent": BUILDER_FORMULA_PROMPT,
    "kuma-automation-formula-agent": GENERATE_FORMULA_PROMPT,
    "kuma-search-docs-agent": SEARCH_DOCS_INSTRUCTIONS,
    "kuma-onboarding-suggestions-agent": ONBOARDING_SUGGESTIONS_INSTRUCTIONS,
}

# Phoenix prompt versions require a model/provider; never dispatched from here.
_PLACEHOLDER_MODEL = "gpt-4o"
_PLACEHOLDER_PROVIDER = "OPENAI"


def prompt_hashes() -> dict[str, str]:
    """Short content hash per synced prompt, for experiment metadata stamping."""

    return {
        identifier: hashlib.sha256(template.encode()).hexdigest()[:12]
        for identifier, template in SYNCED_PROMPTS.items()
    }


def _template_text(version: "PromptVersion") -> str:
    """Read back a fetched PromptVersion's stored text.

    ``PromptVersion`` has no public template accessor (see
    phoenix/client/types/prompts.py) — we always store a single system
    message with plain string content, so unwrap it the same way.
    """

    content = version._template["messages"][0]["content"]
    if isinstance(content, str):
        return content
    return "".join(
        part.get("text", "") for part in content if part.get("type") == "text"
    )


def sync_prompts(client: "Client") -> dict[str, str]:
    """Push every ``SYNCED_PROMPTS`` entry to Phoenix as a versioned prompt.

    Phoenix prompts are append-only: ``create`` adds a new version and never
    edits one in place, so a new version is only created when the identifier
    is missing or its stored text has drifted from the current constant —
    unrelated eval-sync runs shouldn't spam the version history.

    :return: ``{identifier: "created" | "updated" | "unchanged"}``.
    """

    from phoenix.client.types.prompts import PromptVersion

    results: dict[str, str] = {}
    for identifier, template in SYNCED_PROMPTS.items():
        try:
            existing = client.prompts.get(prompt_identifier=identifier)
        except ValueError:
            # The phoenix client surfaces a 404 as ValueError (Prompts.get).
            existing = None

        if existing is not None and _template_text(existing) == template:
            results[identifier] = "unchanged"
            continue

        client.prompts.create(
            name=identifier,
            version=PromptVersion(
                [{"role": "system", "content": template}],
                model_name=_PLACEHOLDER_MODEL,
                model_provider=_PLACEHOLDER_PROVIDER,
                template_format="NONE",
            ),
        )
        results[identifier] = "created" if existing is None else "updated"

    counts = Counter(results.values())
    logger.info(
        "Synced Phoenix prompts: {} created, {} updated, {} unchanged",
        counts.get("created", 0),
        counts.get("updated", 0),
        counts.get("unchanged", 0),
    )
    return results

import re
from dataclasses import dataclass

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage

from baserow_enterprise.assistant.action_memory import (
    MutationEvidence,
    get_mutation_evidence,
)
from baserow_enterprise.assistant.deps import AssistantDeps

_UNAVAILABLE_TOOL_PATTERNS = (
    re.compile(
        r"\btools?(?:\s+for\b.{0,100})?\s+"
        r"(?:(?:is|are)\s+(?:currently\s+)?not\s+available|"
        r"(?:isn't|aren't)\s+(?:currently\s+)?available)\s+"
        r"(?:in|under)\s+(?:this|the\s+current)\s+"
        r"(?:session|mode|context|tool\s*set)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bI\s+(?:do not|don't)\s+have\s+(?:access\s+to\s+)?(?:the\s+)?"
        r"(?:(?:required|necessary)\s+)?tools?\s+(?:in|under)\s+"
        r"(?:this|the\s+current)\s+(?:session|mode|context|tool\s*set)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?current\s+tool\s*set\s+"
        r"(?:(?:does|do)\s+not|doesn't|don't)\s+"
        r"(?:include|expose|provide)\b",
        re.IGNORECASE,
    ),
)
_CHANGE_VERBS = r"(?:created|updated|deleted|added|configured|set up|applied|completed)"
_COMPLETED_CHANGE_PATTERNS = (
    re.compile(
        rf"\bI(?:'ve| have)?\s+(?:successfully\s+)?{_CHANGE_VERBS}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:the|your)\s+.{{0,80}}\s+"
        rf"(?:(?:has|have) been|was|were)\s+(?:successfully\s+)?"
        rf"{_CHANGE_VERBS}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^\s*(?:done\b[\s:—-]*)?(?:successfully\s+)?{_CHANGE_VERBS}\b|"
        r"^\s*done\s*[.!]?\s*$",
        re.IGNORECASE,
    ),
)
_CLAUSE_BOUNDARY = re.compile(
    r"[.!?;\n]+|\b(?:although|but|however|though|while|yet)\b", re.IGNORECASE
)
_FAILED_WORK_PATTERN = re.compile(
    r"\b(?:errors?|failed|failure|incomplete|pending|remaining|"
    r"could(?:n't|n’t| not)|unable|wasn't|weren't|"
    r"not (?:applied|completed|configured|created|deleted|updated))\b",
    re.IGNORECASE,
)
_NO_ERROR_PATTERN = re.compile(r"\b(?:without|no)\s+errors?\b", re.IGNORECASE)
# Delete is excluded: destructive actions must stay behind user confirmation.
_HANDOFF_VERBS = r"(?:create|set up|configure|update|add|apply|complete)"
_ACTION_HANDOFF_PATTERNS = (
    re.compile(
        rf"\b(?:I am|I'm|we are|we're)\s+(?:now\s+)?ready to\s+{_HANDOFF_VERBS}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:let me know if you(?:'d| would) like me to|"
        rf"would you like me to)\s+(?:go ahead (?:and|to)\s+)?{_HANDOFF_VERBS}\b",
        re.IGNORECASE,
    ),
)
_ACTION_BLOCKER_PATTERN = re.compile(
    r"\b(?:need|require|requires|missing|once|after|when|until|blocked|"
    r"permission|cannot|can't|unable)\b",
    re.IGNORECASE,
)
_UNRELATED_HELP_PATTERN = re.compile(
    r"\b(?:anything else|another|additional|future|more help)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class _CompletionClaim:
    allow_partial: bool


def _looks_like_tool_call(answer: str) -> bool:
    stripped = answer.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].strip()
    head = stripped[:200]
    return stripped.startswith("{") and '"name"' in head and '"arguments"' in head


def _claims_current_tools_are_unavailable(answer: str) -> bool:
    return any(pattern.search(answer) for pattern in _UNAVAILABLE_TOOL_PATTERNS)


def _explains_unconfigured_documentation_search(
    ctx: RunContext[AssistantDeps] | None, answer: str
) -> bool:
    if ctx is None:
        return False
    catalog = getattr(ctx.deps, "tool_catalog", "")
    if not isinstance(catalog, str) or "search_user_docs" in catalog:
        return False

    normalized = answer.lower()
    names_documentation_search = any(
        name in normalized
        for name in ("search_user_docs", "documentation search", "docs search")
    )
    explains_configuration = "not configured" in normalized
    return names_documentation_search and explains_configuration


def _claims_completed_change(answer: str) -> bool:
    return any(pattern.search(answer) for pattern in _COMPLETED_CHANGE_PATTERNS)


def _defers_action_without_blocker(answer: str) -> bool:
    for clause in _CLAUSE_BOUNDARY.split(answer):
        if not any(pattern.search(clause) for pattern in _ACTION_HANDOFF_PATTERNS):
            continue
        if _ACTION_BLOCKER_PATTERN.search(clause):
            continue
        if _UNRELATED_HELP_PATTERN.search(clause):
            continue
        return True
    return False


def _completion_claims(answer: str) -> list[_CompletionClaim]:
    claims = []
    for clause in _CLAUSE_BOUNDARY.split(answer):
        clause = clause.strip()
        if clause and _claims_completed_change(clause):
            claims.append(
                _CompletionClaim(allow_partial=_clause_allows_partial(clause))
            )
    return claims


def _clause_allows_partial(clause: str) -> bool:
    return bool(_FAILED_WORK_PATTERN.search(_NO_ERROR_PATTERN.sub("", clause)))


def _evidence_supports(evidence: MutationEvidence, claim: _CompletionClaim) -> bool:
    # Verb-class matching produced false retries on truthful answers; any
    # successful mutation grounds the claim, so only tool-free claims retry.
    return evidence.changed if claim.allow_partial else evidence.completed


def _claims_are_grounded(
    messages: list[ModelMessage] | None, claims: list[_CompletionClaim]
) -> bool:
    if not claims or messages is None:
        return True
    evidence = get_mutation_evidence(messages)
    return all(
        any(_evidence_supports(item, claim) for item in evidence) for claim in claims
    )


def validate_final_answer(ctx: RunContext[AssistantDeps], answer: str) -> str:
    """
    Reject answers that bypass tools or make unverified claims.

    :param ctx: The agent run context, or None outside an agent run.
    :param answer: The candidate final answer produced by the model.
    :return: The answer unchanged when it passes every check.
    :raises ModelRetry: When the answer prints a tool call as text, invents a
        tool-availability limitation, claims an unverified change, or hands an
        executable action back to the user.
    """

    if _looks_like_tool_call(answer):
        raise ModelRetry(
            "That answer is a tool call printed as text, so nothing was "
            "executed. Call the tool instead, and if the payload is large "
            "split it into batches of at most 20 rows per call."
        )
    if _claims_current_tools_are_unavailable(
        answer
    ) and not _explains_unconfigured_documentation_search(ctx, answer):
        raise ModelRetry(
            "Do not infer that a tool is unavailable from the current mode. "
            "If its schema is hidden, call search_tools with its name, then call "
            "the revealed tool; mode routing is automatic. If the action is "
            "genuinely unsupported, cite the matching <limitations> entry. If a "
            "tool failed, report its actual error instead."
        )

    claims = _completion_claims(answer)
    grounded = _claims_are_grounded(ctx.messages if ctx is not None else None, claims)
    if claims and not grounded:
        raise ModelRetry(
            "You claimed a change succeeded without a verified successful tool "
            "result. Execute the required tool first, or accurately say what is "
            "still pending and why."
        )
    # A pending ask_user question is the one legitimate handoff.
    asked = ctx is not None and isinstance(ctx.deps.pending_question, str)
    # A grounded completion claim means the offer is an optional extra.
    if not claims and not asked and _defers_action_without_blocker(answer):
        raise ModelRetry(
            "Do not hand an executable action back to the user by saying you are "
            "ready or asking whether to proceed. Execute it now. Ask only when "
            "required input is missing, or report the exact tool error or supported "
            "limitation that blocks it."
        )
    return answer

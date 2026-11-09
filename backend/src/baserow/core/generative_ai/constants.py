from enum import StrEnum


class ReasoningEffort(StrEnum):
    """How much a model reasons before it replies, lowest first."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


REASONING_EFFORTS = tuple(ReasoningEffort)
"""Every reasoning effort, lowest first."""

# Web searches one reply may run, at about $10 per 1,000 searches plus tokens.
WEB_SEARCH_MAX_PER_REPLY = 5

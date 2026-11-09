from enum import StrEnum


class ReasoningEffort(StrEnum):
    """How much a model reasons before it replies, lowest first."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


REASONING_EFFORTS = tuple(ReasoningEffort)
"""Every reasoning effort, lowest first."""

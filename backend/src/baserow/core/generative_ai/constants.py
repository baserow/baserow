from enum import StrEnum


class ReasoningEffort(StrEnum):
    """How much a model reasons before it replies, lowest first."""

    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


REASONING_EFFORTS = tuple(ReasoningEffort)
"""Every reasoning effort, lowest first."""


class ProviderFailure(StrEnum):
    """Why a provider failed a request, for the failures a user can act on."""

    AUTH_FAILED = "provider_auth_failed"
    RATE_LIMITED = "provider_rate_limited"
    UNAVAILABLE = "provider_unavailable"


# Web searches one reply may run, at about $10 per 1,000 searches plus tokens.
WEB_SEARCH_MAX_PER_REPLY = 5

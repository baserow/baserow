from django.contrib.auth.models import AbstractUser


def get_identity_type(user):
    if not isinstance(user, AbstractUser):
        return None
    profile = getattr(user, "profile", None)
    # Old cached profiles must fail closed instead of loading a new field in async auth.
    kind = profile.__dict__.get("identity_type") if profile is not None else None
    return kind if kind in ("human", "agent") else None


def is_human_user(user) -> bool:
    """Return whether this identity can use human account features."""

    return get_identity_type(user) == "human"


def is_agent_user(user) -> bool:
    """Return whether this User is an agent identity."""

    return get_identity_type(user) == "agent"

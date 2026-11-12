from django.contrib.auth.models import AbstractUser
from django.db.models import Q

IDENTITY_EMAIL_DOMAIN = "identities.invalid"


def get_user_type(user: object) -> str | None:
    if not isinstance(user, AbstractUser):
        return None
    profile = getattr(user, "profile", None)
    # Incomplete profiles must not trigger a deferred-field query in async auth.
    kind = profile.__dict__.get("user_type") if profile is not None else None
    return kind if kind in ("human", "identity") else None


def is_human(user: object) -> bool:
    """Return whether the stored User represents a human, regardless of status."""

    return get_user_type(user) == "human"


def is_identity(user: object) -> bool:
    """Return whether the stored User represents a nonhuman identity."""

    return get_user_type(user) == "identity"


def active_identity_q(user_lookup: str = "") -> Q:
    """
    Matches the identities that can act, be assigned or be mentioned.

    :param user_lookup: The lookup path from the queried model to its user, for
        example `user__`. Empty when the user model itself is queried.
    :return: The condition to filter with.
    """

    return Q(
        **{
            f"{user_lookup}profile__user_type": "identity",
            f"{user_lookup}profile__trashed": False,
            f"{user_lookup}is_active": True,
        }
    )

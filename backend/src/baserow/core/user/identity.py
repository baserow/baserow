from collections.abc import Iterable

from django.contrib.auth.models import AbstractUser
from django.db.models import Q, prefetch_related_objects

IDENTITY_EMAIL_DOMAIN = "identities.invalid"


def load_user_types(users: Iterable[object]) -> None:
    """
    Loads the missing profiles of the given users in one query. Reading the type of a
    user loads its profile, so call this before classifying a list of users instead
    of asking every caller to preload profiles.

    :param users: The actors to load the profile of. Other objects are skipped.
    """

    without_duplicates = {
        id(user): user for user in users if isinstance(user, AbstractUser)
    }
    prefetch_related_objects(list(without_duplicates.values()), "profile")


def get_user_type(user: object) -> str | None:
    if not isinstance(user, AbstractUser):
        return None
    profile = getattr(user, "profile", None)
    # Incomplete profiles must not trigger a deferred-field query in async auth.
    kind = profile.__dict__.get("user_type") if profile is not None else None
    return kind if kind in ("human", "identity") else None


def is_human(user: object) -> bool:
    """
    Return whether the stored User represents a human, regardless of status. Call
    `load_user_types` first when classifying a list of users.
    """

    return get_user_type(user) == "human"


def is_identity(user: object) -> bool:
    """Return whether the stored User represents a nonhuman identity."""

    return get_user_type(user) == "identity"


def has_internal_email(user: AbstractUser) -> bool:
    """
    Returns whether the email of the user is the generated address of an identity,
    which is a key and must never be shown.

    :param user: The person or identity whose email is checked.
    :return: Whether the email is in the domain reserved for identities.
    """

    return user.email.endswith(f"@{IDENTITY_EMAIL_DOMAIN}")


def get_user_label(user: AbstractUser) -> str:
    """
    Returns the text that names a user where only text fits, such as an export.

    :param user: The person or identity to name.
    :return: The email of the user, or its name when the email is internal.
    """

    return user.first_name if has_internal_email(user) else user.email


def collaborator_q(include_identities: bool, user_lookup: str = "") -> Q:
    """Select the people, and optionally the active identities, among users."""

    kinds = Q(**{f"{user_lookup}profile__user_type": "human"})
    if include_identities:
        kinds |= active_identity_q(user_lookup)
    return kinds


def active_identity_q(user_lookup: str = "") -> Q:
    """Select identities eligible for new assignments and run-as choices."""

    return Q(
        **{
            f"{user_lookup}profile__user_type": "identity",
            f"{user_lookup}profile__trashed": False,
            f"{user_lookup}profile__to_be_deleted": False,
            f"{user_lookup}is_active": True,
        }
    )

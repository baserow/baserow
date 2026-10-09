"""What Kuma's changes to uid-keyed lists share: table columns and menu items."""

import uuid
from collections.abc import Iterable
from typing import TypeVar

NO_CHANGES = "No changes were applied."

_Item = TypeVar("_Item")


def canonical_uid(raw: str) -> str:
    """
    Canonicalize a uid the model sent so it compares equal to stored uids.

    :param raw: The uid as sent.
    :return: The lower-case hyphenated uid, or the stripped input if it isn't a UUID.
    """

    try:
        return str(uuid.UUID(raw.strip()))
    except ValueError:
        return raw.strip()


def name_key(name: str) -> str:
    """
    Compare names ignoring case and surrounding spaces.

    :param name: A column, field or menu item name.
    :return: The comparison key.
    """

    return name.strip().casefold()


def unique_in_order(items: Iterable[_Item]) -> list[_Item]:
    """
    Drop repeated items, keeping the first of each.

    :param items: The items, possibly repeated.
    :return: Each item once, in the order first seen.
    """

    return list(dict.fromkeys(items))

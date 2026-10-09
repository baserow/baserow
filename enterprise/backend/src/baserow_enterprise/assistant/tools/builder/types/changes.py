"""What Kuma's changes to uid-keyed lists share: table columns and menu items."""

import uuid

NO_CHANGES = "No changes were applied."


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

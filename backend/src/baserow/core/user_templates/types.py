import dataclasses
from typing import List, Optional, TypedDict

from baserow.core.models import UserTemplateState


class TemplateMetadata(TypedDict, total=False):
    """
    The private metadata of a template revision, only shown to its owner. It's
    read and written through `UserTemplateHandler` only.
    """

    # The workspace the applications of the revision were copied from.
    source_workspace_id: int
    # The ids of the applications the revision was copied from.
    source_application_ids: List[int]


@dataclasses.dataclass(frozen=True)
class UnblockOutcome:
    """What a user template returned to when an admin unblocked it."""

    # The state of the template after the unblock.
    state: UserTemplateState
    # The revision the unblock listed, if any.
    listed_revision_id: Optional[int]
    # Whether the template is listed after the unblock, also with an edit in review.
    listed: bool

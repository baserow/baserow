from typing import Any, Dict, Iterable, List

from django.contrib.auth.models import AbstractUser

from baserow.core.models import Workspace
from baserow.core.prosemirror.utils import extract_mention_ids
from baserow.core.registry import Instance

from .models import RowComment


class RowCommentMentionTargetType(Instance):
    """
    One kind of thing a row comment can address with `@`. The type name is
    the `kind` stored on the mention node, so a document resolves itself: each
    registered type picks its mentions out of the document, stores them on
    the comment, says what the comment event carries for them, offers its
    candidates to the picker, and reacts when it is mentioned.
    """

    def extract_ids(self, message: Dict[str, Any]) -> set:
        return extract_mention_ids(message, self.type)

    def resolve(self, ids: set, workspace: Workspace) -> List[Any]:
        """
        The mentioned objects that exist in the workspace; a mention of
        something elsewhere, or gone, is dropped rather than refused.
        """

        raise NotImplementedError

    def attach(self, row_comment: RowComment, targets: List[Any]) -> None:
        """Stores the resolved mentions on the comment."""

        raise NotImplementedError

    def get_attached(self, row_comment: RowComment) -> List[Any]:
        """The mentions stored on the comment, for an update's diff."""

        raise NotImplementedError

    def get_signal_kwargs(self, targets: List[Any]) -> Dict[str, Any]:
        """Extra keyword arguments the comment signals carry for this type."""

        return {}

    def get_event_payload(self, targets: List[Any]) -> Dict[str, Any]:
        """What the row comment trigger's event payload carries for this type."""

        return {}

    def get_event_schema(self) -> Dict[str, Any]:
        """The schema properties of `get_event_payload`."""

        return {}

    def list_mentionable(self, user: AbstractUser, table) -> List[Dict[str, Any]]:
        """
        The candidates the picker offers for this table, as
        `{"type", "id", "name"}`; empty when the picker already has them
        from elsewhere (members) or nothing applies.
        """

        return []

    def comment_created(self, row_comment: RowComment, row, targets: List[Any]):
        """Reacts to a new comment mentioning `targets`."""

    def comment_updated(
        self, row_comment: RowComment, row, targets: List[Any], previous: List[Any]
    ):
        """Reacts to an edited comment; `previous` holds the earlier mentions."""


class UserMentionTargetType(RowCommentMentionTargetType):
    """
    A workspace member. Mentioning one notifies them; the picker gets the
    members from the workspace it already holds, so nothing is listed here.
    """

    type = "user"

    def resolve(self, ids, workspace):
        return list(
            workspace.users.filter(
                id__in=_int_ids(ids), profile__to_be_deleted=False
            ).select_related("profile")
        )

    def attach(self, row_comment, targets):
        if targets:
            row_comment.mentions.set(targets)
        else:
            row_comment.mentions.clear()

    def get_attached(self, row_comment):
        return list(row_comment.mentions.all())

    def get_signal_kwargs(self, targets):
        return {"mentions": list(targets)}

    def get_event_payload(self, targets):
        return {
            "mentions": [
                {"id": mention.id, "name": mention.first_name} for mention in targets
            ]
        }

    def get_event_schema(self):
        return {"mentions": {"type": "array", "title": "Mentions"}}

    def comment_created(self, row_comment, row, targets):
        from .notification_types import RowCommentMentionNotificationType

        # A comment without an author (posted by an agent) names no sender,
        # so it notifies nobody for now.
        if targets and row_comment.user_id is not None:
            RowCommentMentionNotificationType.notify_mentioned_users(
                row_comment, row, targets
            )

    def comment_updated(self, row_comment, row, targets, previous):
        new = [target for target in targets if target not in previous]
        self.comment_created(row_comment, row, new)


def _int_ids(ids: Iterable[Any]) -> set:
    """Mention ids come from a document, so anything that is not an id is dropped."""

    result = set()
    for value in ids:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result

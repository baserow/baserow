from typing import Any, Dict, Set

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from prosemirror.model import Node

from baserow.core.models import Workspace

from .schema import schema


def is_valid_prosemirror_document(json_doc: Dict[str, Any]) -> bool:
    """
    Returns whether the given json document is valid according to the schema.

    :param json_doc: The json document to validate.
    :return: Whether the given json document is valid according to the schema.
    """

    try:
        Node.from_json(schema, json_doc)
        return True
    except ValueError:
        return False


MENTION_KIND_USER = "user"


def extract_mention_ids(json_doc: Dict[str, Any], kind: str) -> Set[int]:
    """
    The ids of the mentions of one kind in the document. Mention nodes carry
    a `kind` (what is being addressed: a user, an application, ...); the
    registered mention target types decide what each kind resolves to.

    :raise ValueError: When the document is not valid according to the schema.
    """

    mentions = set()

    def _extract_mentions(node, *args):
        # Older documents have no kind; they only ever mentioned users.
        if (
            node.type.name == "mention"
            and (node.attrs.get("kind") or MENTION_KIND_USER) == kind
        ):
            mentions.add(node.attrs["id"])

    doc = Node.from_json(schema, json_doc)
    doc.descendants(_extract_mentions)
    return mentions


def extract_mentioned_user_ids(json_doc: Dict[str, Any]) -> Set[int]:
    """
    Extracts the user ids of all mentioned users from the given json document.

    :raise ValueError: When the given json document is not valid according to the
        schema.
    """

    return extract_mention_ids(json_doc, MENTION_KIND_USER)


def extract_mentioned_users_in_workspace(
    json_doc: Dict[str, Any], workspace: Workspace
) -> QuerySet[AbstractUser]:
    """
    Returns a queryset of all mentioned users in the given workspace.

    :param json_doc: The json document to extract the mentioned user ids from.
    :param workspace: The workspace to search for mentioned users.
    :return: A queryset of all mentioned users in the given workspace.
    :raise ValueError: When the mentioned user ids are not all in the given
        workspace.
    """

    mentioned_user_ids = extract_mentioned_user_ids(json_doc)
    return workspace.users.filter(
        id__in=mentioned_user_ids, profile__to_be_deleted=False
    ).select_related("profile")


def prosemirror_doc_from_plain_text(plain_text_message) -> Dict[str, Any]:
    """
    Returns a json document from the given plain text message.

    :param plain_text_message: The plain text message to convert to a json document.
    :return: A json document.
    """

    return {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": plain_text_message}],
            }
        ],
    }


def prosemirror_doc_to_plain_text(json_doc: Dict[str, Any]) -> str:
    """
    Returns a plain text message from the given json document.

    :param json_doc: The json document to convert to a plain text message.
    :return: A plain text message.
    """

    def _to_plain_text(node):
        return node.type.spec["toText"](node, _to_plain_text)

    doc = Node.from_json(schema, json_doc)
    return _to_plain_text(doc.content.content[0])

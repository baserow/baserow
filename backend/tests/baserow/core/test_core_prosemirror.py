import pytest

from baserow.core.identities.handler import IdentityHandler
from baserow.core.prosemirror.utils import (
    extract_mentioned_user_ids,
    extract_mentioned_users_in_workspace,
    is_valid_prosemirror_document,
    prosemirror_doc_to_plain_text,
)


def test_valid_prosemirror_doc_can_be_parsed():
    random_doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "hey "},
                    {"type": "mention", "attrs": {"id": 1, "label": "staff-dev"}},
                    {
                        "type": "text",
                        "text": " Lorem Ipsum is simply dummy text of the printing and typesetting industry.",
                    },
                    {"type": "hardBreak"},
                    {"type": "hardBreak"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Lorem"},
                ],
            }
        ],
    }

    assert is_valid_prosemirror_document(random_doc) is True

    mentioned_user_ids = extract_mentioned_user_ids(random_doc)
    assert mentioned_user_ids == {1}

    assert prosemirror_doc_to_plain_text(random_doc) == (
        "hey @staff-dev Lorem Ipsum is simply dummy text of the printing and "
        "typesetting industry.\n\n\nLorem"
    )


@pytest.mark.django_db
def test_identity_mentions_resolve_only_within_the_workspace(data_fixture):
    identity = data_fixture.create_identity()
    foreign_identity = data_fixture.create_identity()
    workspace = IdentityHandler.get_workspace(identity)
    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {"id": identity.id, "label": identity.first_name},
                    }
                    for identity in (identity, foreign_identity)
                ],
            }
        ],
    }
    assert list(extract_mentioned_users_in_workspace(message, workspace)) == [identity]

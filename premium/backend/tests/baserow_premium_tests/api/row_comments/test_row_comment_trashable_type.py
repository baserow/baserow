from django.test.utils import override_settings

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.trash.exceptions import CannotRestoreChildBeforeParent
from baserow.core.trash.handler import TrashHandler
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import RowComment
from baserow_premium.row_comments.trash_types import RowCommentTrashableItemType


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_restore_row_comment_before_row(premium_data_fixture, api_client):
    user = premium_data_fixture.create_user(
        first_name="User 1", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    commented_on_row = rows[0]
    commented_on_row_id = commented_on_row.id
    comment = RowComment.objects.create(
        table=table, row_id=commented_on_row_id, user=user, comment="My test comment"
    )

    RowCommentHandler.delete_comment(user, comment)
    RowHandler().delete_row(user, table, commented_on_row)

    with pytest.raises(CannotRestoreChildBeforeParent):
        TrashHandler.restore_item(user, RowCommentTrashableItemType.type, comment.id)

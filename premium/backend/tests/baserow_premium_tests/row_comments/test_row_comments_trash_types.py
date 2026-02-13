from django.test.utils import override_settings

import pytest

from baserow.core.trash.handler import TrashHandler
from baserow_premium.row_comments.models import RowComment


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comment_can_be_trashed(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table)
    rows = premium_data_fixture.create_rows_in_table(table, [[]])
    row_comment = premium_data_fixture.create_row_comment(
        user=user, row=rows[0], comment="Test"
    )

    trash_entry = TrashHandler.trash(
        user, table.database.workspace, table.database, row_comment
    )
    assert trash_entry.trash_item_type == "row_comment"
    assert trash_entry.trash_item_id == row_comment.id
    assert trash_entry.trash_item_owner_id == user.id

    assert RowComment.objects.count() == 0
    assert RowComment.objects_and_trash.count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trashed_row_comment_can_be_restored(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    table = premium_data_fixture.create_database_table(user=user)
    premium_data_fixture.create_text_field(table=table)
    rows = premium_data_fixture.create_rows_in_table(table, [[]])
    row_comment = premium_data_fixture.create_row_comment(
        user=user, row=rows[0], comment="Test"
    )

    TrashHandler.trash(user, table.database.workspace, table.database, row_comment)

    TrashHandler.restore_item(
        user, "row_comment", row_comment.id, parent_trash_item_id=None
    )

    row_comment.refresh_from_db()
    assert row_comment.comment == "Test"
    assert row_comment.trashed is False
    assert RowComment.objects.count() == 1

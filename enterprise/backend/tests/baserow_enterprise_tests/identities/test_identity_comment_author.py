import pytest

from baserow.core.notifications.models import NotificationRecipient
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import RowCommentsNotificationMode


@pytest.mark.django_db
def test_identity_comment_author_uses_workspace_license_without_subscribing(
    enterprise_data_fixture, premium_data_fixture, synced_roles, enable_enterprise
):
    human = enterprise_data_fixture.create_user()
    table, _, rows = enterprise_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=human
    )
    identity = enterprise_data_fixture.create_identity(
        workspace=table.database.workspace, role_uid="ADMIN"
    )
    message = premium_data_fixture.create_comment_message_with_mentions([human])

    comment = RowCommentHandler.create_comment(identity, table.id, rows[0].id, message)

    assert comment.user == identity
    assert NotificationRecipient.objects.get().recipient == human
    assert not RowCommentsNotificationMode.objects.filter(user=identity).exists()

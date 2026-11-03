import pytest

from baserow.core.notifications.models import NotificationRecipient
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import RowCommentsNotificationMode


@pytest.mark.django_db
def test_agent_comment_author_uses_workspace_license_without_subscribing(
    enterprise_data_fixture, premium_data_fixture, synced_roles, enable_enterprise
):
    human = enterprise_data_fixture.create_user()
    table, _, rows = enterprise_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=human
    )
    agent = enterprise_data_fixture.create_agent(
        workspace=table.database.workspace, role_uid="ADMIN"
    )
    message = premium_data_fixture.create_comment_message_with_mentions([human])

    comment = RowCommentHandler.create_comment(agent, table.id, rows[0].id, message)

    assert comment.user == agent
    assert NotificationRecipient.objects.get().recipient == human
    assert not RowCommentsNotificationMode.objects.filter(user=agent).exists()

from django.urls import reverse

import pytest

from baserow.core.notifications.models import NotificationRecipient
from baserow_premium.row_comments.handler import RowCommentHandler
from baserow_premium.row_comments.models import RowCommentsNotificationMode


@pytest.mark.django_db
def test_identity_comment_author_uses_workspace_license_without_subscribing(
    api_client,
    enterprise_data_fixture,
    premium_data_fixture,
    synced_roles,
    enable_enterprise,
):
    human, token = enterprise_data_fixture.create_user_and_token()
    table, _, rows = enterprise_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=human
    )
    identity = enterprise_data_fixture.create_identity(
        workspace=table.database.workspace, role_uid="ADMIN"
    )
    message = premium_data_fixture.create_comment_message_with_mentions([human])

    comment = RowCommentHandler.create_comment(identity, table.id, rows[0].id, message)

    assert comment.user == identity
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.json()["results"][0]["user_type"] == "identity"
    assert NotificationRecipient.objects.get().recipient == human
    assert not RowCommentsNotificationMode.objects.filter(user=identity).exists()

from unittest.mock import MagicMock, call, patch

from django.db.models import Count, Q
from django.shortcuts import reverse
from django.test import override_settings

import pytest
from baserow_premium.row_comments.handler import (
    RowCommentHandler,
    RowCommentsNotificationModes,
)
from baserow_premium.row_comments.notification_types import (
    RowCommentMentionNotificationType,
    RowCommentNotificationType,
)
from freezegun import freeze_time
from pytest_unordered import unordered
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT

from baserow.core.models import WorkspaceUser
from baserow.core.notifications.handler import NotificationHandler
from baserow.core.notifications.models import NotificationRecipient
from baserow.test_utils.helpers import AnyInt


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.notifications.signals.notification_created.send")
def test_notification_creation_on_creating_row_comment_mention(
    mocked_notification_created, api_client, premium_data_fixture
):
    user_1, token_1 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user_1
    )
    workspace = table.database.workspace
    user_2, token_2 = premium_data_fixture.create_user_and_token(
        workspace=workspace, has_active_premium_license=True
    )

    message = premium_data_fixture.create_comment_message_with_mentions([user_2])

    with freeze_time("2020-01-01 12:00"):
        token_1 = premium_data_fixture.generate_token(user_1)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
    assert response.status_code == HTTP_200_OK
    comment_id = response.json()["id"]

    assert mocked_notification_created.called_once()
    args = mocked_notification_created.call_args
    assert args == call(
        sender=NotificationHandler,
        notification=NotificationHandler.get_notification_by(
            user_2, data__contains={"comment_id": comment_id}
        ),
        notification_recipients=list(
            NotificationRecipient.objects.filter(recipient=user_2)
        ),
        user=user_1,
    )

    # the user can see the notification in the list of notifications
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "created_on": "2020-01-01T12:00:00Z",
                "type": RowCommentMentionNotificationType.type,
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "database_id": table.database.id,
                    "database_name": table.database.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "row_id": rows[0].id,
                    "row_name": str(rows[0]),
                    "comment_id": comment_id,
                    "message": message,
                },
            }
        ],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.notifications.signals.notification_created.send")
def test_notify_only_new_mentions_when_updating_a_comment(
    mocked_notification_created, api_client, premium_data_fixture
):
    user_1, token_1 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user_1
    )
    workspace = table.database.workspace
    user_2 = premium_data_fixture.create_user(
        workspace=workspace, has_active_premium_license=True
    )

    message = premium_data_fixture.create_comment_message_with_mentions([user_2])
    with freeze_time("2020-01-01 11:00"):
        comment = RowCommentHandler.create_comment(
            user_1, table.id, rows[0].id, message
        )
    new_message = premium_data_fixture.create_comment_message_with_mentions(
        [user_1, user_2]
    )

    with freeze_time("2020-01-01 12:00"):
        token_1 = premium_data_fixture.generate_token(user_1)
        response = api_client.patch(
            reverse(
                "api:premium:row_comments:item",
                kwargs={"table_id": table.id, "comment_id": comment.id},
            ),
            {"message": new_message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
    assert response.status_code == HTTP_200_OK
    comment_id = response.json()["id"]

    assert mocked_notification_created.called_once()
    args = mocked_notification_created.call_args
    assert args == call(
        sender=NotificationHandler,
        notification=NotificationHandler.get_notification_by(
            user_1, data__contains={"comment_id": comment_id}
        ),
        notification_recipients=list(
            NotificationRecipient.objects.filter(recipient=user_1)
        ),
        user=user_1,
    )

    # the user can see the notification in the list of notifications
    token_1 = premium_data_fixture.generate_token(user_1)
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": AnyInt(),
                "type": RowCommentMentionNotificationType.type,
                "created_on": "2020-01-01T12:00:00Z",
                "read": False,
                "sender": {
                    "id": user_1.id,
                    "username": user_1.username,
                    "first_name": user_1.first_name,
                },
                "workspace": {"id": workspace.id},
                "data": {
                    "database_id": table.database.id,
                    "database_name": table.database.name,
                    "table_id": table.id,
                    "table_name": table.name,
                    "row_id": rows[0].id,
                    "row_name": str(rows[0]),
                    "comment_id": comment_id,
                    "message": new_message,
                },
            }
        ],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(DEBUG=True)
def test_email_notifications_are_created_correctly(
    mock_get_mail_connection, premium_data_fixture, api_client
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    user_1, token_1 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True, first_name="User 1"
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user_1
    )
    workspace = table.database.workspace
    user_2 = premium_data_fixture.create_user(
        workspace=workspace, has_active_premium_license=True, first_name="User 2"
    )

    row = rows[0]
    message = premium_data_fixture.create_comment_message_with_mentions([user_2])

    with freeze_time("2020-01-01 12:00"):
        token_1 = premium_data_fixture.generate_token(user_1)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": row.id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_200_OK

    # Force to send the notifications
    res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
        Q(pk=user_2.pk)
    )
    assert res.users_with_notifications == [user_2]
    assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
    assert res.users_with_notifications[0].total_unsent_count == 1
    assert res.remaining_users_to_notify_count == 0

    mock_get_mail_connection.assert_called_once_with(fail_silently=False)
    summary_emails = mock_connection.send_messages.call_args[0][0]
    assert len(summary_emails) == 1
    user_2_summary_email = summary_emails[0]
    assert user_2_summary_email.to == [user_2.email]
    assert user_2_summary_email.get_subject() == "You have 1 new notification - Baserow"

    notif = NotificationRecipient.objects.get(recipient=user_2)
    notification_url = f"http://localhost:3000/notification/{notif.workspace_id}/{notif.notification_id}"

    expected_context = {
        "notifications": [
            {
                "title": f"User 1 mentioned you in row {str(row)} in {table.name}.",
                "description": "@User 2",
                "url": notification_url,
            }
        ],
        "new_notifications_count": 1,
        "unlisted_notifications_count": 0,
    }
    user_2_summary_email_context = user_2_summary_email.get_context()

    for k, v in expected_context.items():
        assert user_2_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@override_settings(DEBUG=True)
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_user_receive_notification_if_subscribed_for_comments_on_a_row(
    mocked_broadcast_to_users, api_client, premium_data_fixture
):
    user_1, token_1 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    user_2, token_2 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    commenter, commenter_token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(users=[user_1, user_2, commenter])
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")],
        rows=["first row", "second_row"],
        user=user_1,
        database=database,
    )

    def subscribe_to_row_comments(mode=RowCommentsNotificationModes.MODE_ALL_COMMENTS):
        response = api_client.put(
            reverse(
                "api:premium:row_comments:notification_mode",
                kwargs={"row_id": rows[0].id, "table_id": table.id},
            ),
            {"mode": mode},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token_1}",
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        # Reset the mock because this endpoint also broadcasts a message to the
        # user with a different session-id to update the notification_mode for this row
        mocked_broadcast_to_users.reset_mock()

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "Test comment"
    )

    def post_comment():
        token = premium_data_fixture.generate_token(commenter)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK

    # the first time, the user will receive the realtime update
    # about the change of the notification_mode to 'all' comments
    post_comment()
    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert args[0] == [
        [commenter.id],
        {
            "type": "row_comments_notification_mode_updated",
            "table_id": table.id,
            "row_id": rows[0].id,
            "mode": "all",
        },
        None,
    ]
    mocked_broadcast_to_users.reset_mock()

    subscribe_to_row_comments()
    # now user_1 should receive the notification
    with freeze_time("2021-01-01 12:00"):
        post_comment()

    # the saved data are valid
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK

    expected_notification = {
        "id": AnyInt(),
        "type": "row_comment",
        "sender": {
            "id": commenter.id,
            "username": commenter.username,
            "first_name": commenter.first_name,
        },
        "workspace": {"id": workspace.id},
        "created_on": "2021-01-01T12:00:00Z",
        "read": False,
        "data": {
            "row_id": rows[0].id,
            "row_name": str(rows[0]),
            "table_id": table.id,
            "table_name": table.name,
            "database_id": database.id,
            "database_name": database.name,
            "comment_id": AnyInt(),
            "message": message,
        },
    }
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [expected_notification],
    }

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert args[0] == [
        [user_1.id],
        {
            "type": "notifications_created",
            "notifications": [expected_notification],
        },
    ]

    # user_2 received nothing
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_2}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }

    mocked_broadcast_to_users.reset_mock()

    # user_1 stops receiving notifications changing the subscription mode
    subscribe_to_row_comments(
        mode=RowCommentsNotificationModes.MODE_ONLY_MENTIONS.value
    )
    post_comment()

    assert mocked_broadcast_to_users.call_count == 0

    # only the previous one, the last comment is not notified
    response = api_client.get(
        reverse("api:notifications:list", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token_1}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [expected_notification],
    }


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@override_settings(DEBUG=True)
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_all_interested_users_receive_the_notification_when_a_comment_is_posted(
    mocked_broadcast_to_users, api_client, premium_data_fixture
):
    user_1, _ = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    user_2, _ = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    user_3, _ = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    user_4, _ = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    commenter, commenter_token = premium_data_fixture.create_user_and_token(
        first_name="Commenter", has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(
        users=[user_1, user_2, user_3, user_4, commenter]
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")],
        rows=["first row", "second_row"],
        user=user_1,
        database=database,
    )

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "Test comment"
    )

    # Create a first comment so that the commenter notification mode will be
    # changed to 'all'
    api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {commenter_token}",
    )

    # subscribe all users to receive notifications on all comments
    for usr in [user_1, user_2, user_3, user_4]:
        RowCommentHandler().update_row_comments_notification_mode(
            usr,
            table.id,
            rows[0].id,
            mode=RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
        )
    # Reset the mock because this endpoint also broadcasts a message to the
    # user with a different session-id to update the notification_mode for this row
    mocked_broadcast_to_users.reset_mock()

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {commenter_token}",
    )
    assert response.status_code == HTTP_200_OK

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert unordered(args[0][0], [user_1.id, user_2.id, user_3.id, user_4.id])
    expected_count_per_user = [1, 1, 1, 1]
    qs = NotificationRecipient.objects.filter(
        recipient__in=[user_1, user_2, user_3, user_4]
    ).annotate(count=Count("notification_id"))
    assert list(qs.values_list("count", flat=True)) == expected_count_per_user


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@override_settings(DEBUG=True)
@pytest.mark.enable_signals("baserow.ws.tasks.broadcast_to_users.delay")
def test_only_users_with_access_to_the_table_receive_the_notification_for_new_comments(
    mocked_broadcast_to_users, api_client, premium_data_fixture
):
    user_1, token_1 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    user_2, token_2 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    commenter, commenter_token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    workspace = premium_data_fixture.create_workspace(users=[user_1, user_2, commenter])
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")],
        rows=["first row", "second_row"],
        user=user_1,
        database=database,
    )

    def subscribe_to_row_comments(
        user_token, mode=RowCommentsNotificationModes.MODE_ALL_COMMENTS
    ):
        response = api_client.put(
            reverse(
                "api:premium:row_comments:notification_mode",
                kwargs={"row_id": rows[0].id, "table_id": table.id},
            ),
            {"mode": mode},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {user_token}",
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        # Reset the mock because this endpoint also broadcasts a message to the
        # user with a different session-id to update the notification_mode for this row
        mocked_broadcast_to_users.reset_mock()

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "Test comment"
    )

    def post_comment():
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {commenter_token}",
        )
        assert response.status_code == HTTP_200_OK

    # create a first message to change the notification mode for the commenter
    post_comment()
    mocked_broadcast_to_users.assert_called_once()
    mocked_broadcast_to_users.reset_mock()

    # Now subscribe 2 users and notice that both will receive the notification
    subscribe_to_row_comments(token_1)
    subscribe_to_row_comments(token_2)
    post_comment()

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert unordered(args[0][0], [user_1.id, user_2.id])

    mocked_broadcast_to_users.reset_mock()

    # remove users from the workspace
    WorkspaceUser.objects.filter(
        user__in=[user_1, user_2], workspace=workspace
    ).delete()

    # This time nobody receives the notification because users don't belong to
    # the workspace anymore
    post_comment()

    assert mocked_broadcast_to_users.call_count == 0

    # Adding them back, they receive the notification again
    WorkspaceUser.objects.bulk_create(
        [
            WorkspaceUser(user=user_1, workspace=workspace, order=1),
            WorkspaceUser(user=user_2, workspace=workspace, order=2),
        ]
    )

    post_comment()

    assert mocked_broadcast_to_users.call_count == 1
    args = mocked_broadcast_to_users.call_args_list[0][0]
    assert unordered(args[0][0], [user_1.id, user_2.id])


@pytest.mark.django_db
def test_row_comment_notification_type_can_be_rendered_as_email(
    premium_data_fixture,
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    commenter = premium_data_fixture.create_user(has_active_premium_license=True)
    workspace = premium_data_fixture.create_workspace(users=[user, commenter])
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")],
        rows=["first row", "second_row"],
        user=user,
        database=database,
    )

    row_comment = premium_data_fixture.create_row_comment(
        commenter, rows[0], "Test comment"
    )

    notification_recipients = RowCommentNotificationType.notify_subscribed_users(
        row_comment, row_comment.get_parent(), [user]
    )

    assert len(notification_recipients) == 1
    notification = notification_recipients[0].notification

    assert (
        RowCommentNotificationType.get_notification_title_for_email(notification, {})
        == f"{commenter.first_name} posted a comment in row {str(rows[0])} in {table.name}."
    )
    assert (
        RowCommentNotificationType.get_notification_description_for_email(
            notification, {}
        )
        == "Test comment"
    )


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_can_get_row_comment_notification_mode_from_row_metadata(
    api_client, premium_data_fixture
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    table = premium_data_fixture.create_database_table(user=user)
    row = table.get_model().objects.create()

    def get_row_from_api_with_metadata():
        return api_client.get(
            reverse(
                "api:database:rows:item",
                kwargs={"table_id": table.id, "row_id": row.id},
            )
            + "?include=metadata",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response = get_row_from_api_with_metadata()
    assert response.status_code == HTTP_200_OK
    assert response.json()["metadata"] == {}

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": row.id, "table_id": table.id},
        ),
        {"mode": "all"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = get_row_from_api_with_metadata()
    assert response.status_code == HTTP_200_OK
    assert response.json()["metadata"]["row_comments_notification_mode"] == "all"

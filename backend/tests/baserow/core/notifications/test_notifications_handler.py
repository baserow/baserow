from unittest.mock import MagicMock, call, patch

from django.conf import settings
from django.db.models import Q
from django.test import override_settings

import pytest

from baserow.api.notifications.serializers import NotificationRecipientSerializer
from baserow.core.models import UserProfile, WorkspaceUser
from baserow.core.notifications.exceptions import NotificationDoesNotExist
from baserow.core.notifications.handler import (
    NotificationHandler,
    UserNotificationsGrouper,
)
from baserow.core.notifications.models import Notification, NotificationRecipient
from baserow.core.user.handler import UserHandler

from .utils import custom_notification_types_registered


@pytest.mark.django_db
def test_get_workspace_notifications(data_fixture, mutable_notification_type_registry):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    workspace_notification = data_fixture.create_workspace_notification_for_users(
        recipients=[user],
        workspace=workspace,
        notification_type="test_workspace_notification",
    )
    user_notification = data_fixture.create_user_notification_for_users(
        recipients=[user], notification_type="test_user_notification"
    )

    notification_recipients = NotificationHandler.list_notifications(
        user=user, workspace=workspace
    )

    assert len(notification_recipients) == 2
    assert notification_recipients[0].notification_id == user_notification.id
    assert notification_recipients[0].notification.type == "test_user_notification"
    assert notification_recipients[1].notification_id == workspace_notification.id
    assert notification_recipients[1].notification.type == "test_workspace_notification"


@pytest.mark.django_db
def test_get_notification_by_id(data_fixture, mutable_notification_type_registry):
    user = data_fixture.create_user()
    notification = data_fixture.create_user_notification_for_users(recipients=[user])

    assert (
        NotificationHandler.get_notification_by_id(user, notification.id).id
        == notification.id
    )

    with pytest.raises(NotificationDoesNotExist):
        NotificationHandler.get_notification_by_id(user, 999)


@pytest.mark.django_db
def test_annotate_workspaces_with_unread_notifications_count(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    q = WorkspaceUser.objects.filter(user=user, workspace=workspace).all()
    annotated_q = (
        NotificationHandler.annotate_workspaces_with_unread_notifications_count(
            user, q, outer_ref_key="workspace_id"
        )
    )

    assert annotated_q[0].unread_notifications_count == 0

    data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )

    annotated_q = (
        NotificationHandler.annotate_workspaces_with_unread_notifications_count(
            user, q, outer_ref_key="workspace_id"
        )
    )

    assert annotated_q[0].unread_notifications_count == 1


@pytest.mark.django_db
def test_get_unread_notifications_count(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()

    assert NotificationHandler.get_unread_notifications_count(user) == 0

    data_fixture.create_user_notification_for_users(recipients=[user])

    assert NotificationHandler.get_unread_notifications_count(user) == 1


@pytest.mark.django_db
def test_mark_notification_as_read(data_fixture, mutable_notification_type_registry):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    notification = data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )

    qs = NotificationRecipient.objects.filter(recipient=user, notification=notification)
    assert qs.get().read is False

    NotificationHandler.mark_notification_as_read(user, notification)

    assert qs.get().read is True


@pytest.mark.django_db
def test_mark_all_notifications_as_read(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    assert NotificationHandler.get_unread_notifications_count(user, workspace) == 2

    NotificationHandler.mark_all_notifications_as_read(user, workspace=workspace)

    assert NotificationHandler.get_unread_notifications_count(user, workspace) == 0


@pytest.mark.django_db
def test_clear_all_direct_notifications(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    data_fixture.create_workspace_notification_for_users(
        recipients=[user], workspace=workspace
    )
    data_fixture.create_user_notification_for_users(recipients=[user])

    assert Notification.objects.count() == 2

    NotificationHandler.clear_all_notifications(user, workspace=workspace)

    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_clear_direct_notifications_should_delete_them(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_user = data_fixture.create_user(workspace=workspace)

    data_fixture.create_workspace_notification_for_users(
        recipients=[user, other_user], workspace=workspace
    )

    count_user_notifications = NotificationHandler.list_notifications(
        user, workspace=workspace
    ).count
    count_other_user_notifications = NotificationHandler.list_notifications(
        other_user, workspace=workspace
    ).count

    assert Notification.objects.all().count() == 1
    assert count_user_notifications() == 1
    assert count_other_user_notifications() == 1

    NotificationHandler.clear_all_notifications(user, workspace=workspace)

    assert Notification.objects.all().count() == 1
    assert count_user_notifications() == 0
    assert count_other_user_notifications() == 1

    NotificationHandler.clear_all_notifications(other_user, workspace=workspace)

    assert Notification.objects.all().count() == 0
    assert count_user_notifications() == 0
    assert count_other_user_notifications() == 0


@pytest.mark.django_db
def test_all_users_can_see_and_clear_broadcast_notifications(
    data_fixture, mutable_notification_type_registry
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=other_user)

    notification = data_fixture.create_broadcast_notification()

    user_notifications = NotificationHandler.list_notifications(
        user, workspace=workspace
    )
    user_unread_notifications_count = (
        lambda: NotificationHandler.get_unread_notifications_count(user)
    )
    other_user_notifications = NotificationHandler.list_notifications(
        other_user, workspace=workspace
    )
    other_user_unread_notifications_count = (
        lambda: NotificationHandler.get_unread_notifications_count(other_user)
    )

    assert Notification.objects.count() == 1
    assert user_unread_notifications_count() == 1
    assert other_user_unread_notifications_count() == 1

    NotificationHandler.mark_all_notifications_as_read(user, workspace=workspace)

    assert user_unread_notifications_count() == 0
    assert user_notifications[0].read is True

    assert other_user_unread_notifications_count() == 1
    assert other_user_notifications[0].read is False

    NotificationHandler.mark_notification_as_read(other_user, notification)

    assert other_user_unread_notifications_count() == 0

    # notifications have been read by are still there, let's clear them

    assert user_notifications.count() == 1
    assert other_user_notifications.count() == 1

    NotificationHandler.clear_all_notifications(user, workspace=workspace)

    assert user_notifications.count() == 0
    assert other_user_notifications.count() == 1

    NotificationHandler.clear_all_notifications(other_user, workspace=other_workspace)

    # broadcast notifications remain there until the notification is deleted
    assert NotificationRecipient.objects.filter(cleared=True).count() == 2
    assert Notification.objects.count() == 1

    Notification.objects.all().delete()
    assert NotificationRecipient.objects.count() == 0


@pytest.mark.django_db
@patch("baserow.core.notifications.tasks.send_queued_notifications_to_users.delay")
def test_queued_notifications_are_not_visible_to_the_users(
    mocked_send_queued_notifications_to_users,
    data_fixture,
    mutable_notification_type_registry,
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(members=[user, other_user])

    data_fixture.register_notification_type("test 1")
    data_fixture.register_notification_type("test 2")

    notification_1 = Notification(workspace=workspace, type="test 1")
    notification_2 = Notification(workspace=workspace, type="test 2")

    user_notifications = NotificationHandler.list_notifications(
        user, workspace=workspace
    )
    other_user_notifications = NotificationHandler.list_notifications(
        other_user, workspace=workspace
    )

    assert Notification.objects.count() == 0
    assert user_notifications.count() == 0
    assert other_user_notifications.count() == 0

    grouper = UserNotificationsGrouper()
    grouper.add(notification_1, [user.id, other_user.id])
    grouper.add(notification_2, [user.id])
    grouper.create_all_notifications_and_trigger_task()

    # counts are still 0 because notifications are marked as queued and the task
    # has not been executed yet
    assert Notification.objects.count() == 2
    assert user_notifications.count() == 0
    assert other_user_notifications.count() == 0

    assert mocked_send_queued_notifications_to_users.called_once()

    qs = NotificationRecipient.objects.filter(queued=True)
    assert qs.filter(recipient=user).count() == 2
    assert qs.filter(recipient=other_user).count() == 1


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.tasks.broadcast_to_users.apply")
@pytest.mark.enable_signals(
    "baserow.core.notifications.tasks.send_queued_notifications_to_users.delay",
    "baserow.ws.tasks.broadcast_to_users.delay",
)
def test_queued_notifications_are_sent_grouped_by_user(
    mocked_broadcast_to_users,
    data_fixture,
    mutable_notification_type_registry,
):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(members=[user, other_user])

    data_fixture.register_notification_type(notification_type="test 1")
    data_fixture.register_notification_type(notification_type="test 2")

    notification_1 = NotificationHandler.construct_notification(
        notification_type="test 1", workspace=workspace
    )
    notification_2 = NotificationHandler.construct_notification(
        notification_type="test 2", workspace=workspace
    )

    grouper = UserNotificationsGrouper()
    grouper.add(notification_1, [user.id, other_user.id])
    grouper.add(notification_2, [user.id])
    grouper.create_all_notifications_and_trigger_task()

    user_notifications = NotificationRecipient.objects.filter(recipient=user)
    other_user_notifications = NotificationRecipient.objects.filter(
        recipient=other_user
    )

    assert mocked_broadcast_to_users.call_count == 2
    args = mocked_broadcast_to_users.call_args_list
    assert args[0][0] == call(
        [user.id],
        {
            "type": "notifications_created",
            "notifications": NotificationRecipientSerializer(
                user_notifications, many=True
            ).data,
        },
    )
    assert args[1][0] == call(
        [other_user.id],
        {
            "type": "notifications_created",
            "notifications": NotificationRecipientSerializer(
                other_user_notifications, many=True
            ).data,
        },
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_not_all_notification_types_are_included_in_the_email_notification_summary(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    options = UserProfile.EmailNotificationFrequencyOptions

    with custom_notification_types_registered() as (
        TestNotification,
        ExcludedFromEmailTestNotification,
    ):
        user_1 = data_fixture.create_user(email_notification_frequency=options.INSTANT)
        data_fixture.create_notification_for_users(
            recipients=[user_1], notification_type=TestNotification.type
        )
        data_fixture.create_notification_for_users(
            recipients=[user_1],
            notification_type=ExcludedFromEmailTestNotification.type,
        )

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.DAILY)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.WEEKLY)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.INSTANT)
        )
        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_1_summary_email = summary_emails[0]
        assert user_1_summary_email.to == [user_1.email]
        assert (
            user_1_summary_email.get_subject()
            == "You have 1 new notification - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                }
            ],
            "new_notifications_count": 1,
            "unlisted_notifications_count": 0,
        }
        user_1_summary_email_context = user_1_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_1_summary_email_context[k] == v


@pytest.mark.django_db
def test_no_email_without_renderable_notifications(
    data_fixture, mutable_notification_type_registry
):
    options = UserProfile.EmailNotificationFrequencyOptions

    with custom_notification_types_registered() as (
        _,
        ExcludedFromEmailTestNotification,
    ):
        user_1 = data_fixture.create_user(email_notification_frequency=options.INSTANT)
        data_fixture.create_notification_for_users(
            recipients=[user_1],
            notification_type=ExcludedFromEmailTestNotification.type,
        )

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.DAILY)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.WEEKLY)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.INSTANT)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0


@patch("baserow.core.notifications.handler.get_mail_connection")
@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("email_notification_frequency", ["daily", "weekly"])
def test_user_with_daily_email_notification_frequency_settings(
    mock_get_mail_connection,
    email_notification_frequency,
    data_fixture,
    mutable_notification_type_registry,
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    with custom_notification_types_registered() as (
        TestNotification,
        ExcludedFromEmailTestNotification,
    ):
        options = UserProfile.EmailNotificationFrequencyOptions

        user_1 = data_fixture.create_user(
            email_notification_frequency=email_notification_frequency
        )
        user_2 = data_fixture.create_user(email_notification_frequency=options.INSTANT)
        user_3 = data_fixture.create_user(email_notification_frequency=options.NEVER)
        data_fixture.create_notification_for_users(
            recipients=[user_1, user_2, user_3], notification_type=TestNotification.type
        )
        data_fixture.create_notification_for_users(
            recipients=[user_2], notification_type=TestNotification.type
        )
        data_fixture.create_notification_for_users(
            recipients=[user_1],
            notification_type=ExcludedFromEmailTestNotification.type,
        )

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=email_notification_frequency)
        )
        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_1_summary_email = summary_emails[0]
        assert user_1_summary_email.to == [user_1.email]
        assert (
            user_1_summary_email.get_subject()
            == "You have 1 new notification - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                }
            ],
            "new_notifications_count": 1,
            "unlisted_notifications_count": 0,
        }
        user_1_summary_email_context = user_1_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_1_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_are_sent_only_after_setting_is_activated(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection
    options = UserProfile.EmailNotificationFrequencyOptions

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user(email_notification_frequency=options.NEVER)
        data_fixture.create_notification_for_users(
            recipients=[user_1], notification_type=TestNotification.type
        )
        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0

        user_1 = UserHandler().update_user(
            user_1, email_notification_frequency=options.INSTANT
        )
        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == []
        assert mock_get_mail_connection.call_count == 0

        data_fixture.create_notification_for_users(
            recipients=[user_1], notification_type=TestNotification.type
        )

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )

        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_1_summary_email = summary_emails[0]
        assert user_1_summary_email.to == [user_1.email]
        assert (
            user_1_summary_email.get_subject()
            == "You have 1 new notification - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                }
            ],
            "new_notifications_count": 1,
            "unlisted_notifications_count": 0,
        }
        user_1_summary_email_context = user_1_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_1_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(MAX_NOTIFICATIONS_LISTED_PER_EMAIL=10)
def test_email_notifications_are_included_up_to_email_limit(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection
    limit = settings.MAX_NOTIFICATIONS_LISTED_PER_EMAIL

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user()

        for _ in range(limit + 1):
            data_fixture.create_notification_for_users(
                recipients=[user_1], notification_type=TestNotification.type
            )

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == limit
        assert res.users_with_notifications[0].total_unsent_count == limit + 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_1_summary_email = summary_emails[0]
        assert user_1_summary_email.to == [user_1.email]
        assert (
            user_1_summary_email.get_subject()
            == f"You have {limit + 1} new notifications - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                }
                for _ in range(limit)
            ],
            "new_notifications_count": limit + 1,
            "unlisted_notifications_count": 1,
        }
        user_1_summary_email_context = user_1_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_1_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
def test_email_notifications_are_sent_just_once(
    data_fixture, mutable_notification_type_registry
):
    options = UserProfile.EmailNotificationFrequencyOptions

    with custom_notification_types_registered() as (
        TestNotification,
        ExcludedFromEmailTestNotification,
    ):
        user_1 = data_fixture.create_user(email_notification_frequency=options.INSTANT)
        data_fixture.create_notification_for_users(
            recipients=[user_1], notification_type=TestNotification.type
        )
        data_fixture.create_notification_for_users(
            recipients=[user_1],
            notification_type=ExcludedFromEmailTestNotification.type,
        )

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 1
        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.INSTANT)
        )
        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0
        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(profile__email_notification_frequency=options.INSTANT)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_broadcast_notifications_are_not_sent_by_email(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    data_fixture.create_user(
        email_notification_frequency=UserProfile.EmailNotificationFrequencyOptions.INSTANT
    )
    data_fixture.create_broadcast_notification()

    user_1 = data_fixture.create_user()

    res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
        Q(pk=user_1.pk)
    )
    assert res.users_with_notifications == []
    assert res.remaining_users_to_notify_count == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(EMAIL_NOTIFICATIONS_ENABLED=False)
def test_email_notifications_are_not_sent_if_global_setting_is_disabled(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user()

        data_fixture.create_notification_for_users(
            recipients=[user_1], notification_type=TestNotification.type
        )

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 1

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == [user_1]
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_not_called()

        # Ensure no more notifications are scheduled to be sent
        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_are_not_sent_if_already_read_by_user(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user_1)

        data_fixture.create_workspace_notification_for_users(
            recipients=[user_1],
            notification_type=TestNotification.type,
            workspace=workspace,
        )

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 1

        NotificationHandler.mark_all_notifications_as_read(user_1, workspace)

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_not_called()

        notification = data_fixture.create_workspace_notification_for_users(
            recipients=[user_1],
            notification_type=TestNotification.type,
            workspace=workspace,
        )

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 1

        NotificationHandler.mark_notification_as_read(user_1, notification)

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
def test_email_notifications_are_not_sent_if_already_cleared_by_user(
    mock_get_mail_connection, data_fixture, mutable_notification_type_registry
):
    mock_connection = MagicMock()
    mock_get_mail_connection.return_value = mock_connection

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user()
        workspace = data_fixture.create_workspace(user=user_1)

        data_fixture.create_workspace_notification_for_users(
            recipients=[user_1],
            notification_type=TestNotification.type,
            workspace=workspace,
        )

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 1

        NotificationHandler.clear_all_notifications(user_1, workspace)

        assert NotificationRecipient.objects.filter(email_scheduled=True).count() == 0

        res = NotificationHandler.send_unread_notifications_by_email_to_users_matching_filters(
            Q(pk=user_1.pk)
        )
        assert res.users_with_notifications == []
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_not_called()

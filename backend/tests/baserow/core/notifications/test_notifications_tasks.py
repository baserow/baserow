from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from django.test import override_settings

import pytest
from celery.exceptions import Retry
from freezegun import freeze_time
from loguru import logger

from baserow.core.notifications.tasks import (
    send_daily_and_weekly_notifications_summary_by_email,
    send_daily_notifications_email_to_users,
    send_weekly_notifications_email_to_users,
)

from .utils import custom_notification_types_registered


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY=14)
def test_daily_report_is_sent_at_correct_time_according_to_user_timezone(
    mock_get_mail_connection, data_fixture
):
    with custom_notification_types_registered() as (TestNotification, _):
        # UTC+2
        user_1 = data_fixture.create_user(
            timezone="Europe/Rome", email_notification_frequency="daily"
        )
        # UTC+4
        user_2 = data_fixture.create_user(
            timezone="Asia/Dubai", email_notification_frequency="daily"
        )

        with freeze_time("2023-08-04 08:00:00"):
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_1, user_2],
                data={"test": True},
            )
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_2],
                data={"test": True},
            )

        assert user_1.profile.last_notifications_email_sent_at is None

        res = send_daily_notifications_email_to_users(
            datetime(2023, 8, 4, 11, 0, tzinfo=timezone.utc)
        )

        assert res.users_with_notifications == []

        mock_mail_connection = MagicMock()
        mock_get_mail_connection.return_value = mock_mail_connection

        # The email is sent for user_1 because it's 14:00 in Rome, but not for user_2
        with freeze_time("2023-08-04 12:00:00"):
            res = send_daily_notifications_email_to_users()

        assert res.users_with_notifications == [user_1]
        user_1.refresh_from_db()
        assert user_1.profile.last_notifications_email_sent_at == datetime(
            2023, 8, 4, 12, 0, 0, tzinfo=timezone.utc
        )
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_mail_connection.send_messages.call_args[0][0]
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

        mock_mail_connection.reset_mock()
        mock_get_mail_connection.reset_mock()

        # we can also pass a datetime to the function, sending the email for users
        # in dubai

        assert user_2.profile.last_notifications_email_sent_at is None

        with freeze_time("2023-08-04 10:00:00"):
            res = send_daily_notifications_email_to_users()

        assert res.users_with_notifications == [user_2]
        user_2.refresh_from_db()
        assert user_2.profile.last_notifications_email_sent_at == datetime(
            2023, 8, 4, 10, 0, 0, tzinfo=timezone.utc
        )

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_mail_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_2_summary_email = summary_emails[0]
        assert user_2_summary_email.to == [user_2.email]
        assert (
            user_2_summary_email.get_subject()
            == "You have 2 new notifications - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                },
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                },
            ],
            "new_notifications_count": 2,
            "unlisted_notifications_count": 0,
        }
        user_2_summary_email_context = user_2_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_2_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY=14)
@override_settings(EMAIL_NOTIFICATIONS_WEEKLY_DAY_OF_WEEK=4)
def test_weekly_report_is_sent_at_correct_date_and_time_according_to_user_timezone(
    mock_get_mail_connection, data_fixture
):
    with custom_notification_types_registered() as (TestNotification, _):
        # UTC+2
        user_1 = data_fixture.create_user(
            timezone="Europe/Rome", email_notification_frequency="weekly"
        )
        # UTC+4
        user_2 = data_fixture.create_user(
            timezone="Asia/Dubai", email_notification_frequency="weekly"
        )

        with freeze_time("2023-07-04 08:00:00"):
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_1, user_2],
                data={"test": True},
            )
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_2],
                data={"test": True},
            )

        assert user_1.profile.last_notifications_email_sent_at is None

        res = send_weekly_notifications_email_to_users(
            datetime(2023, 7, 4, 12, 0, tzinfo=timezone.utc)
        )

        assert res.users_with_notifications == []

        mock_mail_connection = MagicMock()
        mock_get_mail_connection.return_value = mock_mail_connection

        # The email is sent for user_1 because it's 14:00 in Rome, but not for user_2
        with freeze_time("2023-08-04 12:00:00"):
            res = send_weekly_notifications_email_to_users()

        assert res.users_with_notifications == [user_1]
        user_1.refresh_from_db()
        assert user_1.profile.last_notifications_email_sent_at == datetime(
            2023, 8, 4, 12, 0, 0, tzinfo=timezone.utc
        )
        assert len(res.users_with_notifications[0].unsent_email_notifications) == 1
        assert res.remaining_users_to_notify_count == 0

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_mail_connection.send_messages.call_args[0][0]
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

        mock_mail_connection.reset_mock()
        mock_get_mail_connection.reset_mock()

        # we can also pass a datetime to the function, sending the email for users
        # in dubai

        assert user_2.profile.last_notifications_email_sent_at is None

        with freeze_time("2023-08-04 10:00:00"):
            res = send_weekly_notifications_email_to_users()

        assert res.users_with_notifications == [user_2]
        user_2.refresh_from_db()
        assert user_2.profile.last_notifications_email_sent_at == datetime(
            2023, 8, 4, 10, 0, 0, tzinfo=timezone.utc
        )

        mock_get_mail_connection.assert_called_once_with(fail_silently=False)
        summary_emails = mock_mail_connection.send_messages.call_args[0][0]
        assert len(summary_emails) == 1
        user_2_summary_email = summary_emails[0]
        assert user_2_summary_email.to == [user_2.email]
        assert (
            user_2_summary_email.get_subject()
            == "You have 2 new notifications - Baserow"
        )

        expected_context = {
            "notifications": [
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                },
                {
                    "title": "Test notification",
                    "description": None,
                    "url": None,
                },
            ],
            "new_notifications_count": 2,
            "unlisted_notifications_count": 0,
        }
        user_2_summary_email_context = user_2_summary_email.get_context()

        for k, v in expected_context.items():
            assert user_2_summary_email_context[k] == v


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY=14)
@override_settings(EMAIL_NOTIFICATIONS_WEEKLY_DAY_OF_WEEK=4)
@override_settings(EMAIL_NOTIFICATIONS_LIMIT_PER_TASK={"daily": 1, "weekly": 1})
@override_settings(EMAIL_NOTIFICATIONS_AUTO_RETRY_IF_LIMIT_REACHED_AFTER=None)
def test_daily_report_is_sent_up_to_max_limit_per_task_and_log_the_error(
    mock_get_mail_connection, data_fixture, mocker
):
    mock_logger_error = mocker.patch.object(logger, "error")

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user(
            email="u1@test.com", email_notification_frequency="daily"
        )
        user_2 = data_fixture.create_user(
            email="u2@test.com", email_notification_frequency="daily"
        )
        user_3 = data_fixture.create_user(
            email="u3@test.com", email_notification_frequency="weekly"
        )
        user_4 = data_fixture.create_user(
            email="u4@test.com", email_notification_frequency="weekly"
        )

        with freeze_time("2023-08-04 13:00:00"):
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_1, user_2, user_3, user_4],
            )

        mock_mail_connection = MagicMock()
        mock_get_mail_connection.return_value = mock_mail_connection

        with freeze_time("2023-08-04 14:00:00"):
            send_daily_and_weekly_notifications_summary_by_email()

        # the mail connection is called twice, once for daily and once for weekly,
        # but only one email is sent for each because of the limit we set

        mock_get_mail_connection.call_count == 2
        daily_summary_emails = mock_mail_connection.send_messages.call_args_list[0][0][
            0
        ]
        assert len(daily_summary_emails) == 1
        assert daily_summary_emails[0].to in [[user_1.email], [user_2.email]]
        weekly_summary_emails = mock_mail_connection.send_messages.call_args_list[1][0][
            0
        ]
        assert len(weekly_summary_emails) == 1
        assert weekly_summary_emails[0].to in [[user_3.email], [user_4.email]]

        mock_logger_error.assert_called_once_with(
            "The maximum number of email of notifications was reached.\n"
            "Daily sent: 1.\n"
            "Daily remaining: 1.\n"
            "Weekly sent: 1.\n"
            "Weekly reamaining: 1.\n"
        )

        mock_get_mail_connection.reset_mock()
        mock_mail_connection.reset_mock()
        mock_logger_error.reset_mock()

        # we need to manually call the function again at the same hour to send
        # the remaining emails
        with freeze_time("2023-08-04 14:10:00"):
            send_daily_and_weekly_notifications_summary_by_email()

        mock_get_mail_connection.call_count == 2
        daily_summary_emails_2 = mock_mail_connection.send_messages.call_args_list[0][
            0
        ][0]
        assert len(daily_summary_emails_2) == 1
        assert daily_summary_emails_2[0].to in [[user_1.email], [user_2.email]]
        assert daily_summary_emails_2[0].to != daily_summary_emails[0].to

        weekly_summary_emails_2 = mock_mail_connection.send_messages.call_args_list[1][
            0
        ][0]
        assert len(weekly_summary_emails_2) == 1
        assert weekly_summary_emails_2[0].to in [[user_3.email], [user_4.email]]
        assert weekly_summary_emails_2[0].to != weekly_summary_emails[0].to

        mock_logger_error.assert_not_called()


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.notifications.handler.get_mail_connection")
@override_settings(EMAIL_NOTIFICATIONS_DAILY_HOUR_OF_DAY=14)
@override_settings(EMAIL_NOTIFICATIONS_WEEKLY_DAY_OF_WEEK=4)
@override_settings(EMAIL_NOTIFICATIONS_LIMIT_PER_TASK={"daily": 1, "weekly": 1})
@override_settings(EMAIL_NOTIFICATIONS_AUTO_RETRY_IF_LIMIT_REACHED_AFTER=3)
def test_daily_report_is_sent_up_to_max_limit_per_task_log_the_error_and_retry_after(
    mock_get_mail_connection, data_fixture, mocker
):
    mock_logger_error = mocker.patch.object(logger, "error")

    with custom_notification_types_registered() as (TestNotification, _):
        user_1 = data_fixture.create_user(
            email="u1@test.com", email_notification_frequency="daily"
        )
        user_2 = data_fixture.create_user(
            email="u2@test.com", email_notification_frequency="daily"
        )
        user_3 = data_fixture.create_user(
            email="u3@test.com", email_notification_frequency="weekly"
        )
        user_4 = data_fixture.create_user(
            email="u4@test.com", email_notification_frequency="weekly"
        )

        with freeze_time("2023-08-04 13:00:00"):
            data_fixture.create_notification_for_users(
                notification_type=TestNotification.type,
                recipients=[user_1, user_2, user_3, user_4],
            )

        mock_mail_connection = MagicMock()
        mock_get_mail_connection.return_value = mock_mail_connection

        with freeze_time("2023-08-04 14:00:00"), pytest.raises(Retry):
            send_daily_and_weekly_notifications_summary_by_email()

        # the mail connection is called twice, once for daily and once for weekly,
        # but only one email is sent for each because of the limit we set

        mock_get_mail_connection.call_count == 2
        daily_summary_emails = mock_mail_connection.send_messages.call_args_list[0][0][
            0
        ]
        assert len(daily_summary_emails) == 1
        assert daily_summary_emails[0].to in [[user_1.email], [user_2.email]]
        weekly_summary_emails = mock_mail_connection.send_messages.call_args_list[1][0][
            0
        ]
        assert len(weekly_summary_emails) == 1
        assert weekly_summary_emails[0].to in [[user_3.email], [user_4.email]]

        mock_logger_error.assert_called_once_with(
            "The maximum number of email of notifications was reached.\n"
            "Daily sent: 1.\n"
            "Daily remaining: 1.\n"
            "Weekly sent: 1.\n"
            "Weekly reamaining: 1.\n"
        )

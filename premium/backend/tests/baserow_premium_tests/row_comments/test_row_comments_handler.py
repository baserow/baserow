from unittest.mock import call, patch

from django.test.utils import override_settings

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.row_comments.exceptions import (
    InvalidRowCommentException,
    RowCommentDoesNotExist,
    UserNotRowCommentAuthorException,
)
from baserow_premium.row_comments.handler import (
    RowCommentHandler,
    RowCommentsNotificationModes,
)
from baserow_premium.row_comments.models import RowComment, RowCommentsNotificationMode
from freezegun import freeze_time

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_make_null_comment_using_handler(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    with pytest.raises(InvalidRowCommentException):
        # noinspection PyTypeChecker
        RowCommentHandler.create_comment(user, table.id, rows[0].id, None)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_make_blank_comment_using_handler(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("")

    with pytest.raises(InvalidRowCommentException):
        RowCommentHandler.create_comment(user, table.id, rows[0].id, message)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_create_comment_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(first_name="Test User")
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    with pytest.raises(FeaturesNotAvailableError):
        RowCommentHandler.create_comment(user, table.id, rows[0].id, "Test")


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_create_comment_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [table.database.workspace_id]
    )

    RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        RowCommentHandler.create_comment(user, table.id, rows[0].id, message)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.row_comments.signals.row_comment_created.send")
def test_row_comment_created_signal_called(
    mock_row_comment_created, premium_data_fixture
):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    with freeze_time("2020-01-02 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    mock_row_comment_created.assert_called_once()
    args = mock_row_comment_created.call_args
    assert args.kwargs["mentions"] == []
    assert args.kwargs["row_comment"] == c
    assert args.kwargs["user"] == user
    assert args.kwargs["row"].id == rows[0].id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comment_can_only_be_updated_by_author(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    other_user = premium_data_fixture.create_user(
        first_name="other_user", has_active_premium_license=True
    )
    other_user_in_same_workspace = premium_data_fixture.create_user(
        first_name="other_user_same_workspace", has_active_premium_license=True
    )

    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    CoreHandler().add_user_to_workspace(
        table.database.workspace, other_user_in_same_workspace
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    with freeze_time("2020-01-01 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    updated_message = premium_data_fixture.create_comment_message_from_plain_text(
        "updated comment"
    )
    with pytest.raises(UserNotInWorkspace):
        RowCommentHandler.update_comment(other_user, c, updated_message)

    CoreHandler().add_user_to_workspace(table.database.workspace, other_user)

    with pytest.raises(UserNotRowCommentAuthorException):
        RowCommentHandler.update_comment(
            other_user_in_same_workspace, c, updated_message
        )

    with freeze_time("2020-01-01 12:01"):
        updated_comment = RowCommentHandler.update_comment(user, c, updated_message)

    assert updated_comment.message == updated_message
    assert updated_comment.id == c.id
    assert updated_comment.created_on.strftime("%Y-%m-%d %H:%M") == "2020-01-01 12:00"
    assert updated_comment.updated_on.strftime("%Y-%m-%d %H:%M") == "2020-01-01 12:01"


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.row_comments.signals.row_comment_updated.send")
def test_row_comment_updated_signal_called(
    mock_row_comment_updated, premium_data_fixture
):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    updated_message = premium_data_fixture.create_comment_message_from_plain_text(
        "updated comment"
    )
    RowCommentHandler.update_comment(user, c, updated_message)

    mock_row_comment_updated.assert_called_once()
    args = mock_row_comment_updated.call_args

    assert args.kwargs["mentions"] == []
    assert args.kwargs["row_comment"] == c
    assert args.kwargs["user"] == user
    assert args.kwargs["row"].id == rows[0].id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comment_can_only_be_deleted_by_author(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    other_user = premium_data_fixture.create_user(
        first_name="other_user", has_active_premium_license=True
    )
    other_user_in_same_workspace = premium_data_fixture.create_user(
        first_name="other_user_same_workspace", has_active_premium_license=True
    )

    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    CoreHandler().add_user_to_workspace(
        table.database.workspace, other_user_in_same_workspace
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    with freeze_time("2020-01-01 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    with pytest.raises(UserNotInWorkspace):
        RowCommentHandler.delete_comment(other_user, c)

    with pytest.raises(UserNotRowCommentAuthorException):
        RowCommentHandler.delete_comment(other_user_in_same_workspace, c)

    with freeze_time("2020-01-01 12:01"):
        RowCommentHandler.delete_comment(user, c)

    assert c.trashed
    with pytest.raises(RowCommentDoesNotExist):
        RowCommentHandler.get_comment_by_id(user, table.id, c.id)

    trashed_comment = RowComment.objects_and_trash.get(id=c.id)
    assert trashed_comment.id == c.id
    assert trashed_comment.trashed


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.row_comments.signals.row_comment_deleted.send")
def test_row_comment_deleted_signal_called(
    mock_row_comment_deleted, premium_data_fixture
):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    RowCommentHandler.delete_comment(user, c)

    mock_row_comment_deleted.assert_called_once()
    args = mock_row_comment_deleted.call_args

    assert args == call(RowCommentHandler, row_comment=c, user=user, mentions=[])


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comment_mentions_are_created(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    user2 = premium_data_fixture.create_user(
        first_name="test_user2",
        has_active_premium_license=True,
        workspace=table.database.workspace,
    )
    message = premium_data_fixture.create_comment_message_with_mentions([user2])

    with freeze_time("2020-01-02 12:00"):
        c = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)

    assert list(c.mentions.all()) == [user2]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comment_cant_mention_user_outside_workspace(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    user2 = premium_data_fixture.create_user(
        first_name="test_user2",
        has_active_premium_license=True,
    )

    message = premium_data_fixture.create_comment_message_with_mentions([user2])

    comment = RowCommentHandler.create_comment(user, table.id, rows[0].id, message)
    assert comment.mentions.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_change_row_comments_notification_mode(premium_data_fixture):
    user = premium_data_fixture.create_user(
        first_name="test_user", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    assert RowCommentsNotificationMode.objects.count() == 0

    RowCommentHandler.update_row_comments_notification_mode(
        user, table.id, rows[0].id, RowCommentsNotificationModes.MODE_ALL_COMMENTS
    )

    assert RowCommentsNotificationMode.objects.count() == 1

    RowCommentHandler.update_row_comments_notification_mode(
        user, table.id, rows[0].id, RowCommentsNotificationModes.MODE_ONLY_MENTIONS
    )

    assert (
        RowCommentsNotificationMode.objects.filter(
            mode=RowCommentsNotificationModes.MODE_ONLY_MENTIONS
        ).count()
        == 1
    )

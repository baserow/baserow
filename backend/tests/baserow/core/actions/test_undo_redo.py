import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.api.sessions import set_untrusted_client_session_id
from baserow.contrib.database.fields.actions import UpdateFieldActionType
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    UndoableActionCustomCleanupMixin,
    UndoableActionType,
    action_type_registry,
)
from baserow.core.action.scopes import RootActionScopeType, WorkspaceActionScopeType
from baserow.core.actions import (
    CreateApplicationActionType,
    CreateWorkspaceActionType,
    DeleteWorkspaceActionType,
    UpdateApplicationActionType,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import WORKSPACE_USER_PERMISSION_ADMIN, Application, Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import (
    assert_undo_redo_actions_are_valid,
    assert_undo_redo_actions_fails_with_error,
)

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_action_with_matching_session_and_category_undoes(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not Workspace.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_action_with_matching_session_and_not_matching_category_does_nothing(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace_user = action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    fake_category_which_wont_match = cast(
        ActionScopeStr,
        CreateWorkspaceActionType.scope() + "_fake_category_which_wont_match",
    )
    actions = ActionHandler.undo(user, [fake_category_which_wont_match], session_id)

    assert not actions
    assert Workspace.objects.filter(id=workspace_user.workspace_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_action_with_not_matching_session_and_not_matching_category_does_nothing(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace_user = action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    fake_category_which_wont_match = cast(
        ActionScopeStr,
        CreateWorkspaceActionType.scope() + "_fake_category_which_wont_match",
    )
    other_session_which_wont_match = session_id + "_fake"
    actions = ActionHandler.undo(
        user, [fake_category_which_wont_match], other_session_which_wont_match
    )

    assert not actions
    assert Workspace.objects.filter(id=workspace_user.workspace_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_action_with_not_matching_session_and_matching_category_does_nothing(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace_user = action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    other_session_which_wont_match = session_id + "_fake"
    actions = ActionHandler.undo(
        user,
        [CreateWorkspaceActionType.scope()],
        other_session_which_wont_match,
    )

    assert not actions
    assert Workspace.objects.filter(id=workspace_user.workspace_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_action_with_matching_session_and_category_redoes(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace_user = action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not Workspace.objects.exists()

    actions = ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])
    assert Workspace.objects.filter(id=workspace_user.workspace_id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_action_with_matching_session_and_not_matching_category_doesnt_redo(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])
    assert not Workspace.objects.exists()

    fake_category_which_wont_match = cast(
        ActionScopeStr,
        CreateWorkspaceActionType.scope() + "_fake_category_which_wont_match",
    )
    actions = ActionHandler.redo(user, [fake_category_which_wont_match], session_id)

    assert not actions
    assert not Workspace.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_action_with_not_matching_session_and_not_matching_category_doesnt_redo(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])
    assert not Workspace.objects.exists()

    fake_category_which_wont_match = cast(
        ActionScopeStr,
        CreateWorkspaceActionType.scope() + "_fake_category_which_wont_match",
    )
    other_session_which_wont_match = session_id + "_fake"

    actions = ActionHandler.redo(
        user, [fake_category_which_wont_match], other_session_which_wont_match
    )

    assert not actions
    assert not Workspace.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_action_with_not_matching_session_and_matching_category_doesnt_redo(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])
    assert not Workspace.objects.exists()

    other_session_which_wont_match = session_id + "_fake"

    actions = ActionHandler.redo(
        user,
        [CreateWorkspaceActionType.scope()],
        other_session_which_wont_match,
    )

    assert not actions
    assert not Workspace.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_with_multiple_sessions_undoes_only_in_provided_session(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    same_user_with_different_session = User.objects.get(id=user.id)
    set_untrusted_client_session_id(
        same_user_with_different_session, "different-session"
    )

    workspace_user_from_first_session = action_type_registry.get_by_type(
        CreateWorkspaceActionType
    ).do(user, workspace_name="test")
    workspace_user_from_second_session = action_type_registry.get_by_type(
        CreateWorkspaceActionType
    ).do(same_user_with_different_session, workspace_name="test2")

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not actions
    assert not Workspace.objects.filter(
        id=workspace_user_from_first_session.workspace_id
    ).exists()
    assert Workspace.objects.filter(
        id=workspace_user_from_second_session.workspace_id
    ).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_with_multiple_sessions_redoes_only_in_provided_session(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    same_user_with_different_session = User.objects.get(id=user.id)
    other_session_id = "different-session"
    set_untrusted_client_session_id(same_user_with_different_session, other_session_id)

    workspace_user_from_first_session = action_type_registry.get_by_type(
        CreateWorkspaceActionType
    ).do(user, workspace_name="test")
    workspace_user_from_second_session = action_type_registry.get_by_type(
        CreateWorkspaceActionType
    ).do(same_user_with_different_session, workspace_name="test2")

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], other_session_id)
    assert not Workspace.objects.filter(
        id=workspace_user_from_first_session.workspace_id
    ).exists()
    assert not Workspace.objects.filter(
        id=workspace_user_from_second_session.workspace_id
    ).exists()

    # Do something else in the other session, this should not affect the redo of
    # the first session.
    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        same_user_with_different_session, workspace_name="test2"
    )

    actions = ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])
    actions = ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert not actions

    assert Workspace.objects.filter(
        id=workspace_user_from_first_session.workspace_id
    ).exists()
    assert not Workspace.objects.filter(
        id=workspace_user_from_second_session.workspace_id
    ).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_with_multiple_users_undoes_only_in_the_own_users_actions(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user(session_id=session_id)

    workspace_created_by_first_user = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test")
        .workspace
    )
    workspace_created_by_second_user = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user2, workspace_name="test2")
        .workspace
    )

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert not actions

    assert not Workspace.objects.filter(id=workspace_created_by_first_user.id).exists()
    assert Workspace.objects.filter(id=workspace_created_by_second_user.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_with_multiple_users_redoes_only_in_the_own_users_actions(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    user2 = data_fixture.create_user(session_id=session_id)

    workspace_created_by_first_user = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test")
        .workspace
    )
    workspace_created_by_second_user = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user2, workspace_name="test2")
        .workspace
    )

    user2_actions = ActionHandler.undo(
        user2, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(user2_actions, [CreateWorkspaceActionType])

    actions = ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])

    actions = ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert_undo_redo_actions_are_valid(actions, [CreateWorkspaceActionType])

    actions = ActionHandler.redo(user, [CreateWorkspaceActionType.scope()], session_id)
    assert not actions

    assert Workspace.objects.filter(id=workspace_created_by_first_user.id).exists()
    assert not Workspace.objects.filter(id=workspace_created_by_second_user.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_when_undo_fails_can_try_undo_next_action(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace1 = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test")
        .workspace
    )
    workspace2 = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test2")
        .workspace
    )
    TrashHandler.permanently_delete(workspace2)

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        undone_actions, [CreateWorkspaceActionType]
    )

    assert Workspace.objects.filter(id=workspace1.id).exists()

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not Workspace.objects.filter(id=workspace1.id).exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
@patch("baserow.core.signals.workspace_deleted.send")
def test_when_undo_fails_the_action_is_rolled_back(
    mock_workspace_deleted,
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test2")
        .workspace
    )

    mock_workspace_deleted.side_effect = Exception(
        "Error that should make the undo rollback"
    )

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert undone_actions
    assert undone_actions[0].error, "Undo/redo action should have an error"

    assert Workspace.objects.filter(id=workspace.id).exists(), (
        "The workspace should still exist as the undo transaction should have failed and "
        "rolled back. "
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_when_undo_fails_can_try_redo_undo_to_try_again(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    other_user = data_fixture.create_user(session_id=session_id)

    # User A creates a workspace
    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test")
        .workspace
    )

    # User B deletes the workspace
    locked_workspace = CoreHandler().get_workspace_for_update(workspace_id=workspace.id)
    data_fixture.create_user_workspace(
        workspace=locked_workspace,
        user=other_user,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    action_type_registry.get_by_type(DeleteWorkspaceActionType).do(
        other_user, workspace=locked_workspace
    )

    # User A tries to Undo the creation of the workspace, it fails as it has already
    # been deleted.
    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        undone_actions, [DeleteWorkspaceActionType]
    )

    # User B Undoes the deletion, recreating the workspace
    ActionHandler.undo(other_user, [DeleteWorkspaceActionType.scope()], session_id)

    # User A Redoes which does nothing
    redone_actions = ActionHandler.redo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        redone_actions, [DeleteWorkspaceActionType]
    )

    # User A can now Undo the creation of the workspace as it exists again
    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not Workspace.objects.exists()


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_when_redo_fails_the_action_is_rolled_back(
    data_fixture,
):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)

    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test2")
        .workspace
    )
    action_type_registry.get_by_type(DeleteWorkspaceActionType).do(
        user, CoreHandler().get_workspace_for_update(workspace.id)
    )

    # Undo the deletion restoring the workspace.
    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    with patch(
        "baserow.core.signals.workspace_deleted.send"
    ) as mock_workspace_deleted_send:
        mock_workspace_deleted_send.side_effect = Exception(
            "Error that should make the redo rollback"
        )

        # Redo the deletion
        redone_actions = ActionHandler.redo(
            user, [CreateWorkspaceActionType.scope()], session_id
        )
    assert_undo_redo_actions_fails_with_error(
        redone_actions, [CreateWorkspaceActionType]
    )

    assert Workspace.objects.filter(id=workspace.id).exists(), (
        "The workspace should still exist as the redo should have rolled back when it "
        "failed. "
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_actions_which_were_updated_less_than_configured_limit_ago_not_cleaned_up(
    data_fixture, settings
):
    now = datetime.now(tz=timezone.utc)
    num_minutes_where_actions_shouldnt_be_cleaned = timedelta(
        minutes=int(settings.MINUTES_UNTIL_ACTION_CLEANED_UP) / 2
    )
    with transaction.atomic():
        with freeze_time(now - num_minutes_where_actions_shouldnt_be_cleaned):
            _create_two_no_custom_cleanup_actions(data_fixture)

    with freeze_time(now):
        assert Action.objects.count() == 2
        ActionHandler.clean_up_old_undoable_actions()
        assert Action.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_cleanup_doesnt_do_n_queries_per_action_when_they_have_no_custom_cleanup(
    data_fixture, settings, django_assert_num_queries
):
    now = datetime.now(tz=timezone.utc)
    num_minutes_where_actions_will_be_old_for_clean = timedelta(
        minutes=int(settings.MINUTES_UNTIL_ACTION_CLEANED_UP) * 2
    )
    # Make two actions and record the number of queries done.
    with freeze_time(now - num_minutes_where_actions_will_be_old_for_clean):
        _create_two_no_custom_cleanup_actions(data_fixture)

    with freeze_time(now):
        assert Action.objects.count() == 2
        with CaptureQueriesContext(connection) as clean_up_two_actions:
            ActionHandler.clean_up_old_undoable_actions()
        assert Action.objects.count() == 0

    # Now make 4 actions and record the number of queries done
    with freeze_time(now - num_minutes_where_actions_will_be_old_for_clean):
        _create_two_no_custom_cleanup_actions(data_fixture)
        _create_two_no_custom_cleanup_actions(data_fixture)

    with freeze_time(now):
        assert Action.objects.count() == 4
        with CaptureQueriesContext(connection) as clean_up_four_actions:
            ActionHandler.clean_up_old_undoable_actions()
        assert Action.objects.count() == 0

    # They should be the same as we should be doing a single bulk query to delete all
    # actions without a custom cleanup.
    assert len(clean_up_two_actions.captured_queries) == len(
        clean_up_four_actions.captured_queries
    )


def _create_two_no_custom_cleanup_actions(data_fixture):
    user = data_fixture.create_user()
    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test2")
        .workspace
    )
    action_type_registry.get_by_type(DeleteWorkspaceActionType).do(
        user, CoreHandler().get_workspace_for_update(workspace.id)
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_cleanup_does_extra_cleanup_for_actions_implementing_it(data_fixture, settings):
    now = datetime.now(tz=timezone.utc)
    num_minutes_where_actions_will_be_old_enough_for_cleaning = timedelta(
        minutes=int(settings.MINUTES_UNTIL_ACTION_CLEANED_UP) * 2
    )
    with transaction.atomic():
        with freeze_time(
            now - num_minutes_where_actions_will_be_old_enough_for_cleaning
        ):
            _create_two_no_custom_cleanup_actions(data_fixture)
            _create_an_action_with_custom_cleanup(data_fixture)

    with freeze_time(now):
        assert Action.objects.count() == 3
        ActionHandler.clean_up_old_undoable_actions()
        assert Action.objects.count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.undo_redo
def test_custom_cleanup_failing_doesnt_rollback_other_successful_cleanups(
    data_fixture, settings, mutable_action_registry, django_assert_num_queries
):
    now = datetime.now(tz=timezone.utc)
    num_minutes_where_actions_will_be_old_enough_for_cleaning = timedelta(
        minutes=int(settings.MINUTES_UNTIL_ACTION_CLEANED_UP) * 2
    )
    with transaction.atomic():
        with freeze_time(
            now - num_minutes_where_actions_will_be_old_enough_for_cleaning
        ):
            _create_two_no_custom_cleanup_actions(data_fixture)
            _create_an_action_with_custom_cleanup(data_fixture)
        # Make the cleanup action happen later so it is cleaned up last.
        with freeze_time(
            now - num_minutes_where_actions_will_be_old_enough_for_cleaning / 2
        ):
            action_which_will_fail = _create_an_action_with_custom_cleanup_which_raises(
                mutable_action_registry,
                data_fixture,
                cleanup_exception_message="Custom cleanup failed",
            )

    with freeze_time(now):
        assert Action.objects.count() == 4
        with pytest.raises(Exception, match="Custom cleanup failed"):
            ActionHandler.clean_up_old_undoable_actions()
        # The other 3 actions were deleted successfully, and only the last one which
        # failed is left.
        assert Action.objects.count() == 1
        assert Action.objects.first().id == action_which_will_fail.id


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undoing_multiple_actions_in_a_single_undo_operation(data_fixture):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test2"
    )

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(
        undone_actions, [CreateWorkspaceActionType, CreateWorkspaceActionType]
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_undoing_multiple_actions_is_limited_in_a_single_undo_operation(data_fixture):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test2"
    )

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(undone_actions, [CreateWorkspaceActionType])

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(undone_actions, [CreateWorkspaceActionType])


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_redoing_multiple_actions_in_a_single_redo_operation(data_fixture):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test2"
    )

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    redone_actions = ActionHandler.redo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(
        redone_actions, [CreateWorkspaceActionType, CreateWorkspaceActionType]
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
@override_settings(MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP=1)
def test_redoing_multiple_actions_is_limited_in_a_single_undo_operation(data_fixture):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test"
    )

    action_type_registry.get_by_type(CreateWorkspaceActionType).do(
        user, workspace_name="test2"
    )

    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)
    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    redone_actions = ActionHandler.redo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(redone_actions, [CreateWorkspaceActionType])

    redone_actions = ActionHandler.redo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_are_valid(redone_actions, [CreateWorkspaceActionType])


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_undo_redo_action_group_with_interleaved_actions(data_fixture):
    session_id = "session-id"
    action_group_1, action_group_2 = uuid.uuid4(), uuid.uuid4()
    user_1 = data_fixture.create_user(
        session_id=session_id, action_group=action_group_1
    )
    user_2 = data_fixture.create_user(
        session_id=session_id, action_group=action_group_2
    )
    workspace = data_fixture.create_workspace(users=[user_1, user_2])

    def _interleave_actions():
        user_1_app = action_type_registry.get_by_type(CreateApplicationActionType).do(
            user_1, workspace, application_type="database", name="u1_a1"
        )
        user_2_app = action_type_registry.get_by_type(CreateApplicationActionType).do(
            user_2, workspace, application_type="database", name="u2_a1"
        )
        action_type_registry.get_by_type(UpdateApplicationActionType).do(
            user_1, user_1_app, name="u1_a2"
        )
        action_type_registry.get_by_type(UpdateApplicationActionType).do(
            user_2, user_2_app, name="u2_a2"
        )

    _interleave_actions()

    assert Application.objects.count() == 2

    # user1 undo, user2 undo, user1 redo, user2 redo
    undone_actions = ActionHandler.undo(
        user_1, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        undone_actions, [UpdateApplicationActionType, CreateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == ["u2_a2"]
    undone_actions = ActionHandler.undo(
        user_2, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        undone_actions, [UpdateApplicationActionType, CreateApplicationActionType]
    )
    assert Application.objects.count() == 0
    redone_actions = ActionHandler.redo(
        user_1, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        redone_actions, [CreateApplicationActionType, UpdateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == ["u1_a2"]
    redone_actions = ActionHandler.redo(
        user_2, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        redone_actions, [CreateApplicationActionType, UpdateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == unordered(
        ["u1_a2", "u2_a2"]
    )

    # user1 undo, user2 undo, user2 redo, user1 redo
    undone_actions = ActionHandler.undo(
        user_1, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        undone_actions, [UpdateApplicationActionType, CreateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == ["u2_a2"]
    undone_actions = ActionHandler.undo(
        user_2, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        undone_actions, [UpdateApplicationActionType, CreateApplicationActionType]
    )
    assert Application.objects.count() == 0
    redone_actions = ActionHandler.redo(
        user_2, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        redone_actions, [CreateApplicationActionType, UpdateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == ["u2_a2"]
    redone_actions = ActionHandler.redo(
        user_1, [WorkspaceActionScopeType.value(workspace_id=workspace.id)], session_id
    )
    assert_undo_redo_actions_are_valid(
        redone_actions, [CreateApplicationActionType, UpdateApplicationActionType]
    )
    assert list(Application.objects.values_list("name", flat=True)) == unordered(
        ["u1_a2", "u2_a2"]
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
@patch("baserow.core.signals.workspace_deleted.send")
def test_when_undo_fails_the_action_group_is_rolled_back(
    mock_workspace_deleted,
    data_fixture,
):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)

    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test2")
        .workspace
    )

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace=workspace, application_type="database", name="u1_a1"
    )

    mock_workspace_deleted.side_effect = Exception(
        "Error that should make the undo rollback"
    )

    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        undone_actions, [CreateWorkspaceActionType, CreateApplicationActionType]
    )

    assert Workspace.objects.filter(id=workspace.id).exists(), (
        "The workspace should still exist as the undo transaction should have failed and "
        "rolled back. "
    )

    assert Application.objects.filter(id=application.id).exists(), (
        "The application should still exist as the undo transaction should have failed and "
        "rolled back. "
    )


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_when_undo_fails_in_action_group_can_try_redo_undo_to_try_again(
    data_fixture,
):
    session_id, action_group = "session-id", uuid.uuid4()
    user = data_fixture.create_user(session_id=session_id, action_group=action_group)
    other_user = data_fixture.create_user(session_id=session_id)

    # User A creates a workspace
    workspace = (
        action_type_registry.get_by_type(CreateWorkspaceActionType)
        .do(user, workspace_name="test")
        .workspace
    )

    application = action_type_registry.get_by_type(CreateApplicationActionType).do(
        user, workspace=workspace, application_type="database", name="u1_a1"
    )

    # User B deletes the workspace
    locked_workspace = CoreHandler().get_workspace_for_update(workspace_id=workspace.id)
    data_fixture.create_user_workspace(
        workspace=locked_workspace,
        user=other_user,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    action_type_registry.get_by_type(DeleteWorkspaceActionType).do(
        other_user, workspace=locked_workspace
    )

    # User A tries to Undo the creation of the workspace, it fails as it has already
    # been deleted.
    undone_actions = ActionHandler.undo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        undone_actions, [DeleteWorkspaceActionType, CreateApplicationActionType]
    )

    # User B Undoes the deletion, recreating the workspace
    ActionHandler.undo(other_user, [DeleteWorkspaceActionType.scope()], session_id)

    # User A Redoes which does nothing
    redone_actions = ActionHandler.redo(
        user, [CreateWorkspaceActionType.scope()], session_id
    )
    assert_undo_redo_actions_fails_with_error(
        redone_actions, [DeleteWorkspaceActionType, CreateApplicationActionType]
    )

    # User A can now Undo the creation of the workspace as it exists again
    ActionHandler.undo(user, [CreateWorkspaceActionType.scope()], session_id)

    assert not Workspace.objects.exists()


def _create_an_action_with_custom_cleanup(data_fixture):
    user = data_fixture.create_user()
    text_field = data_fixture.create_text_field(user=user)
    action_type_registry.get_by_type(UpdateFieldActionType).do(
        user, text_field, "boolean"
    )


def _create_an_action_with_custom_cleanup_which_raises(
    mutable_action_registry, data_fixture, cleanup_exception_message
) -> Action:
    class ActionWithCustomCleanupThatAlwaysRaises(
        UndoableActionCustomCleanupMixin, UndoableActionType
    ):
        type = "action_with_custom_cleanup_that_always_raises"

        @classmethod
        def clean_up_any_extra_action_data(cls, action_being_cleaned_up: Action):
            raise Exception(cleanup_exception_message)

        @classmethod
        def do(cls, user) -> Action:
            return cls.register_action(user, cls.Params(), cls.scope())

        @classmethod
        def scope(cls, *args, **kwargs) -> ActionScopeStr:
            return RootActionScopeType.value()

        @classmethod
        def undo(cls, user: AbstractUser, params: Any, action_being_undone: Action):
            pass

        @classmethod
        def redo(cls, user: AbstractUser, params: Any, action_being_redone: Action):
            pass

    mutable_action_registry.register(ActionWithCustomCleanupThatAlwaysRaises())

    return mutable_action_registry.get_by_type(
        ActionWithCustomCleanupThatAlwaysRaises
    ).do(data_fixture.create_user())

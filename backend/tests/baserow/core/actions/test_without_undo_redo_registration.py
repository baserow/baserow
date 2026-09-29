from unittest.mock import patch

import pytest

from baserow.api.sessions import (
    get_client_undo_redo_action_group_id,
    get_untrusted_client_session_id,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)
from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.core.action.context import without_undo_redo_registration
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action


@pytest.mark.django_db
def test_actions_inside_the_block_are_registered_without_a_session(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")
    set_untrusted_client_session_id(user, "session-1")

    with without_undo_redo_registration(user):
        CreateRowsActionType.do(user=user, table=table, rows_values=[{}])

    action = Action.objects.get(type=CreateRowsActionType.type)
    assert action.session is None


@pytest.mark.django_db
def test_the_session_id_is_restored_afterwards(data_fixture):
    user = data_fixture.create_user()
    set_untrusted_client_session_id(user, "session-1")
    set_client_undo_redo_action_group_id(user, "group-1")

    with without_undo_redo_registration(user):
        assert get_untrusted_client_session_id(user) is None
        assert get_client_undo_redo_action_group_id(user) is None

    assert get_untrusted_client_session_id(user) == "session-1"
    assert get_client_undo_redo_action_group_id(user) == "group-1"


@pytest.mark.django_db
def test_the_session_id_is_restored_after_an_exception(data_fixture):
    user = data_fixture.create_user()
    set_untrusted_client_session_id(user, "session-1")

    with pytest.raises(ValueError):
        with without_undo_redo_registration(user):
            raise ValueError("boom")

    assert get_untrusted_client_session_id(user) == "session-1"


@pytest.mark.django_db
def test_the_action_done_signal_still_fires(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")
    set_untrusted_client_session_id(user, "session-1")

    with patch("baserow.core.action.signals.action_done.send") as mocked_send:
        with without_undo_redo_registration(user):
            CreateRowsActionType.do(user=user, table=table, rows_values=[{}])

    assert mocked_send.call_count == 1
    assert mocked_send.call_args.kwargs["session"] is None


@pytest.mark.django_db
def test_the_action_cannot_be_undone(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Name")
    set_untrusted_client_session_id(user, "session-1")

    with without_undo_redo_registration(user):
        CreateRowsActionType.do(user=user, table=table, rows_values=[{}])

    undone = ActionHandler.undo(
        user, [TableActionScopeType.value(table_id=table.id)], "session-1"
    )
    assert undone == []

from unittest.mock import patch

import pytest

from baserow.contrib.database.action.scopes import ViewActionScopeType
from baserow.contrib.database.views.actions import (
    SubmitFormActionType,
    UpdateViewActionType,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.test_utils.helpers import assert_undo_redo_actions_are_valid


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_can_undo_update_view_receive_notification_on_submit(data_fixture):
    session_id = "session-id"
    user = data_fixture.create_user(session_id=session_id)
    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)

    def list_users_to_notify_on_submit():
        return [u.id for u in form_view.users_to_notify_on_submit.all()]

    assert list_users_to_notify_on_submit() == []

    action_type_registry.get_by_type(UpdateViewActionType).do(
        user, form_view, receive_notification_on_submit=True
    )

    assert list_users_to_notify_on_submit() == [user.id]

    undone_actions = ActionHandler.undo(
        user, [ViewActionScopeType.value(form_view.id)], session_id
    )
    assert_undo_redo_actions_are_valid(undone_actions, [UpdateViewActionType])

    assert list_users_to_notify_on_submit() == []

    redone_actions = ActionHandler.redo(
        user, [ViewActionScopeType.value(form_view.id)], session_id
    )
    assert_undo_redo_actions_are_valid(redone_actions, [UpdateViewActionType])

    assert list_users_to_notify_on_submit() == [user.id]


@pytest.mark.django_db
def test_submit_form_emit_action_done_signal(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    form = data_fixture.create_form_view(table=table)
    text_field = data_fixture.create_text_field(table=table)
    data_fixture.create_form_view_field_option(
        form, text_field, required=True, enabled=True, order=1
    )

    with patch("baserow.core.action.signals.action_done.send") as send_mock:
        row = SubmitFormActionType.do(user, form, {text_field.db_column: "test"})

        assert row.id is not None
        assert send_mock.call_count == 1
        assert send_mock.call_args[1]["action_type"].type == SubmitFormActionType.type
        assert send_mock.call_args[1]["user"].id == user.id
        assert send_mock.call_args[1]["action_params"] == {
            "view_id": form.id,
            "view_name": form.name,
            "row_id": row.id,
            "table_id": table.id,
            "table_name": table.name,
            "database_id": table.database.id,
            "database_name": table.database.name,
            "values": {text_field.db_column: "test"},
            "fields_metadata": {
                text_field.db_column: {"id": text_field.id, "type": "text"},
                "id": row.id,
            },
        }

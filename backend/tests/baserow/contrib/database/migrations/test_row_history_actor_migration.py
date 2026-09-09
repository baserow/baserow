from datetime import datetime, timezone

import pytest


@pytest.mark.once_per_day_in_ci
def test_row_history_actor_types_are_backfilled(migrator):
    """Existing row history keeps users and identifies anonymous actors."""

    old_state = migrator.migrate([("database", "0223_gridview_group_by_layout")])

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Database = old_state.apps.get_model("database", "Database")
    Table = old_state.apps.get_model("database", "Table")
    RowHistory = old_state.apps.get_model("database", "RowHistory")

    workspace = Workspace.objects.create(name="workspace")
    database = Database.objects.create(
        content_type=ContentType.objects.get_for_model(Database),
        order=1,
        name="database",
        workspace_id=workspace.id,
        trashed=False,
    )
    table = Table.objects.create(
        database_id=database.id, name="table", order=1, trashed=False
    )
    common_values = {
        "table_id": table.id,
        "row_id": 1,
        "field_names": [],
        "fields_metadata": {},
        "action_uuid": "00000000-0000-0000-0000-000000000001",
        "action_command_type": "DO",
        "action_timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "action_type": "update_row",
        "before_values": {},
        "after_values": {},
    }
    user_entry = RowHistory.objects.create(
        user_id=1, user_name="User", **common_values
    )
    anonymous_entry = RowHistory.objects.create(
        user_id=None, user_name="Anonymous User", **common_values
    )

    new_state = migrator.migrate([("database", "0224_rowhistory_actor")])
    RowHistory = new_state.apps.get_model("database", "RowHistory")

    assert RowHistory.objects.get(id=user_entry.id).actor_type == "auth.User"
    assert RowHistory.objects.get(id=anonymous_entry.id).actor_type == "anonymous"

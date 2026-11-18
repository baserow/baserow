from django.db import connection

import pytest

HISTORY_IDENTITY_MIGRATIONS = [
    (
        "database",
        "0228_delete_password_view_default_values",
        "0229_rowhistory_actor_user_type",
        "database_rowhistory",
        "actor_user_type",
    ),
    (
        "automation",
        "0044_workflow_description_and_node_note",
        "0045_automationworkflowhistory_triggered_by_user_type",
        "automation_automationworkflowhistory",
        "triggered_by_user_type",
    ),
    (
        "baserow_enterprise",
        "0074_delete_legacy_agent_subjects",
        "0075_auditlogentry_actor_user_type",
        "baserow_enterprise_auditlogentry",
        "actor_user_type",
    ),
]


def _get_column(table_name, column_name):
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table_name)
    return next((column for column in columns if column.name == column_name), None)


@pytest.mark.once_per_day_in_ci
@pytest.mark.parametrize(
    "app,previous,current,table_name,column_name", HISTORY_IDENTITY_MIGRATIONS
)
def test_history_identity_columns_are_added_nullable_without_a_default(
    migrator, app, previous, current, table_name, column_name
):
    migrator.migrate([(app, previous)])
    assert _get_column(table_name, column_name) is None

    migrator.migrate([(app, current)])
    column = _get_column(table_name, column_name)
    assert column.null_ok
    assert column.default is None

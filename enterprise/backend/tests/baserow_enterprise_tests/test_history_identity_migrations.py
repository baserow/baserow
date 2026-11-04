from django.db import connection

import pytest

HISTORY_IDENTITY_MIGRATIONS = [
    (
        "database",
        "0228_delete_password_view_default_values",
        "0229_rowhistory_identity_type",
        "database_rowhistory",
        "actor_identity_type",
    ),
    (
        "automation",
        "0041_automationworkflow_untrusted_content",
        "0042_workflowhistory_identity_type",
        "automation_automationworkflowhistory",
        "triggered_by_identity_type",
    ),
    (
        "baserow_enterprise",
        "0070_semantic_search",
        "0071_auditlog_identity_type",
        "baserow_enterprise_auditlogentry",
        "actor_identity_type",
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
def test_history_identity_columns_are_added_without_changing_entries(
    migrator, app, previous, current, table_name, column_name
):
    """Agent users test plan 14.2.1."""

    migrator.migrate([(app, previous)])
    assert _get_column(table_name, column_name) is None

    migrator.migrate([(app, current)])
    column = _get_column(table_name, column_name)
    assert column.null_ok
    assert column.default is None

import pytest
from django.db import connection


@pytest.mark.once_per_day_in_ci
def test_audit_log_actor_migration_retries_after_column_addition(migrator):
    """An interrupted non-atomic migration can recreate its actor index on retry."""

    migrator.migrate([("baserow_enterprise", "0067_graph_element")])

    with connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE "baserow_enterprise_auditlogentry" '
            'ADD COLUMN "actor_type" varchar(255) NOT NULL DEFAULT \'auth.User\''
        )
        cursor.execute(
            'ALTER TABLE "baserow_enterprise_auditlogexportjob" '
            'ADD COLUMN "filter_actor_type" varchar(255) DEFAULT \'auth.User\''
        )

    state = migrator.migrate([("baserow_enterprise", "0068_auditlogentry_agent")])
    AuditLogEntry = state.apps.get_model("baserow_enterprise", "AuditLogEntry")
    AuditLogExportJob = state.apps.get_model("baserow_enterprise", "AuditLogExportJob")

    assert AuditLogEntry._meta.get_field("actor_type").db_default is not None
    assert AuditLogExportJob._meta.get_field("filter_actor_type").db_default is not None

from rest_framework import serializers

from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.api.tables.serializers import TableSerializer
from baserow.contrib.database.db.atomic import (
    read_repeatable_read_single_table_transaction,
)
from baserow.contrib.database.table.actions import DuplicateTableActionType
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import DuplicateTableJob
from baserow.contrib.database.table.operations import (
    DuplicateDatabaseTableOperationType,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.jobs.registries import JobType


class DuplicateTableJobType(JobType):
    type = "duplicate_table"
    model_class = DuplicateTableJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    }

    request_serializer_field_names = ["table_id"]

    request_serializer_field_overrides = {
        "table_id": serializers.IntegerField(
            help_text="The ID of the table to duplicate.",
        ),
    }

    serializer_field_names = ["original_table", "duplicated_table"]
    serializer_field_overrides = {
        "original_table": TableSerializer(read_only=True),
        "duplicated_table": TableSerializer(read_only=True),
    }

    def transaction_atomic_context(self, job: "DuplicateTableJob"):
        return read_repeatable_read_single_table_transaction(job.original_table.id)

    def prepare_values(self, values, user):
        table = TableHandler().get_table(values.pop("table_id"))

        CoreHandler().check_permissions(
            user,
            DuplicateDatabaseTableOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        return {
            "original_table": table,
        }

    def run(self, job, progress):
        new_table_clone = action_type_registry.get_by_type(DuplicateTableActionType).do(
            job.actor,
            job.original_table,
            progress_builder=progress.create_child_builder(
                represents_progress=progress.total
            ),
        )

        # update the job with the new duplicated table
        job.duplicated_table = new_table_clone
        job.save(update_fields=("duplicated_table",))

        return new_table_clone

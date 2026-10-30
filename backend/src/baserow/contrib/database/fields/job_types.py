from rest_framework import serializers

from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.api.fields.serializers import (
    FieldSerializer,
    FieldSerializerWithRelatedFields,
)
from baserow.contrib.database.db.atomic import (
    read_repeatable_read_single_table_transaction,
)
from baserow.contrib.database.fields.actions import DuplicateFieldActionType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import DuplicateFieldJob
from baserow.contrib.database.fields.operations import DuplicateFieldOperationType
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.jobs.registries import JobType


class DuplicateFieldJobType(JobType):
    type = "duplicate_field"
    model_class = DuplicateFieldJob
    max_count = 1

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
    }

    request_serializer_field_names = ["field_id"]

    request_serializer_field_overrides = {
        "field_id": serializers.IntegerField(
            help_text="The ID of the field to duplicate.",
        ),
        "duplicate_data": serializers.BooleanField(
            help_text="Whether to duplicate the data of the field.",
            default=False,
        ),
    }

    serializer_field_names = ["original_field", "duplicated_field"]
    serializer_field_overrides = {
        "original_field": FieldSerializer(read_only=True),
        "duplicated_field": FieldSerializerWithRelatedFields(read_only=True),
    }

    def transaction_atomic_context(self, job: "DuplicateFieldJob"):
        return read_repeatable_read_single_table_transaction(
            job.original_field.table.id
        )

    def prepare_values(self, values, user):
        field = FieldHandler().get_field(values["field_id"])
        CoreHandler().check_permissions(
            user,
            DuplicateFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        return {
            "original_field": field,
            "duplicate_data": values.get("duplicate_data", False),
        }

    def run(self, job, progress):
        duplicate_field_action_type = action_type_registry.get_by_type(
            DuplicateFieldActionType
        )
        new_field_clone, updated_fields = duplicate_field_action_type.do(
            job.actor,
            job.original_field,
            job.duplicate_data,
            progress.create_child_builder(represents_progress=progress.total),
        )

        # update the job with the new duplicated field instance
        job.duplicated_field = new_field_clone
        job.save(update_fields=("duplicated_field",))

        return new_field_clone, updated_fields

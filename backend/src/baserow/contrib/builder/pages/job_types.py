from typing import Any, Dict

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from rest_framework import serializers

from baserow.contrib.builder.api.pages.serializers import PageSerializer
from baserow.contrib.builder.pages.actions import DuplicatePageActionType
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import DuplicatePageJob
from baserow.contrib.builder.pages.operations import DuplicatePageOperationType
from baserow.core.action.registries import action_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.jobs.registries import JobType


class DuplicatePageJobType(JobType):
    type = "duplicate_page"
    model_class = DuplicatePageJob
    max_count = 1

    request_serializer_field_names = ["page_id"]

    request_serializer_field_overrides = {
        "page_id": serializers.IntegerField(
            help_text="The ID of the page to duplicate.",
        ),
    }

    serializer_field_names = ["original_page", "duplicated_page"]
    serializer_field_overrides = {
        "original_page": PageSerializer(read_only=True),
        "duplicated_page": PageSerializer(read_only=True),
    }

    def transaction_atomic_context(self, job: "DuplicatePageJobType"):
        return transaction.atomic()

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        page = PageHandler().get_page(values.pop("page_id"))

        CoreHandler().check_permissions(
            user,
            DuplicatePageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        return {"original_page": page}

    def run(self, job, progress):
        new_page_clone = action_type_registry.get_by_type(DuplicatePageActionType).do(
            job.user,
            job.original_page,
            progress_builder=progress.create_child_builder(
                represents_progress=progress.total
            ),
        )

        job.duplicated_page = new_page_clone
        job.save(update_fields=("duplicated_page",))

        return new_page_clone

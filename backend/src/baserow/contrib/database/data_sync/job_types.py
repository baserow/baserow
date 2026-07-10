from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from loguru import logger
from rest_framework import serializers

from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.api.data_sync.errors import (
    ERROR_DATA_SYNC_DOES_NOT_EXIST,
    ERROR_SYNC_DATA_SYNC_ALREADY_RUNNING,
    ERROR_SYNC_ERROR,
)
from baserow.contrib.database.api.data_sync.serializers import DataSyncSerializer
from baserow.contrib.database.data_sync.exceptions import (
    DataSyncDoesNotExist,
    SyncDataSyncTableAlreadyRunning,
    SyncError,
)
from baserow.contrib.database.db.atomic import (
    read_repeatable_read_single_table_transaction,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.signals import table_updated
from baserow.core.action.registries import action_type_registry
from baserow.core.db import transaction_atomic
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.models import JobQuerySet
from baserow.core.jobs.registries import JobType

from .actions import SyncDataSyncTableActionType
from .handler import DataSyncHandler
from .models import (
    DATA_SYNC_JOB_TRIGGERED_BY_MANUAL,
    DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC,
    DataSync,
    SyncDataSyncTableJob,
)
from .operations import ListDataSyncJobsOperationType, SyncTableOperationType
from .registries import data_sync_type_registry

MAX_FOREIGN_DATA_SYNCS_TO_SCOPE = 50


def validation_error_to_human_readable_string(e):
    return "\n".join(e.messages)


class SyncDataSyncTableJobType(JobType):
    type = "sync_data_sync_table"
    model_class = SyncDataSyncTableJob
    max_count = 3

    api_exceptions_map = {
        DataSyncDoesNotExist: ERROR_DATA_SYNC_DOES_NOT_EXIST,
        SyncDataSyncTableAlreadyRunning: ERROR_SYNC_DATA_SYNC_ALREADY_RUNNING,
    }
    job_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        SyncDataSyncTableAlreadyRunning: ERROR_SYNC_DATA_SYNC_ALREADY_RUNNING[2],
        SyncError: ERROR_SYNC_ERROR[2],
        ValidationError: validation_error_to_human_readable_string,
    }
    request_serializer_field_names = ["data_sync_id"]
    request_serializer_field_overrides = {
        "data_sync_id": serializers.IntegerField(
            help_text="The ID of data sync to sync.",
        ),
    }
    serializer_field_names = ["data_sync", "triggered_by", "user_name"]
    serializer_field_overrides = {
        "data_sync": DataSyncSerializer(read_only=True),
        "triggered_by": serializers.CharField(
            read_only=True,
            help_text="Whether this sync run was started manually or periodically.",
        ),
        "user_name": serializers.CharField(
            source="user.first_name",
            read_only=True,
            help_text="The name of the user that started this sync run.",
        ),
    }

    def get_filters_serializer(self):
        from baserow.contrib.database.api.data_sync.serializers import (
            SyncDataSyncTableJobFiltersSerializer,
        )

        return SyncDataSyncTableJobFiltersSerializer

    def enhance_queryset(self, queryset: JobQuerySet) -> JobQuerySet:
        return queryset.select_related("user", "data_sync__table").prefetch_related(
            "data_sync__synced_properties"
        )

    def scope_queryset_to_user(
        self, user: AbstractUser, queryset: JobQuerySet
    ) -> JobQuerySet:
        """
        On top of their own jobs, users can see the sync runs started by other
        users (including periodic ones) for every data sync they have the
        ``ListDataSyncJobsOperationType`` permission on. Falls back to
        owner-only scoping when the queryset spans too many data syncs, so an
        unfiltered listing can't trigger unbounded permission checks.
        """

        foreign_data_syncs = list(
            DataSync.objects.filter(
                id__in=queryset.exclude(user=user)
                .exclude(data_sync_id=None)
                .values("data_sync_id")
            ).select_related("table__database__workspace")[
                : MAX_FOREIGN_DATA_SYNCS_TO_SCOPE + 1
            ]
        )
        if len(foreign_data_syncs) > MAX_FOREIGN_DATA_SYNCS_TO_SCOPE:
            return queryset.filter(user=user)

        data_syncs_by_workspace = defaultdict(list)
        for data_sync in foreign_data_syncs:
            data_syncs_by_workspace[data_sync.table.database.workspace].append(
                data_sync
            )

        allowed_data_sync_ids = []
        for workspace, data_syncs in data_syncs_by_workspace.items():
            allowed_table_ids = set(
                CoreHandler()
                .filter_queryset(
                    user,
                    ListDataSyncJobsOperationType.type,
                    Table.objects.filter(
                        id__in=[data_sync.table_id for data_sync in data_syncs]
                    ),
                    workspace=workspace,
                )
                .values_list("id", flat=True)
            )
            allowed_data_sync_ids += [
                data_sync.id
                for data_sync in data_syncs
                if data_sync.table_id in allowed_table_ids
            ]

        return queryset.filter(Q(user=user) | Q(data_sync_id__in=allowed_data_sync_ids))

    def _get_running_jobs(self, job: SyncDataSyncTableJob) -> JobQuerySet:
        # Server-driven periodic runs must not consume the user's manual cap.
        return (
            super()
            ._get_running_jobs(job)
            .exclude(triggered_by=DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC)
        )

    def _can_schedule_or_raise(
        self, running_jobs: JobQuerySet, new_job: SyncDataSyncTableJob
    ) -> None:
        """
        Limits concurrent manual data syncs to ``max_count`` per user overall,
        and at most one pending or running job per individual data sync, no
        matter who or what triggered it. Periodic runs are exempt from the
        per-user cap because their schedule is server-driven. Jobs that haven't
        been updated within the soft time limit are considered stale leftovers
        of crashed workers and don't block new syncs.

        :raises MaxJobCountExceeded: If a conflicting job is already running.
        """

        if new_job.triggered_by != DATA_SYNC_JOB_TRIGGERED_BY_PERIODIC:
            super()._can_schedule_or_raise(running_jobs, new_job)

        if new_job.data_sync_id is not None:
            stale_cutoff = timezone.now() - timedelta(
                seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT
            )
            already_running = (
                SyncDataSyncTableJob.objects.filter(
                    data_sync_id=new_job.data_sync_id,
                    updated_on__gte=stale_cutoff,
                )
                .is_pending_or_running()
                .exists()
            )
            if already_running:
                raise MaxJobCountExceeded(
                    f"A {self.type} job is already running for this data sync."
                )

    def on_error(self, job: SyncDataSyncTableJob, error: Exception) -> None:
        """
        Persists the sync error on the data sync and notifies clients. This must
        happen here because the failed sync's transaction, including the
        ``last_error`` write done inside it, has been rolled back.
        """

        if not isinstance(error, SyncError) or not job.data_sync:
            return

        data_sync = job.data_sync
        data_sync.last_error = str(error)
        data_sync.save(update_fields=("last_error",))

        if not data_sync.table.trashed:
            table_updated.send(
                self, table=data_sync.table, user=job.user, force_table_refresh=False
            )

    def on_cancelled(self, job: SyncDataSyncTableJob) -> None:
        # Delete table if this is the initial sync job (last_sync is None), to avoid
        # leaving an empty, unsynced table that the user never explicitly created.
        if job.data_sync and job.data_sync.last_sync is None:
            try:
                TableHandler().delete_table(job.user, job.data_sync.table)
            except Exception:
                logger.exception(
                    f"Failed to delete table for cancelled data sync job {job.id}."
                )

    def transaction_atomic_context(self, job: "SyncDataSyncTableJob"):
        # If the job doesn't exist, the job won't be executed, so we can start a normal
        # transaction.
        if not job.data_sync:
            return transaction_atomic()
        return read_repeatable_read_single_table_transaction(job.data_sync.table_id)

    def prepare_values(self, values, user):
        data_sync = DataSyncHandler().get_data_sync(values["data_sync_id"])
        data_sync_type_registry.get_by_model(data_sync).prepare_sync_job_values(
            data_sync
        )
        CoreHandler().check_permissions(
            user,
            SyncTableOperationType.type,
            workspace=data_sync.table.database.workspace,
            context=data_sync.table,
        )
        return {
            "data_sync": data_sync,
            # Not in the request serializer, so API users can't set it.
            "triggered_by": values.get(
                "triggered_by", DATA_SYNC_JOB_TRIGGERED_BY_MANUAL
            ),
        }

    def run(self, job, progress):
        # Don't do anything if the data sync and/or table has been deleted because then
        # there is nothing to update anymore.
        if not job.data_sync:
            return

        data_sync = job.data_sync.specific

        # Don't do anything if the table has been trashed in the meantime because we
        # then can't update the values anyway.
        if data_sync.table.trashed:
            return

        data_sync = action_type_registry.get_by_type(SyncDataSyncTableActionType).do(
            job.user,
            data_sync,
            progress_builder=progress.create_child_builder(
                represents_progress=progress.total
            ),
        )

        if data_sync.last_error:
            raise SyncError(data_sync.last_error)

        progress.set_progress(100)

        return data_sync

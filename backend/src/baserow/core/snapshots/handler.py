from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import OperationalError, transaction
from django.db.models import Count, OuterRef, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from baserow.contrib.database.exceptions import (
    DatabaseSnapshotMaxLocksExceededException,
)
from baserow.core.deferred_callbacks import deferred_callback_context
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
    is_max_lock_exceeded_exception,
)
from baserow.core.handler import CoreHandler
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import Job
from baserow.core.models import Application, Snapshot, Workspace
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import (
    ImportExportConfig,
    application_type_registry,
    plugin_registry,
)
from baserow.core.signals import application_created
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    SnapshotDoesNotExist,
    SnapshotIsBeingCreated,
    SnapshotIsBeingDeleted,
    SnapshotIsBeingRestored,
    SnapshotKeepAboveMaximum,
    SnapshotKeepBelowProtected,
    SnapshotKeepChangeDeletesSnapshots,
    SnapshotKeepExceedsAllowance,
    SnapshotKeepFullOfProtected,
    SnapshotKeepIsZero,
    SnapshotNameNotUnique,
)
from baserow.core.snapshots.signals import (
    before_snapshot_created,
    snapshot_keep_updated,
)
from baserow.core.storage import get_default_storage
from baserow.core.utils import Progress

from .job_types import CreateSnapshotJobType, RestoreSnapshotJobType
from .operations import (
    CreateSnapshotApplicationOperationType,
    DeleteApplicationSnapshotOperationType,
    ListSnapshotsApplicationOperationType,
    ReadWorkspaceSnapshotSettingsOperationType,
    RestoreApplicationSnapshotOperationType,
    UpdateApplicationSnapshotKeepOperationType,
    UpdateWorkspaceSnapshotSettingsOperationType,
)
from .tasks import delete_application_snapshot


@dataclass
class UpdatedSnapshotKeep:
    """
    The result of changing a keep: the keep before and after, and how many
    snapshots were deleted because of it.
    """

    original_keep: Optional[int]
    new_keep: Optional[int]
    deleted_count: int


class SnapshotHandler:
    def _being_created(self) -> QuerySet:
        """
        Returns the snapshots that are still being created. A snapshot whose creation
        was interrupted, for example because its worker was stopped, is left out once
        it's older than the longest a creation can take.
        """

        started_after = datetime.now(tz=timezone.utc) - timedelta(
            seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 60
        )
        return Snapshot.objects.filter(
            snapshot_to_application__isnull=True,
            mark_for_deletion=False,
            created_at__gte=started_after,
        )

    def count(self, workspace: Workspace) -> int:
        """
        Counts the snapshots in the provided workspace, including the ones that are
        still being created. Manual and automatic snapshots are counted together.

        :param workspace: The workspace for which to count the snapshots.
        """

        restorable = Snapshot.objects.restorable().filter(
            snapshot_from_application__workspace=workspace
        )
        being_created = self._being_created().filter(
            snapshot_from_application__workspace=workspace
        )
        return (restorable | being_created).count()

    def _application_snapshots(self, application: Application) -> QuerySet:
        """
        Returns the snapshots the provided application holds: the restorable ones
        and the one being created, if any.
        """

        return Snapshot.objects.restorable().filter(
            snapshot_from_application=application
        ) | self._being_created().filter(snapshot_from_application=application)

    def _lock_workspace(self, workspace: Workspace) -> Workspace:
        """
        Locks the provided workspace until the end of the current transaction, so that
        only one snapshot or keep change at a time is checked and saved.

        :return: The locked workspace, with up to date values.
        """

        return (
            Workspace.objects.select_for_update(of=("self",), no_key=True)
            .filter(id=workspace.id)
            .first()
        )

    def get_allowance(self, workspace: Workspace) -> int:
        """
        Returns the snapshot allowance of the provided workspace: how many snapshots
        its applications can keep together. A negative value means there is no
        limit, and 0 means snapshots are disabled. A plugin can set it per
        workspace, for example from its plan, otherwise it's
        `BASEROW_MAX_SNAPSHOTS_PER_GROUP`.

        :param workspace: The workspace for which to get the allowance.
        """

        for plugin in plugin_registry.get_all():
            allowance = plugin.get_snapshot_allowance(workspace)
            if allowance is not None:
                return allowance
        return settings.BASEROW_MAX_SNAPSHOTS_PER_GROUP

    def get_max_keep(self) -> Optional[int]:
        """
        Returns the most snapshots one application can keep, or `None` when there is
        no maximum.
        """

        max_keep = settings.BASEROW_MAX_SNAPSHOTS_KEEP_PER_APPLICATION
        return max_keep if max_keep >= 0 else None

    def get_copied_keep(self, keep: Optional[int]) -> Optional[int]:
        """
        Returns the keep an application copied from another one gets, by a duplicate
        or a restore: the same keep, but never above the maximum keep, which can have
        been lowered since it was set.

        :param keep: The keep of the original application, `None` when it follows
            the workspace default.
        """

        max_keep = self.get_max_keep()
        if keep is None or max_keep is None:
            return keep
        return min(keep, max_keep)

    def get_effective_keep(self, application: Application) -> int:
        """
        Returns how many snapshots the provided application keeps: its own keep, or
        the workspace default keep when it doesn't have one.

        :param application: The application, with its workspace.
        """

        if application.snapshot_keep is not None:
            return application.snapshot_keep
        return application.workspace.snapshot_default_keep

    def _get_applications_with_keep(self, workspace: Workspace) -> QuerySet:
        """
        Returns the applications of the provided workspace that reserve part of its
        allowance: the ones that aren't trashed and support snapshots.
        """

        unsupported_content_types = [
            ContentType.objects.get_for_model(application_type.model_class)
            for application_type in application_type_registry.get_all()
            if not application_type.supports_snapshots
        ]
        return Application.objects.filter(workspace_id=workspace.id).exclude(
            content_type__in=unsupported_content_types
        )

    def get_allowance_used(
        self, workspace: Workspace, default_keep: Optional[int] = None
    ) -> int:
        """
        Returns how much of the allowance of the provided workspace its applications
        reserve: the sum of their effective keeps.

        :param workspace: The workspace.
        :param default_keep: The workspace default keep to count with, defaults to
            the current one.
        """

        if default_keep is None:
            default_keep = workspace.snapshot_default_keep
        used = self._get_applications_with_keep(workspace).aggregate(
            used=Sum(Coalesce("snapshot_keep", Value(default_keep)))
        )["used"]
        return used or 0

    def is_over_allowance(self, workspace: Workspace) -> bool:
        """
        Whether the applications of the provided workspace reserve more than its
        allowance. That happens when applications are added, or the allowance is
        lowered. Core never blocks snapshots because of it; SaaS does once its grace
        period is over.

        :param workspace: The workspace.
        """

        allowance = self.get_allowance(workspace)
        return allowance >= 0 and self.get_allowance_used(workspace) > allowance

    def can_exceed_allowance(self, workspace: Workspace) -> bool:
        """
        Whether raising a keep can take the provided workspace over its allowance.
        Core never allows it; a plugin can, for example SaaS, which gives the
        workspace a grace period before it refuses new snapshots.

        :param workspace: The workspace.
        """

        return any(
            plugin.allows_snapshot_keep_over_allowance(workspace)
            for plugin in plugin_registry.get_all()
        )

    def is_snapshot_creation_blocked(self, workspace: Workspace) -> bool:
        """
        Whether a plugin refuses new snapshots in the provided workspace, for example
        SaaS once the workspace has been over its allowance for its grace period.

        :param workspace: The workspace.
        """

        return any(
            plugin.is_snapshot_creation_blocked(workspace)
            for plugin in plugin_registry.get_all()
        )

    def _check_snapshots_allowed(self, application: Application) -> None:
        """
        Checks that a snapshot of the provided application can be created as far as
        the workspace is concerned.

        :raises MaximumSnapshotsReached: When snapshots are disabled, or a receiver
            of `before_snapshot_created` stops it.
        """

        if self.get_allowance(application.workspace) == 0:
            raise MaximumSnapshotsReached()
        before_snapshot_created.send(
            self, workspace=application.workspace, application=application
        )

    def check_room_for_snapshot(self, application: Application) -> None:
        """
        Checks that the provided application has room for one more snapshot. It has
        room when it holds fewer snapshots than its keep, or when one of them can be
        replaced: an unprotected one that isn't being restored.

        :param application: The application, with its workspace.
        :raises SnapshotKeepIsZero: When the application keeps no snapshots.
        :raises SnapshotKeepFullOfProtected: When the application is at its keep and
            none of its snapshots can be replaced.
        """

        keep = self.get_effective_keep(application)
        if keep == 0:
            raise SnapshotKeepIsZero()
        if self._application_snapshots(application).count() < keep:
            return
        # The same rule as the rotation that follows the new snapshot, so a snapshot
        # is only allowed when one will really be replaced.
        if self.get_snapshot_to_replace(application) is None:
            raise SnapshotKeepFullOfProtected()

    def get_snapshot_to_replace(self, application: Application) -> Optional[Snapshot]:
        """
        Returns the snapshot a new snapshot of the provided application replaces: its
        oldest unprotected one, when the application is at its keep.

        :param application: The application, with its workspace.
        :return: The snapshot, or `None` when nothing is replaced.
        """

        snapshots = self.get_snapshots_to_rotate(
            application, max(self.get_effective_keep(application) - 1, 0)
        )
        return snapshots.order_by("created_at", "id").first()

    def get_snapshots_to_rotate(
        self, application: Application, keep: Optional[int] = None
    ) -> QuerySet:
        """
        Returns the oldest unprotected snapshots of the provided application that go
        beyond its keep. Protected snapshots are never included, and still count
        towards the keep. Snapshots that are being restored are left out.

        :param application: The application, with its workspace.
        :param keep: How many snapshots to keep, defaults to the application's
            effective keep.
        :return: A queryset of the snapshots that should be deleted.
        """

        if keep is None:
            keep = self.get_effective_keep(application)
        return Snapshot.objects.filter(
            id__in=self._get_snapshot_ids_to_rotate([(application, keep)])
        )

    def _get_snapshot_ids_to_rotate(self, applications_and_keeps: List[tuple]) -> List:
        """
        Returns the ids of the snapshots to delete so that each of the provided
        applications holds no more than its keep: its oldest unprotected ones beyond
        it. A snapshot being restored is skipped for now rather than replaced by a
        newer one; a later rotation deletes it once it's restored. It runs the same
        few queries however many applications there are.

        :param applications_and_keeps: Tuples of an application and its keep.
        :return: The ids of the snapshots to delete.
        """

        keeps = {application.id: keep for application, keep in applications_and_keeps}
        if not keeps:
            return []
        counts = self._count_restorable(list(keeps))
        excess = {
            application_id: counts[application_id] - keep
            for application_id, keep in keeps.items()
            if counts.get(application_id, 0) > keep
        }
        if not excess:
            return []

        being_restored = set(
            JobHandler.get_pending_or_running_jobs(RestoreSnapshotJobType.type)
            .filter(snapshot__snapshot_from_application_id__in=list(excess))
            .values_list("snapshot_id", flat=True)
        )
        unprotected = (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application_id__in=list(excess), protected=False)
            .order_by("snapshot_from_application_id", "created_at", "id")
            .values_list("id", "snapshot_from_application_id")
        )
        ids = []
        taken = defaultdict(int)
        for snapshot_id, application_id in unprotected:
            if taken[application_id] >= excess[application_id]:
                continue
            taken[application_id] += 1
            if snapshot_id not in being_restored:
                ids.append(snapshot_id)
        return ids

    def _delete_rotated_snapshots(self, snapshot_ids: List) -> int:
        """
        Schedules the deletion of the provided snapshots, picked for rotation. The
        rows are locked first, and the ones that were protected, deleted or started
        being restored in the meantime are left alone.

        :param snapshot_ids: The ids picked by `_get_snapshot_ids_to_rotate`.
        :return: How many snapshots were deleted.
        """

        if not snapshot_ids:
            return 0
        snapshots = list(
            Snapshot.objects.filter(
                id__in=snapshot_ids, protected=False, mark_for_deletion=False
            )
            .select_for_update(of=("self",))
            .order_by("id")
        )
        being_restored = set(
            JobHandler.get_pending_or_running_jobs(RestoreSnapshotJobType.type)
            .filter(snapshot_id__in=[snapshot.id for snapshot in snapshots])
            .values_list("snapshot_id", flat=True)
        )
        to_delete = [
            snapshot
            for snapshot in snapshots
            if not snapshot.protected
            and not snapshot.mark_for_deletion
            and snapshot.id not in being_restored
        ]
        Snapshot.objects.filter(id__in=[snapshot.id for snapshot in to_delete]).update(
            mark_for_deletion=True
        )
        for snapshot in to_delete:
            if snapshot.snapshot_to_application_id is not None:
                delete_application_snapshot.delay(snapshot.snapshot_to_application_id)
        return len(to_delete)

    def rotate_snapshots(
        self, application: Application, keep: Optional[int] = None
    ) -> int:
        """
        Schedules the deletion of the oldest unprotected snapshots of the provided
        application that go beyond its keep. Protected snapshots and snapshots that
        are being restored are never deleted.

        :param application: The application, with its workspace.
        :param keep: How many snapshots to keep, defaults to the application's
            effective keep.
        :return: How many snapshots were deleted.
        """

        if keep is None:
            keep = self.get_effective_keep(application)
        return self._delete_rotated_snapshots(
            self._get_snapshot_ids_to_rotate([(application, keep)])
        )

    def _count_protected(self, applications: List[Application]) -> Dict[int, int]:
        """
        Returns how many protected snapshots each of the provided applications holds.
        """

        counts = (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application__in=applications, protected=True)
            .values("snapshot_from_application_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["snapshot_from_application_id"]: row["count"] for row in counts}

    def _count_restorable(self, applications: List[Application]) -> Dict[int, int]:
        """
        Returns how many restorable snapshots each of the provided applications
        holds.
        """

        counts = (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application__in=applications)
            .values("snapshot_from_application_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["snapshot_from_application_id"]: row["count"] for row in counts}

    def _validate_keep_change(
        self,
        workspace: Workspace,
        original_keep: int,
        new_keep: int,
        original_used: int,
        new_used: int,
        affected: List[tuple],
        delete_snapshots: bool,
    ) -> List:
        """
        Validates a keep change: the maximum keep, the allowance, the protected
        snapshots and the snapshots it deletes. It runs the same few queries however
        many applications are affected.

        :param workspace: The locked workspace.
        :param original_keep: The keep before the change.
        :param new_keep: The new keep.
        :param original_used: The allowance used before the change.
        :param new_used: The allowance used after the change.
        :param affected: Tuples of each application whose effective keep changes and
            its new effective keep.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            keep is confirmed.
        :return: The ids of the snapshots the change deletes.
        """

        # The maximum can be lowered after a keep was saved, so it's only checked
        # when the keep goes up.
        max_keep = self.get_max_keep()
        if max_keep is not None and new_keep > max_keep and new_keep > original_keep:
            raise SnapshotKeepAboveMaximum()

        allowance = self.get_allowance(workspace)
        if (
            allowance >= 0
            and new_used > original_used
            and new_used > allowance
            and not self.can_exceed_allowance(workspace)
        ):
            raise SnapshotKeepExceedsAllowance()

        protected = self._count_protected([application for application, _ in affected])
        if any(
            protected.get(application.id, 0) > keep for application, keep in affected
        ):
            raise SnapshotKeepBelowProtected()

        to_delete = self._get_snapshot_ids_to_rotate(affected)
        if to_delete and not delete_snapshots:
            raise SnapshotKeepChangeDeletesSnapshots(len(to_delete))
        return to_delete

    def get_application(
        self, application_id: int, performed_by: AbstractUser, operation_type: str
    ) -> Application:
        """
        Returns the specific application with the provided id, with its workspace,
        after checking that the user can perform the operation on it.

        :raises ApplicationDoesNotExist: When the application doesn't exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the workspace.
        """

        application = (
            CoreHandler()
            .get_application(
                application_id,
                base_queryset=Application.objects.select_related("workspace"),
            )
            .specific
        )
        CoreHandler().check_permissions(
            performed_by,
            operation_type,
            workspace=application.workspace,
            context=application,
        )
        return application

    def update_application_keep(
        self,
        application_id: int,
        performed_by: AbstractUser,
        keep: Optional[int],
        delete_snapshots: bool = False,
    ) -> Tuple[Application, UpdatedSnapshotKeep]:
        """
        Changes how many snapshots the provided application keeps. `None` makes it
        follow the workspace default keep again. Raising a keep is only allowed
        within the workspace's allowance, unless a plugin lets it go over; lowering
        one deletes the oldest unprotected snapshots beyond it.

        :param application_id: The id of the application.
        :param performed_by: The user changing the keep.
        :param keep: The new keep, or `None` to follow the workspace default.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            keep is confirmed.
        :raises SnapshotKeepAboveMaximum: When the keep is above the maximum.
        :raises SnapshotKeepExceedsAllowance: When raising the keep reserves more
            than the allowance, and the workspace can't go over it.
        :raises SnapshotKeepBelowProtected: When the keep is lower than the number
            of protected snapshots.
        :raises SnapshotKeepChangeDeletesSnapshots: When the change deletes
            snapshots and `delete_snapshots` isn't set.
        :return: The application and the change.
        """

        application = self.get_application(
            application_id,
            performed_by,
            UpdateApplicationSnapshotKeepOperationType.type,
        )
        workspace = self._lock_workspace(application.workspace)
        application.workspace = workspace
        # Another change can be saved while this one waits for the lock, so the keep
        # is read again once it's held.
        application.snapshot_keep = (
            Application.objects.filter(id=application.id)
            .values_list("snapshot_keep", flat=True)
            .get()
        )

        original_keep = application.snapshot_keep
        original_effective = self.get_effective_keep(application)
        new_effective = keep if keep is not None else workspace.snapshot_default_keep
        original_used = self.get_allowance_used(workspace)
        new_used = original_used - original_effective + new_effective

        to_delete = self._validate_keep_change(
            workspace,
            original_effective,
            new_effective,
            original_used,
            new_used,
            [(application, new_effective)],
            delete_snapshots,
        )

        Application.objects.filter(id=application.id).update(snapshot_keep=keep)
        application.snapshot_keep = keep
        deleted = self._delete_rotated_snapshots(to_delete)
        snapshot_keep_updated.send(self, workspace=workspace)
        return application, UpdatedSnapshotKeep(original_keep, keep, deleted)

    def get_keep_to_make_room(
        self, application_id: int, performed_by: AbstractUser
    ) -> Optional[int]:
        """
        Returns the keep the provided application needs so that one more snapshot
        fits without replacing one: its keep plus one, when it keeps no snapshots or
        every snapshot it keeps is protected. `None` when it already has room. The
        workspace stays locked until the end of the transaction, so the keep can be
        raised and the snapshot created before another change gets in between.

        :param application_id: The id of the application.
        :param performed_by: The user creating the snapshot.
        :raises ApplicationDoesNotExist: When the application doesn't exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the workspace.
        :return: The keep to raise it to, or `None`.
        """

        application = self.get_application(
            application_id,
            performed_by,
            CreateSnapshotApplicationOperationType.type,
        )
        application.workspace = self._lock_workspace(application.workspace)
        application.refresh_from_db(fields=["snapshot_keep"])
        try:
            self.check_room_for_snapshot(application)
        except (SnapshotKeepIsZero, SnapshotKeepFullOfProtected):
            return self.get_effective_keep(application) + 1
        return None

    def get_workspace(
        self, workspace_id: int, performed_by: AbstractUser, operation_type: str
    ) -> Workspace:
        """
        Returns the workspace with the provided id, after checking that the user can
        perform the operation on it.

        :raises WorkspaceDoesNotExist: When the workspace doesn't exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the workspace.
        """

        workspace = CoreHandler().get_workspace(workspace_id)
        CoreHandler().check_permissions(
            performed_by, operation_type, workspace=workspace, context=workspace
        )
        return workspace

    def update_workspace_default_keep(
        self,
        workspace_id: int,
        performed_by: AbstractUser,
        keep: int,
        delete_snapshots: bool = False,
    ) -> Tuple[Workspace, UpdatedSnapshotKeep]:
        """
        Changes the workspace default keep: how many snapshots its applications
        without a keep of their own keep. The same rules as for an application keep
        apply to every application that follows it.

        :param workspace_id: The id of the workspace.
        :param performed_by: The user changing the keep.
        :param keep: The new default keep.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            keep is confirmed.
        :raises SnapshotKeepAboveMaximum: When the keep is above the maximum.
        :raises SnapshotKeepExceedsAllowance: When raising the keep reserves more
            than the allowance, and the workspace can't go over it.
        :raises SnapshotKeepBelowProtected: When the keep is lower than the number
            of protected snapshots of an application that follows it.
        :raises SnapshotKeepChangeDeletesSnapshots: When the change deletes
            snapshots and `delete_snapshots` isn't set.
        :return: The workspace and the change.
        """

        workspace = self.get_workspace(
            workspace_id,
            performed_by,
            UpdateWorkspaceSnapshotSettingsOperationType.type,
        )
        workspace = self._lock_workspace(workspace)

        original_keep = workspace.snapshot_default_keep
        original_used = self.get_allowance_used(workspace)
        new_used = self.get_allowance_used(workspace, default_keep=keep)
        followers = list(
            self._get_applications_with_keep(workspace)
            .filter(snapshot_keep__isnull=True)
            .select_related("workspace")
        )

        to_delete = self._validate_keep_change(
            workspace,
            original_keep,
            keep,
            original_used,
            new_used,
            [(application, keep) for application in followers],
            delete_snapshots,
        )

        Workspace.objects.filter(id=workspace.id).update(snapshot_default_keep=keep)
        workspace.snapshot_default_keep = keep
        deleted = self._delete_rotated_snapshots(to_delete)
        snapshot_keep_updated.send(self, workspace=workspace)
        return workspace, UpdatedSnapshotKeep(original_keep, keep, deleted)

    def update_protected(
        self, snapshot_id: int, performed_by: AbstractUser, protected: bool
    ) -> Snapshot:
        """
        Protects or unprotects the provided snapshot. A protected snapshot is never
        deleted automatically. Anyone who can see the application's snapshots can
        change it.

        :param snapshot_id: The id of the snapshot.
        :param performed_by: The user changing it.
        :param protected: Whether the snapshot is protected.
        :raises SnapshotDoesNotExist: When the snapshot doesn't exist.
        :return: The updated snapshot.
        """

        try:
            snapshot = (
                Snapshot.objects.restorable()
                .filter(id=snapshot_id)
                .select_for_update(of=("self",))
                .select_related("snapshot_from_application__workspace", "created_by")
                .get()
            )
        except Snapshot.DoesNotExist:
            raise SnapshotDoesNotExist()

        application = snapshot.snapshot_from_application
        if application.workspace is None or application.workspace.trashed:
            raise SnapshotDoesNotExist()

        CoreHandler().check_permissions(
            performed_by,
            ListSnapshotsApplicationOperationType.type,
            workspace=application.workspace,
            context=application.specific,
        )

        snapshot.protected = protected
        snapshot.save(update_fields=["protected"])
        return snapshot

    def _check_is_in_use(self, snapshot: Snapshot) -> None:
        """
        Checks if the provided snapshot is in use and raises appropriate
        exception if it is.

        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to use
            a snapshot as the data are needed to restore it.
        """

        if self._is_being_restored(snapshot):
            raise SnapshotIsBeingRestored()

        if snapshot.mark_for_deletion is True:
            raise SnapshotIsBeingDeleted()

    def _is_being_restored(self, snapshot: Snapshot) -> bool:
        """
        Checks whether the provided snapshot has a pending or running restore job.
        """

        return (
            JobHandler.get_pending_or_running_jobs(RestoreSnapshotJobType.type)
            .filter(snapshot=snapshot)
            .exists()
        )

    def list(self, application_id: int, performed_by: AbstractUser) -> QuerySet:
        """
        Lists all snapshots for the given application id if the provided
        user is in the same workspace as the application.

        :param application_id: The ID of the application for which to list
            snapshots.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :return: A queryset for snapshots that were created for the given
            application.
        """

        try:
            application = (
                Application.objects.filter(id=application_id)
                .select_related("workspace")
                .get()
            )
        except Application.DoesNotExist:
            raise ApplicationDoesNotExist(
                f"The application with id {application_id} does not exist."
            )

        CoreHandler().check_permissions(
            performed_by,
            ListSnapshotsApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        return (
            Snapshot.objects.restorable()
            .filter(snapshot_from_application__id=application_id)
            .select_related("created_by")
            .order_by("-created_at", "-id")
        )

    def _get_allowance_values(self, workspace: Workspace) -> Dict[str, Any]:
        """
        Returns the allowance values of the provided workspace that the snapshot
        modal and the workspace settings show.
        """

        allowance = self.get_allowance(workspace)
        used = self.get_allowance_used(workspace)
        return {
            "used": used,
            "limit": allowance if allowance >= 0 else None,
            "over_allowance": allowance >= 0 and used > allowance,
            "blocked": self.is_snapshot_creation_blocked(workspace),
            "can_exceed_allowance": self.can_exceed_allowance(workspace),
            "snapshot_count": self.count(workspace),
            "default_keep": workspace.snapshot_default_keep,
            "max_keep": self.get_max_keep(),
            "expiration_days": settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS,
        }

    def get_usage(self, application_id: int, performed_by: AbstractUser) -> Dict:
        """
        Returns the snapshot allowance of the workspace of the given application and
        how much of it is reserved, together with the keep of the application.

        :param application_id: The ID of the application.
        :param performed_by: The user performing the operation that should have
            sufficient permissions.
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :return: A dict with the allowance values, `keep` (`None` when the
            application follows the workspace default), `effective_keep`,
            `snapshot_count_in_application` and `protected_count`.
        """

        application = self.get_application(
            application_id, performed_by, ListSnapshotsApplicationOperationType.type
        )
        restorable = Snapshot.objects.restorable().filter(
            snapshot_from_application=application
        )
        return {
            **self._get_allowance_values(application.workspace),
            "keep": application.snapshot_keep,
            "effective_keep": self.get_effective_keep(application),
            "application_snapshot_count": restorable.count(),
            "protected_count": restorable.filter(protected=True).count(),
        }

    def get_workspace_settings(
        self, workspace_id: int, performed_by: AbstractUser
    ) -> Dict:
        """
        Returns the snapshot allowance of the provided workspace, how much of it is
        reserved, and the keep and snapshots of every application the user can see.

        :param workspace_id: The id of the workspace.
        :param performed_by: The user requesting them.
        :raises WorkspaceDoesNotExist: When the workspace doesn't exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the workspace.
        :return: A dict with the allowance values and `applications`.
        """

        workspace = self.get_workspace(
            workspace_id, performed_by, ReadWorkspaceSnapshotSettingsOperationType.type
        )
        visible_applications = CoreHandler().filter_queryset(
            performed_by,
            ListApplicationsWorkspaceOperationType.type,
            self._get_applications_with_keep(workspace),
            workspace=workspace,
        )
        restorable = Snapshot.objects.restorable().filter(
            snapshot_from_application_id=OuterRef("id")
        )
        applications = visible_applications.annotate(
            snapshot_count=Coalesce(
                Subquery(
                    restorable.order_by()
                    .values("snapshot_from_application_id")
                    .annotate(count=Count("id"))
                    .values("count")
                ),
                Value(0),
            ),
            protected_count=Coalesce(
                Subquery(
                    restorable.filter(protected=True)
                    .order_by()
                    .values("snapshot_from_application_id")
                    .annotate(count=Count("id"))
                    .values("count")
                ),
                Value(0),
            ),
        ).order_by("order", "id")

        return {
            **self._get_allowance_values(workspace),
            "applications": [
                {
                    "id": application.id,
                    "keep": application.snapshot_keep,
                    "snapshot_count": application.snapshot_count,
                    "protected_count": application.protected_count,
                }
                for application in applications
            ],
        }

    def start_create_job(
        self, application_id: int, performed_by: AbstractUser, name: str
    ):
        """
        Create a snapshot instance to track the creation of a snapshot and start the job
        to perform the snapshot creation.

        :param application_id: The ID of the application for which to list snapshots.
        :param performed_by: The user performing the operation that should have
            sufficient permissions.
        :param name: The name for the new snapshot.
        :raises ApplicationDoesNotExist: When the application with the provided id does
            not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises MaximumSnapshotsReached: When snapshots are disabled or blocked for
            the workspace.
        :raises SnapshotKeepIsZero: When the application keeps no snapshots.
        :raises SnapshotKeepFullOfProtected: When the application is at its keep and
            none of its snapshots can be replaced.
        :raises ApplicationOperationNotSupported: When the application type doesn't
            support creating snapshots.
        :raises SnapshotIsBeingCreated: When creating a snapshot is already scheduled
            for the application.
        :raises MaxJobCountExceeded: When the user already has a running job to create a
            snapshot of the same type.
        :return: The snapshot object that was created and the started job.
        """

        snapshot = self.create(application_id, performed_by, name)

        job = JobHandler().create_and_start_job(
            performed_by,
            CreateSnapshotJobType.type,
            snapshot=snapshot,
        )

        return {
            "snapshot": snapshot,
            "job": job,
        }

    def create(self, application_id, performed_by, name):
        try:
            application = (
                Application.objects.filter(id=application_id)
                .select_related("workspace")
                .get()
            )
        except Application.DoesNotExist:
            raise ApplicationDoesNotExist(
                f"The application with id {application_id} does not exist."
            )

        CoreHandler().check_permissions(
            performed_by,
            CreateSnapshotApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        app_type = application_type_registry.get_by_model(application.specific_class)
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        application.workspace = self._lock_workspace(application.workspace)
        self._check_snapshots_allowed(application)

        if self.is_snapshot_being_created(application):
            raise SnapshotIsBeingCreated()

        self.check_room_for_snapshot(application)

        if (
            Snapshot.objects.restorable()
            .filter(
                snapshot_from_application=application,
                created_by=performed_by,
                name=name,
            )
            .exists()
        ):
            raise SnapshotNameNotUnique()

        snapshot = Snapshot.objects.create(
            snapshot_from_application=application,
            created_by=performed_by,
            name=name,
            protected=True,
        )

        return snapshot

    def is_snapshot_being_created(self, application: Application) -> bool:
        """
        Checks whether a manual or automatic snapshot of the provided application is
        currently being created.

        :param application: The application to check.
        """

        return (
            JobHandler()
            .get_pending_or_running_jobs(CreateSnapshotJobType.type)
            .filter(snapshot__snapshot_from_application=application)
            .exists()
            or self._being_created()
            .filter(snapshot_from_application=application)
            .exists()
        )

    def create_automatic(self, application: Application, name: str) -> Snapshot:
        """
        Creates a snapshot instance for an automatic snapshot. Automatic snapshots
        are created by the system on a schedule, so there is no user and no
        permission check. The permissions are checked when the schedule is saved.
        Automatic snapshots aren't protected, so they can be replaced.

        :param application: The application for which to create the snapshot.
        :param name: The name for the new snapshot.
        :raises ApplicationOperationNotSupported: When the application type doesn't
            support creating snapshots.
        :raises MaximumSnapshotsReached: When snapshots are disabled or blocked for
            the workspace.
        :raises SnapshotKeepIsZero: When the application keeps no snapshots.
        :raises SnapshotKeepFullOfProtected: When the application is at its keep and
            none of its snapshots can be replaced.
        :raises SnapshotIsBeingCreated: When another snapshot of the application is
            being created.
        :return: The snapshot object that was created.
        """

        app_type = application_type_registry.get_by_model(application.specific_class)
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        # An application that keeps no snapshots is skipped before anything else,
        # so it never waits for the workspace lock or reports the workspace's state.
        if self.get_effective_keep(application) == 0:
            raise SnapshotKeepIsZero()

        with transaction.atomic():
            application.workspace = self._lock_workspace(application.workspace)
            self._check_snapshots_allowed(application)

            if self.is_snapshot_being_created(application):
                raise SnapshotIsBeingCreated()

            self.check_room_for_snapshot(application)

            return Snapshot.objects.create(
                snapshot_from_application=application,
                created_by=None,
                created_automatically=True,
                protected=False,
                name=name,
            )

    def rotate_after_create(self, application_id: int) -> None:
        """
        Deletes the oldest unprotected snapshots of the provided application beyond
        its keep, once a new snapshot of it was created. It's called after the
        creation is committed, so a failed creation never leaves fewer snapshots.

        :param application_id: The id of the application.
        """

        with transaction.atomic():
            application = (
                Application.objects.filter(id=application_id)
                .select_related("workspace")
                .first()
            )
            if application is None:
                return
            application.workspace = self._lock_workspace(application.workspace)
            self.rotate_snapshots(application)

    def start_restore_job(
        self,
        snapshot_id: int,
        performed_by: AbstractUser,
    ) -> Job:
        """
        Restores a previously created snapshot with the given ID if the
        provided user is in the same workspace as the application.

        :param snapshot_id: The ID of the snapshot to restore.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises ApplicationOperationNotSupported: When the application type
            doesn't support restoring snapshots.
        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to use
            a snapshot as the data are needed to restore it.
        :raises MaxJobCountExceeded: When the user already has a running
            job to restore a snapshot of the same type.
        :return: The job that can be used to track the restoring.
        """

        try:
            snapshot = (
                Snapshot.objects.filter(id=snapshot_id)
                .select_for_update(of=("self",))
                .select_related("snapshot_from_application__workspace")
                .get()
            )
        except Snapshot.DoesNotExist:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        CoreHandler().check_permissions(
            performed_by,
            RestoreApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        app_type = application_type_registry.get_by_model(
            snapshot.snapshot_from_application.specific_class
        )
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        self._check_is_in_use(snapshot)

        job = JobHandler().create_and_start_job(
            performed_by,
            RestoreSnapshotJobType.type,
            snapshot=snapshot,
        )

        return job

    def _schedule_deletion(self, snapshot: Snapshot):
        snapshot.mark_for_deletion = True
        snapshot.save()
        if snapshot.snapshot_to_application is not None:
            delete_application_snapshot.delay(snapshot.snapshot_to_application.id)

    def delete(self, snapshot_id: int, performed_by: AbstractUser) -> None:
        """
        Deletes a previously created snapshot with the given ID if the
        provided user belongs to the same workspace as the application.

        :param snapshot_id: The ID of the snapshot to delete.
        :param performed_by: The user performing the operation that should
            have sufficient permissions.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :raises ApplicationOperationNotSupported: When the application type
            doesn't support deleting snapshots.
        :raises SnapshotIsBeingDeleted: When it is not possible to use
            a snapshot as it is being deleted.
        :raises SnapshotIsBeingRestored: When it is not possible to delete
            a snapshot as the data are needed to restore it.
        :raises MaxJobCountExceeded: When the user already has a running
            job to delete a snapshot of the same type.
        """

        try:
            snapshot = (
                Snapshot.objects.filter(id=snapshot_id)
                .select_for_update(of=("self",))
                .select_related("snapshot_from_application__workspace")
                .get()
            )
        except Snapshot.DoesNotExist:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        CoreHandler().check_permissions(
            performed_by,
            DeleteApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        app_type = application_type_registry.get_by_model(
            snapshot.snapshot_from_application.specific_class
        )
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        self._check_is_in_use(snapshot)
        self._schedule_deletion(snapshot)

    def delete_by_application(self, application: Application) -> None:
        """
        Deletes all snapshots related to the provided application.

        :param application: Application for which to delete all related
            snapshots.
        """

        application_snapshots = Snapshot.objects.filter(
            snapshot_from_application=application
        ).select_for_update(of=("self",))
        for snapshot in application_snapshots:
            self._schedule_deletion(snapshot)

    def delete_expired(self) -> None:
        """
        Finds all snapshots that are considered expired based on
        BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS and schedules their deletion.
        """

        threshold = datetime.now(tz=timezone.utc) - timedelta(
            days=settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS
        )
        expired_snapshots = Snapshot.objects.filter(
            created_at__lt=threshold
        ).select_for_update(of=("self",))
        for snapshot in expired_snapshots:
            self._schedule_deletion(snapshot)

    def perform_create(self, snapshot: Snapshot, progress: Progress) -> None:
        """
        Creates an actual copy of the original application and stores it as
        another application with its workspace set to None to effectively hide it
        from the system.

        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        """

        storage = get_default_storage()

        if snapshot is None:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace

        application = snapshot.snapshot_from_application.specific

        # Automatic snapshots are created by the system. The permissions are checked
        # when their schedule is saved.
        if not snapshot.created_automatically:
            CoreHandler().check_permissions(
                snapshot.created_by,
                CreateSnapshotApplicationOperationType.type,
                workspace=workspace,
                context=application,
            )

        application_type = application_type_registry.get_by_model(application)
        snapshot_import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=True,
            workspace_for_user_references=workspace,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )
        try:
            exported_application = application_type.export_serialized(
                application, snapshot_import_export_config, None, storage
            )
        except OperationalError as e:
            # Detect if this `OperationalError` is due to us exceeding the
            # lock count in `max_locks_per_transaction`. If it is, we'll
            # raise a different exception so that we can catch this scenario.
            if is_max_lock_exceeded_exception(e):
                raise DatabaseSnapshotMaxLocksExceededException()
            raise e

        progress.increment(by=50)
        id_mapping = {"import_workspace_id": workspace.id}
        # Set the `snapshot_from` reverse relation so that after
        # `ApplicationType.import_serialized` creates the `Application`,
        # we set the source snapshot so that `get_root()` can be called
        # on this application.
        exported_application["snapshot_from"] = snapshot
        with deferred_callback_context():
            application_type.import_serialized(
                None,
                exported_application,
                snapshot_import_export_config,
                id_mapping,
                None,
                storage,
                progress_builder=progress.create_child_builder(represents_progress=50),
            )

    def perform_restore(
        self,
        snapshot: Snapshot,
        progress: Progress,
        restored_by: AbstractUser | None = None,
    ) -> Application:
        """
        Creates an application copy from the snapshotted application. The copy
        will be available as a normal application in the same workspace as the
        original application.

        :param snapshot: The snapshot to restore.
        :param progress: Reports how far the restore is.
        :param restored_by: The person restoring, whose permission is checked.
            The snapshot's creator when nobody is given.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :returns: Application that is a copy of the snapshot.
        """

        storage = get_default_storage()

        if snapshot is None:
            raise SnapshotDoesNotExist()

        workspace = snapshot.snapshot_from_application.workspace
        CoreHandler().check_permissions(
            restored_by or snapshot.created_by,
            RestoreApplicationSnapshotOperationType.type,
            workspace=workspace,
            context=snapshot,
        )

        application = snapshot.snapshot_to_application.specific
        application_type = application_type_registry.get_by_model(application)

        restore_snapshot_import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            exclude_sensitive_data=False,
            restored_by=restored_by,
        )
        # Temporary set the workspace for the application so that the permissions can
        # be correctly set during the import process.
        application.workspace = workspace
        exported_application = application_type.export_serialized(
            application, restore_snapshot_import_export_config, None, storage
        )
        progress.increment(by=50)

        with deferred_callback_context():
            imported_application = application_type.import_serialized(
                snapshot.snapshot_from_application.workspace,
                exported_application,
                restore_snapshot_import_export_config,
                {},
                None,
                storage,
                progress_builder=progress.create_child_builder(represents_progress=50),
            )
        imported_application.name = CoreHandler().find_unused_application_name(
            snapshot.snapshot_from_application.workspace, snapshot.name
        )
        # The restored application keeps as many snapshots as the one the snapshot
        # was taken of.
        imported_application.snapshot_keep = self.get_copied_keep(
            snapshot.snapshot_from_application.snapshot_keep
        )
        imported_application.save()
        application_created.send(self, application=imported_application, user=None)
        return imported_application

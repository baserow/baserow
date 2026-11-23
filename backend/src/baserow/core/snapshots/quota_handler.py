from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, OuterRef, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Snapshot, Workspace
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import application_type_registry, plugin_registry
from baserow.core.snapshots.exceptions import (
    MaximumSnapshotsReached,
    MaxSnapshotsAboveLimit,
    MaxSnapshotsBelowProtected,
    MaxSnapshotsChangeDeletesSnapshots,
    MaxSnapshotsExceedsAllowance,
    MaxSnapshotsFullOfProtected,
    MaxSnapshotsIsZero,
)
from baserow.core.snapshots.operations import (
    CreateSnapshotApplicationOperationType,
    ListSnapshotsApplicationOperationType,
    ReadWorkspaceSnapshotSettingsOperationType,
    UpdateApplicationMaxSnapshotsOperationType,
    UpdateWorkspaceSnapshotSettingsOperationType,
)
from baserow.core.snapshots.signals import (
    before_snapshot_created,
    max_snapshots_updated,
)


@dataclass
class UpdatedMaxSnapshots:
    """
    The result of changing a max: the max snapshots before and after, and how many
    snapshots were deleted because of it.
    """

    original_max_snapshots: Optional[int]
    new_max_snapshots: Optional[int]
    deleted_count: int


class SnapshotQuotaHandler:
    """Manage snapshot allowances, application maximums and workspace settings."""

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

    def get_max_snapshots_limit(self) -> Optional[int]:
        """
        Returns the most snapshots one application can keep, or `None` when there is
        no maximum.
        """

        max_snapshots_limit = settings.BASEROW_MAX_SNAPSHOTS_PER_APPLICATION
        return max_snapshots_limit if max_snapshots_limit >= 0 else None

    def get_effective_max_snapshots(self, application: Application) -> int:
        """
        Returns how many snapshots the provided application keeps: its own max
        snapshots, or the workspace default max snapshots when it doesn't have one.

        :param application: The application, with its workspace.
        """

        if application.max_snapshots is not None:
            return application.max_snapshots
        return application.workspace.default_max_snapshots

    def _get_applications_with_max_snapshots(self, workspace: Workspace) -> QuerySet:
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
        self, workspace: Workspace, default_max_snapshots: Optional[int] = None
    ) -> int:
        """
        Returns how much of the allowance of the provided workspace its applications
        reserve: the sum of their effective max snapshots.

        :param workspace: The workspace.
        :param default_max_snapshots: The workspace default max snapshots to count with,
            defaults to the current one.
        """

        if default_max_snapshots is None:
            default_max_snapshots = workspace.default_max_snapshots
        used = self._get_applications_with_max_snapshots(workspace).aggregate(
            used=Sum(Coalesce("max_snapshots", Value(default_max_snapshots)))
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
        Whether raising a max can take the provided workspace over its allowance.
        Core never allows it; a plugin can, for example SaaS, which gives the
        workspace a grace period before it refuses new snapshots.

        :param workspace: The workspace.
        """

        return any(
            plugin.allows_max_snapshots_over_allowance(workspace)
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

    def _validate_max_snapshots_change(
        self,
        workspace: Workspace,
        original_max_snapshots: int,
        new_max_snapshots: int,
        original_used: int,
        new_used: int,
        affected: List[tuple],
        delete_snapshots: bool,
    ) -> List:
        """
        Validates a max snapshots change: the max snapshots limit, the allowance, the
        protected snapshots and the snapshots it deletes. It runs the same few queries
        however many applications are affected.

        :param workspace: The locked workspace.
        :param original_max_snapshots: The max snapshots before the change.
        :param new_max_snapshots: The new max snapshots.
        :param original_used: The allowance used before the change.
        :param new_used: The allowance used after the change.
        :param affected: Tuples of each application whose effective max snapshots
            changes and its new effective max snapshots.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            max snapshots is confirmed.
        :return: The ids of the snapshots the change deletes.
        """

        from .handler import SnapshotHandler

        # The limit can be lowered after a max was saved, so it's only checked
        # when the max snapshots goes up.
        max_snapshots_limit = self.get_max_snapshots_limit()
        if (
            max_snapshots_limit is not None
            and new_max_snapshots > max_snapshots_limit
            and new_max_snapshots > original_max_snapshots
        ):
            raise MaxSnapshotsAboveLimit()

        allowance = self.get_allowance(workspace)
        if (
            allowance >= 0
            and new_used > original_used
            and new_used > allowance
            and not self.can_exceed_allowance(workspace)
        ):
            raise MaxSnapshotsExceedsAllowance()

        protected = SnapshotHandler()._count_held(
            [application for application, _ in affected], protected=True
        )
        if any(
            protected.get(application.id, 0) > max_snapshots
            for application, max_snapshots in affected
        ):
            raise MaxSnapshotsBelowProtected()

        to_delete = SnapshotHandler()._get_snapshot_ids_to_rotate(affected)
        if to_delete and not delete_snapshots:
            raise MaxSnapshotsChangeDeletesSnapshots(len(to_delete))
        return to_delete

    def update_application_max_snapshots(
        self,
        application_id: int,
        performed_by: AbstractUser,
        max_snapshots: Optional[int],
        delete_snapshots: bool = False,
    ) -> Tuple[Application, UpdatedMaxSnapshots]:
        """
        Changes how many snapshots the provided application keeps. `None` makes it
        follow the workspace default max snapshots again. Raising a max is only allowed
        within the workspace's allowance, unless a plugin lets it go over; lowering
        one deletes the oldest unprotected snapshots beyond it.

        :param application_id: The id of the application.
        :param performed_by: The user changing the max snapshots.
        :param max_snapshots: The new max snapshots, or `None` to follow the workspace
            default.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            max snapshots is confirmed.
        :raises MaxSnapshotsAboveLimit: When the max snapshots is above the limit.
        :raises MaxSnapshotsExceedsAllowance: When raising the max snapshots reserves
            more than the allowance, and the workspace can't go over it.
        :raises MaxSnapshotsBelowProtected: When the max snapshots is lower than the
            number of protected snapshots.
        :raises MaxSnapshotsChangeDeletesSnapshots: When the change deletes
            snapshots and `delete_snapshots` isn't set.
        :return: The application and the change.
        """

        from .handler import SnapshotHandler

        application = SnapshotHandler()._get_application_for_snapshot(
            application_id,
            performed_by,
            UpdateApplicationMaxSnapshotsOperationType.type,
        )
        workspace = SnapshotHandler()._lock_workspace(application.workspace)
        application.workspace = workspace
        # Another change can be saved while this one waits for the lock, so the max
        # snapshots is read again once it's held.
        application.max_snapshots = (
            Application.objects.filter(id=application.id)
            .values_list("max_snapshots", flat=True)
            .get()
        )

        original_max_snapshots = application.max_snapshots
        original_effective = self.get_effective_max_snapshots(application)
        new_effective = (
            max_snapshots
            if max_snapshots is not None
            else workspace.default_max_snapshots
        )
        original_used = self.get_allowance_used(workspace)
        new_used = original_used - original_effective + new_effective

        to_delete = self._validate_max_snapshots_change(
            workspace,
            original_effective,
            new_effective,
            original_used,
            new_used,
            [(application, new_effective)],
            delete_snapshots,
        )

        Application.objects.filter(id=application.id).update(
            max_snapshots=max_snapshots
        )
        application.max_snapshots = max_snapshots
        deleted = SnapshotHandler()._delete_rotated_snapshots(to_delete)
        max_snapshots_updated.send(self, workspace=workspace)
        return application, UpdatedMaxSnapshots(
            original_max_snapshots, max_snapshots, deleted
        )

    def get_max_snapshots_to_make_room(
        self, application_id: int, performed_by: AbstractUser
    ) -> Optional[int]:
        """
        Returns the max snapshots the provided application needs so that one more
        snapshot fits without replacing one: its max snapshots plus one, when it keeps
        no snapshots or every snapshot it keeps is protected. `None` when it already has
        room. The workspace stays locked until the end of the transaction, so the max
        snapshots can be raised and the snapshot created before another change gets in
        between.

        :param application_id: The id of the application.
        :param performed_by: The user creating the snapshot.
        :raises ApplicationDoesNotExist: When the application doesn't exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the workspace.
        :return: The max snapshots to raise it to, or `None`.
        """

        from .handler import SnapshotHandler

        application = SnapshotHandler()._get_application_for_snapshot(
            application_id,
            performed_by,
            CreateSnapshotApplicationOperationType.type,
        )
        application.workspace = SnapshotHandler()._lock_workspace(application.workspace)
        application.refresh_from_db(fields=["max_snapshots"])
        try:
            SnapshotHandler().check_room_for_snapshot(application)
        except (MaxSnapshotsIsZero, MaxSnapshotsFullOfProtected):
            return self.get_effective_max_snapshots(application) + 1
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

    def update_workspace_default_max_snapshots(
        self,
        workspace_id: int,
        performed_by: AbstractUser,
        max_snapshots: int,
        delete_snapshots: bool = False,
    ) -> Tuple[Workspace, UpdatedMaxSnapshots]:
        """
        Changes the workspace default max snapshots: the max snapshots of its
        applications that don't have their own. The same rules as for an application's
        max snapshots apply to every application that follows it.

        :param workspace_id: The id of the workspace.
        :param performed_by: The user changing the max snapshots.
        :param max_snapshots: The new default max snapshots.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            max snapshots is confirmed.
        :raises MaxSnapshotsAboveLimit: When the max snapshots is above the limit.
        :raises MaxSnapshotsExceedsAllowance: When raising the max snapshots reserves
            more than the allowance, and the workspace can't go over it.
        :raises MaxSnapshotsBelowProtected: When the max snapshots is lower than the
            number of protected snapshots of an application that follows it.
        :raises MaxSnapshotsChangeDeletesSnapshots: When the change deletes
            snapshots and `delete_snapshots` isn't set.
        :return: The workspace and the change.
        """

        from .handler import SnapshotHandler

        workspace = self.get_workspace(
            workspace_id,
            performed_by,
            UpdateWorkspaceSnapshotSettingsOperationType.type,
        )
        workspace = SnapshotHandler()._lock_workspace(workspace)

        original_max_snapshots = workspace.default_max_snapshots
        original_used = self.get_allowance_used(workspace)
        new_used = self.get_allowance_used(
            workspace, default_max_snapshots=max_snapshots
        )
        followers = list(
            self._get_applications_with_max_snapshots(workspace)
            .filter(max_snapshots__isnull=True)
            .select_related("workspace")
        )

        to_delete = self._validate_max_snapshots_change(
            workspace,
            original_max_snapshots,
            max_snapshots,
            original_used,
            new_used,
            [(application, max_snapshots) for application in followers],
            delete_snapshots,
        )

        Workspace.objects.filter(id=workspace.id).update(
            default_max_snapshots=max_snapshots
        )
        workspace.default_max_snapshots = max_snapshots
        deleted = SnapshotHandler()._delete_rotated_snapshots(to_delete)
        max_snapshots_updated.send(self, workspace=workspace)
        return workspace, UpdatedMaxSnapshots(
            original_max_snapshots, max_snapshots, deleted
        )

    def _get_allowance_values(self, workspace: Workspace) -> Dict[str, Any]:
        """
        Returns the allowance values of the provided workspace that the snapshot
        modal and the workspace settings show.
        """

        from .handler import SnapshotHandler

        allowance = self.get_allowance(workspace)
        used = self.get_allowance_used(workspace)
        return {
            "used": used,
            "limit": allowance if allowance >= 0 else None,
            "over_allowance": allowance >= 0 and used > allowance,
            "blocked": self.is_snapshot_creation_blocked(workspace),
            "can_exceed_allowance": self.can_exceed_allowance(workspace),
            "snapshot_count": SnapshotHandler().count(workspace),
            "default_max_snapshots": workspace.default_max_snapshots,
            "max_snapshots_limit": self.get_max_snapshots_limit(),
            "expiration_days": settings.BASEROW_SNAPSHOT_EXPIRATION_TIME_DAYS,
        }

    def get_usage(self, application_id: int, performed_by: AbstractUser) -> Dict:
        """
        Returns the snapshot allowance of the workspace of the given application and
        how much of it is reserved, together with the max snapshots of the application.

        :param application_id: The ID of the application.
        :param performed_by: The user performing the operation that should have
            sufficient permissions.
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :raises UserNotInWorkspace: When the user doesn't belong to the same workspace
            as the application.
        :return: A dict with the allowance values, `max_snapshots` (`None` when the
            application follows the workspace default), `effective_max_snapshots`,
            `snapshot_count_in_application` and `protected_count`.
        """

        from .handler import SnapshotHandler

        application = SnapshotHandler()._get_application_for_snapshot(
            application_id, performed_by, ListSnapshotsApplicationOperationType.type
        )
        restorable = Snapshot.objects.restorable().filter(
            snapshot_from_application=application
        )
        return {
            **self._get_allowance_values(application.workspace),
            "max_snapshots": application.max_snapshots,
            "effective_max_snapshots": self.get_effective_max_snapshots(application),
            "application_snapshot_count": restorable.count(),
            "protected_count": restorable.filter(protected=True).count(),
        }

    def get_workspace_settings(
        self, workspace_id: int, performed_by: AbstractUser
    ) -> Dict:
        """
        Returns the snapshot allowance of the provided workspace, how much of it is
        reserved, and the max snapshots and snapshots of every application the user can
        see.

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
            self._get_applications_with_max_snapshots(workspace),
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
                    "max_snapshots": application.max_snapshots,
                    "snapshot_count": application.snapshot_count,
                    "protected_count": application.protected_count,
                }
                for application in applications
            ],
        }

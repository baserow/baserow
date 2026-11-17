import dataclasses
from typing import Optional, Tuple

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.models import Application, Snapshot, Workspace
from baserow.core.snapshots.exceptions import SnapshotDoesNotExist
from baserow.core.snapshots.handler import SnapshotHandler, UpdatedSnapshotKeep
from baserow.core.utils import Progress


class CreateSnapshotActionType(ActionType):
    type = "create_snapshot"
    description = ActionTypeDescription(
        _("Create Snapshot"),
        _(
            'Snapshot "%(snapshot_name)s" (%(snapshot_id)s) created for '
            'application "%(application_name)s" (%(application_id)s).'
        ),
    )
    analytics_params = [
        "application_id",
        "snapshot_id",
    ]

    @dataclasses.dataclass
    class Params:
        application_id: int
        application_name: str
        snapshot_id: int
        snapshot_name: str

    @classmethod
    def do(cls, user: AbstractUser, snapshot: Snapshot, progress: Progress):
        """
        Creates a snapshot for the given application.

        :param application_id: The id of the application for which a snapshot will be
            created.
        :param user: The user performing the delete.
        :param name: The name that will be given to the snapshot.
        """

        snapshot_created = SnapshotHandler().perform_create(snapshot, progress)
        application = snapshot.snapshot_from_application
        workspace = application.workspace

        # Once the new snapshot is committed, the oldest unprotected ones beyond the
        # application's keep are deleted. It's robust, so a failure is logged instead
        # of failing a job whose snapshot was created. The next rotation, after the
        # next snapshot or keep change, deletes them instead.
        transaction.on_commit(
            lambda application_id=application.id: SnapshotHandler().rotate_after_create(
                application_id
            ),
            robust=True,
        )

        cls.register_action(
            user=user,
            params=cls.Params(
                application.id, application.name, snapshot.id, snapshot.name
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return snapshot_created

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class RestoreSnapshotActionType(ActionType):
    type = "restore_snapshot"
    description = ActionTypeDescription(
        _("Restore Snapshot"),
        _(
            'Snapshot "%(snapshot_name)s" (%(snapshot_id)s) restored from application '
            '"%(original_application_name)s" (%(original_application_id)s) '
            'to application "%(application_name)s" (%(application_id)s).'
        ),
    )
    analytics_params = [
        "application_id",
        "snapshot_id",
        "original_application_id",
    ]

    @dataclasses.dataclass
    class Params:
        application_id: int
        application_name: str
        snapshot_id: int
        snapshot_name: str
        original_application_id: int
        original_application_name: str

    @classmethod
    def do(cls, user: AbstractUser, snapshot: Snapshot, progress: Progress):
        """
        Creates a snapshot for the given application.

        :param snapshot_id: The id of the snapshot that will be restored.
        :param user: The user performing the delete.

        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
        """

        original_application = snapshot.snapshot_from_application
        application = SnapshotHandler().perform_restore(
            snapshot, progress, restored_by=user
        )

        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                snapshot.id,
                snapshot.name,
                original_application.id,
                original_application.name,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return application

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class DeleteSnapshotActionType(ActionType):
    type = "delete_snapshot"
    description = ActionTypeDescription(
        _("Delete Snapshot"),
        _(
            'Snapshot "%(snapshot_name)s" (%(snapshot_id)s) deleted for '
            'application "%(application_name)s" (%(application_id)s).'
        ),
    )
    analytics_params = [
        "application_id",
        "snapshot_id",
    ]

    @dataclasses.dataclass
    class Params:
        application_id: int
        application_name: str
        snapshot_id: int
        snapshot_name: str

    @classmethod
    def do(cls, user: AbstractUser, snapshot_id: int):
        """
        Creates a snapshot for the given application.

        :param user: The user performing the delete.
        :param snapshot_id: The id of the snapshot that will be deleted.
        :raises SnapshotDoesNotExist: When the snapshot with the provided id
            does not exist.
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

        application = snapshot.snapshot_from_application
        workspace = application.workspace
        snapshot_name = snapshot.name

        SnapshotHandler().delete(snapshot.id, performed_by=user)

        cls.register_action(
            user=user,
            params=cls.Params(
                application.id, application.name, snapshot_id, snapshot_name
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateApplicationSnapshotKeepActionType(ActionType):
    """
    Changing a keep isn't undoable, because lowering it can delete snapshots. It's
    registered as an action so that it's recorded in the audit log.
    """

    type = "update_application_snapshot_keep"
    description = ActionTypeDescription(
        _("Update application snapshot keep"),
        _(
            'Snapshot keep of application "%(application_name)s" '
            "(%(application_id)s) changed from %(original_keep)s to %(keep)s, "
            "deleting %(deleted_count)s snapshot(s)."
        ),
    )
    analytics_params = ["application_id", "keep", "deleted_count"]

    @dataclasses.dataclass
    class Params:
        application_id: int
        application_name: str
        original_keep: Optional[int]
        keep: Optional[int]
        deleted_count: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        application_id: int,
        keep: Optional[int],
        delete_snapshots: bool = False,
    ) -> Tuple[Application, UpdatedSnapshotKeep]:
        """
        Changes how many snapshots an application keeps.

        :param user: The user changing the keep.
        :param application_id: The id of the application.
        :param keep: The new keep, or `None` to follow the workspace default.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            keep is confirmed.
        :return: The application and the change.
        """

        application, updated = SnapshotHandler().update_application_keep(
            application_id, user, keep, delete_snapshots=delete_snapshots
        )
        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                updated.original_keep,
                updated.new_keep,
                updated.deleted_count,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return application, updated

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateWorkspaceSnapshotDefaultKeepActionType(ActionType):
    """
    Changing a keep isn't undoable, because lowering it can delete snapshots. It's
    registered as an action so that it's recorded in the audit log.
    """

    type = "update_workspace_snapshot_default_keep"
    description = ActionTypeDescription(
        _("Update workspace default snapshot keep"),
        _(
            'Default snapshot keep of workspace "%(group_name)s" (%(group_id)s) '
            "changed from %(original_keep)s to %(keep)s, deleting "
            "%(deleted_count)s snapshot(s)."
        ),
    )
    analytics_params = ["workspace_id", "keep", "deleted_count"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        original_keep: int
        keep: int
        deleted_count: int

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace_id: int,
        keep: int,
        delete_snapshots: bool = False,
    ) -> Tuple[Workspace, UpdatedSnapshotKeep]:
        """
        Changes the workspace default keep.

        :param user: The user changing the keep.
        :param workspace_id: The id of the workspace.
        :param keep: The new default keep.
        :param delete_snapshots: Whether deleting the snapshots beyond a lowered
            keep is confirmed.
        :return: The workspace and the change.
        """

        workspace, updated = SnapshotHandler().update_workspace_default_keep(
            workspace_id, user, keep, delete_snapshots=delete_snapshots
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                updated.original_keep,
                updated.new_keep,
                updated.deleted_count,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return workspace, updated

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateSnapshotProtectionActionType(ActionType):
    type = "update_snapshot_protection"
    description = ActionTypeDescription(
        _("Update snapshot protection"),
        _(
            'Snapshot "%(snapshot_name)s" (%(snapshot_id)s) of application '
            '"%(application_name)s" (%(application_id)s) protected: %(protected)s.'
        ),
    )
    analytics_params = ["application_id", "snapshot_id", "protected"]

    @dataclasses.dataclass
    class Params:
        application_id: int
        application_name: str
        snapshot_id: int
        snapshot_name: str
        protected: bool

    @classmethod
    def do(cls, user: AbstractUser, snapshot_id: int, protected: bool) -> Snapshot:
        """
        Protects or unprotects a snapshot.

        :param user: The user changing it.
        :param snapshot_id: The id of the snapshot.
        :param protected: Whether the snapshot is protected.
        :return: The updated snapshot.
        """

        snapshot = SnapshotHandler().update_protected(snapshot_id, user, protected)
        application = snapshot.snapshot_from_application
        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                application.id,
                application.name,
                snapshot.id,
                snapshot.name,
                protected,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return snapshot

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

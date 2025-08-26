import dataclasses
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.models import Action
from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
    UndoableActionType,
)
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    RootActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.handler import CoreHandler, WorkspaceForUpdate
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.models import (
    Application,
    ImportExportResource,
    Template,
    Workspace,
    WorkspaceInvitation,
    WorkspaceUser,
)
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import ChildProgressBuilder


class DeleteWorkspaceActionType(UndoableActionType):
    type = "delete_group"
    description = ActionTypeDescription(
        _("Delete group"),
        _('Group "%(group_name)s" (%(group_id)s) deleted.'),
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, workspace: WorkspaceForUpdate):
        """
        Deletes an existing workspace and related applications if the user has admin
        permissions for the workspace.
        See baserow.core.handler.CoreHandler.delete_workspace for more details.
        Undoing this action restores the workspace, redoing it deletes it again.

        :param user: The user performing the deletion.
        :param workspace: A LockedWorkspace obtained from
            CoreHandler.get_workspace_for_update which will be deleted.
        """

        CoreHandler().delete_workspace(user, workspace)

        cls.register_action(
            user=user,
            params=cls.Params(workspace.id, workspace.name),
            scope=cls.scope(),
            workspace=workspace,
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        TrashHandler.restore_item(
            user,
            "workspace",
            params.workspace_id,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        CoreHandler().delete_workspace_by_id(user, params.workspace_id)


class CreateWorkspaceActionType(UndoableActionType):
    type = "create_group"
    description = ActionTypeDescription(
        _("Create group"),
        _('Group "%(group_name)s" (%(group_id)s) created.'),
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, workspace_name: str) -> WorkspaceUser:
        """
        Creates a new workspace for an existing user. See
        baserow.core.handler.CoreHandler.create_workspace for more details. Undoing this
        action deletes the created workspace, redoing it restores it from the trash.

        :param user: The user creating the workspace.
        :param workspace_name: The name to give the workspace.
        """

        workspace_user = CoreHandler().create_workspace(user, name=workspace_name)
        workspace = workspace_user.workspace

        cls.register_action(
            user=user,
            params=cls.Params(workspace.id, workspace_name),
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        CoreHandler().delete_workspace_by_id(user, params.workspace_id)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        TrashHandler.restore_item(
            user, "workspace", params.workspace_id, parent_trash_item_id=None
        )


class UpdateWorkspaceActionType(UndoableActionType):
    type = "update_group"
    description = ActionTypeDescription(
        _("Update group"),
        _(
            "Group (%(group_id)s) name changed from "
            '"%(original_group_name)s" to "%(group_name)s."'
        ),
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        original_workspace_name: str

    @classmethod
    def do(
        cls, user: AbstractUser, workspace: WorkspaceForUpdate, new_workspace_name: str
    ) -> WorkspaceForUpdate:
        """
        Updates the values of a workspace if the user has admin permissions to the
        workspace. See baserow.core.handler.CoreHandler.upgrade_workspace for more
        details. Undoing this action restores the name of the workspace prior to this
        action being performed, redoing this restores the new name set initially.

        :param user: The user creating the workspace.
        :param workspace: A LockedWorkspace obtained from
            CoreHandler.get_workspace_for_update on which the update will be run.
        :param new_workspace_name: The new name to give the workspace.
        :return: The updated workspace.
        """

        original_workspace_name = workspace.name
        CoreHandler().update_workspace(user, workspace, name=new_workspace_name)

        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace_name=new_workspace_name,
                original_workspace_name=original_workspace_name,
            ),
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        workspace = CoreHandler().get_workspace_for_update(params.workspace_id)
        CoreHandler().update_workspace(
            user,
            workspace,
            name=params.original_workspace_name,
        )

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        workspace = CoreHandler().get_workspace_for_update(params.workspace_id)
        CoreHandler().update_workspace(
            user,
            workspace,
            name=params.new_workspace_name,
        )


class OrderWorkspacesActionType(UndoableActionType):
    type = "order_groups"
    description = ActionTypeDescription(
        _("Order groups"),
        _("Groups order changed."),
    )

    @dataclasses.dataclass
    class Params:
        workspace_ids: List[int]
        original_workspace_ids: List[int]

    @classmethod
    def do(cls, user: AbstractUser, workspace_ids_in_order: List[int]) -> None:
        """
        Changes the order of workspaces for a user.
        See baserow.core.handler.CoreHandler.order_workspaces for more details. Undoing
        this action restores the original order of workspaces prior to this action being
        performed, redoing this restores the new order set initially.

        :param user: The user ordering the workspaces.
        :param workspace_ids_in_order: The ids of the workspaces to order.
        """

        original_workspace_ids_in_order = CoreHandler().get_workspaces_order(user)

        CoreHandler().order_workspaces(user, workspace_ids_in_order)

        cls.register_action(
            user=user,
            params=cls.Params(
                workspace_ids_in_order,
                original_workspace_ids_in_order,
            ),
            scope=cls.scope(),
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()

    @classmethod
    def undo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_undo: Action,
    ):
        CoreHandler().order_workspaces(user, params.original_workspace_ids)

    @classmethod
    def redo(
        cls,
        user: AbstractUser,
        params: Params,
        action_to_redo: Action,
    ):
        CoreHandler().order_workspaces(user, params.workspace_ids)


class OrderApplicationsActionType(UndoableActionType):
    type = "order_applications"
    description = ActionTypeDescription(
        _("Order applications"), _("Applications reordered"), WORKSPACE_ACTION_CONTEXT
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_ids: List[int]
        original_application_ids: List[int]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        application_ids_in_order: List[int],
    ) -> Any:
        """
        Reorders the applications of a given workspace in the desired order. The index
        of the id in the list will be the new order. See
        `baserow.core.handler.CoreHandler.order_applications` for further details. When
        undone re-orders the applications back to the old order, when redone reorders
        to the new order.

        :param user: The user on whose behalf the applications are reordered.
        :param workspace: The workspace where the applications are in.
        :param application_ids_in_order: A list of ids in the new order.
        """

        original_application_ids_in_order = list(
            CoreHandler().order_applications(user, workspace, application_ids_in_order)
        )

        params = cls.Params(
            workspace.id,
            workspace.name,
            application_ids_in_order,
            original_application_ids_in_order,
        )
        cls.register_action(
            user, params, scope=cls.scope(workspace.id), workspace=workspace
        )

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        workspace = CoreHandler().get_workspace_for_update(params.workspace_id)
        CoreHandler().order_applications(
            user, workspace, params.original_application_ids
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        workspace = CoreHandler().get_workspace_for_update(params.workspace_id)
        CoreHandler().order_applications(user, workspace, params.application_ids)


class CreateApplicationActionType(UndoableActionType):
    type = "create_application"
    description = ActionTypeDescription(
        _("Create application"),
        _('"%(application_name)s" (%(application_id)s) %(application_type)s created'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_type",
        "application_id",
        "with_data",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_type: str
        application_id: int
        application_name: str
        with_data: bool

    @classmethod
    def do(
        cls, user: AbstractUser, workspace: Workspace, application_type: str, **kwargs
    ) -> Any:
        """
        Creates a new application based on the provided type. See
        baserow.core.handler.CoreHandler.create_application for further details.
        Undoing this action trashes the application and redoing restores it.

        :param user: The user creating the application.
        :param workspace: The workspace to create the application in.
        :param application_type: The type of application to create.
        :param kwargs: Additional parameters to pass to the application creation.
        :return: The created Application model instance.
        """

        init_with_data = kwargs.get("init_with_data", False)
        application = CoreHandler().create_application(
            user, workspace, application_type, **kwargs
        )

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )

        # Only register an action if this application type supports actions.
        # At the moment, the builder application doesn't use actions and need
        # to bypass registering.
        if application_type.supports_actions:
            params = cls.Params(
                workspace.id,
                workspace.name,
                application_type.type,
                application.id,
                application.name,
                init_with_data,
            )
            cls.register_action(
                user, params, scope=cls.scope(workspace.id), workspace=workspace
            )

        return application

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        application = Application.objects.get(id=params.application_id)
        CoreHandler().delete_application(user, application)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user, "application", params.application_id, parent_trash_item_id=None
        )


class DeleteApplicationActionType(UndoableActionType):
    type = "delete_application"
    description = ActionTypeDescription(
        _("Delete application"),
        _(
            'Application "%(application_name)s" (%(application_id)s) of type '
            "%(application_type)s deleted"
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_type",
        "application_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_type: str
        application_id: int
        application_name: str

    @classmethod
    def do(cls, user: AbstractUser, application: Application) -> None:
        """
        Deletes an existing application instance if the user has access to the
        related workspace. The `application_deleted` signal is also called.
        See baserow.core.handler.CoreHandler.delete_application for further details.
        Undoing this action restores the application and redoing trashes it.

        :param user: The user on whose behalf the application is deleted.
        :param application: The application instance that needs to be deleted.
        """

        CoreHandler().delete_application(user, application)

        workspace = application.workspace
        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        params = cls.Params(
            workspace.id,
            workspace.name,
            application_type.type,
            application.id,
            application.name,
        )
        cls.register_action(
            user, params, scope=cls.scope(workspace.id), workspace=workspace
        )

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user, params: Params, action_being_undone: Action):
        TrashHandler.restore_item(
            user, "application", params.application_id, parent_trash_item_id=None
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        application = CoreHandler().get_application(params.application_id)
        CoreHandler().delete_application(user, application)


class UpdateApplicationActionType(UndoableActionType):
    type = "update_application"
    description = ActionTypeDescription(
        _("Update application"),
        _(
            "Application (%(application_id)s) of type %(application_type)s renamed "
            'from "%(original_application_name)s" to "%(application_name)s"'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_type",
        "application_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_type: str
        application_id: int
        application_name: Optional[str]
        original_application_name: str
        data: Dict[str, Any]
        original_data: Dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, application: Application, **kwargs) -> Application:
        """
        Updates an existing application instance.
        See baserow.core.handler.CoreHandler.update_application for further details.
        Undoing this action restore the original_name while redoing set name again.

        :param user: The user on whose behalf the application is updated.
        :param application: The application instance that needs to be updated.
        :param kwargs: Additional parameters to pass to the application update.
        :raises ValueError: If one of the provided parameters is invalid.
        :return: The updated application instance.
        """

        original_name = application.name

        app_updated_result = CoreHandler().update_application(
            user, application, **kwargs
        )
        application = app_updated_result.updated_application_instance

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        workspace = application.workspace

        # Only register an action if this application type supports actions.
        # At the moment, the builder application doesn't use actions and need
        # to bypass registering.
        if application_type.supports_actions:
            # name is stored separately so it will be removed here from
            # others allowed_values
            app_updated_result.updated_app_allowed_values.pop("name", None)
            app_updated_result.original_app_allowed_values.pop("name", None)

            params = cls.Params(
                workspace.id,
                workspace.name,
                application_type.type,
                application.id,
                kwargs.get("name", original_name),
                original_name,
                app_updated_result.updated_app_allowed_values,
                app_updated_result.original_app_allowed_values,
            )
            cls.register_action(
                user, params, scope=cls.scope(workspace.id), workspace=workspace
            )

        return application

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        application = CoreHandler().get_application(params.application_id).specific
        CoreHandler().update_application(
            user,
            application,
            name=params.original_application_name,
            **params.original_data,
        )

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        application = CoreHandler().get_application(params.application_id).specific
        CoreHandler().update_application(
            user, application, name=params.application_name, **params.data
        )


class DuplicateApplicationActionType(UndoableActionType):
    type = "duplicate_application"
    description = ActionTypeDescription(
        _("Duplicate application"),
        _(
            'Application "%(application_name)s" (%(application_id)s) of type %(application_type)s '
            'duplicated from "%(original_application_name)s" (%(original_application_id)s)'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_type",
        "application_id",
        "original_application_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_type: str
        application_id: int
        application_name: str
        original_application_id: int
        original_application_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        application: Application,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Duplicate an existing application instance.
        See baserow.core.handler.CoreHandler.duplicate_application for further details.
        Undoing this action trashes the application and redoing restores it.

        :param user: The user on whose behalf the application is duplicated.
        :param application: The application instance that needs to be duplicated.
        :param progress_builder: A progress builder instance that can be used to
            track the progress of the duplication.
        :return: The new (duplicated) application instance.
        """

        new_app_clone = CoreHandler().duplicate_application(
            user,
            application,
            progress_builder,
        )
        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        workspace = application.workspace

        params = cls.Params(
            workspace.id,
            workspace.name,
            application_type.type,
            new_app_clone.id,
            new_app_clone.name,
            application.id,
            application.name,
        )
        cls.register_action(user, params, cls.scope(workspace.id), workspace=workspace)

        return new_app_clone

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        application = CoreHandler().get_application(params.application_id)
        CoreHandler().delete_application(user, application)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        TrashHandler.restore_item(
            user, "application", params.application_id, parent_trash_item_id=None
        )


class InstallTemplateActionType(UndoableActionType):
    type = "install_template"
    description = ActionTypeDescription(
        _("Install template"),
        _(
            'Template "%(template_name)s" (%(template_id)s) installed '
            "into application IDs %(installed_application_ids)s"
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "template_id",
        "installed_application_ids",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        template_id: int
        template_name: str
        installed_application_ids: List[int]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        template: Template,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Install a template into the provided workspace. See
        baserow.core.handler.CoreHandler.install_template for further details.
        Undoing this action trash the installed applications and redoing
        restore them all.

        :param user: The user on whose behalf the template is installed.
        :param workspace: The workspace where the applications will be installed.
        :param template: The template to install.
        :param progress_builder: A progress builder instance that can be used to
            track the progress of the installation.
        :return: The list of installed applications.
        """

        installed_applications, _ = CoreHandler().install_template(
            user,
            workspace,
            template,
            progress_builder=progress_builder,
        )

        params = cls.Params(
            workspace.id,
            workspace.name,
            template.id,
            template.name,
            [app.id for app in installed_applications],
        )
        cls.register_action(
            user, params, scope=cls.scope(workspace.id), workspace=workspace
        )

        return installed_applications

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

    @classmethod
    def undo(cls, user: AbstractUser, params: Params, action_being_undone: Action):
        handler = CoreHandler()
        for application_id in params.installed_application_ids:
            application = CoreHandler().get_application(application_id)
            handler.delete_application(user, application)

    @classmethod
    def redo(cls, user: AbstractUser, params: Params, action_being_redone: Action):
        for application_id in params.installed_application_ids:
            TrashHandler.restore_item(
                user, "application", application_id, parent_trash_item_id=None
            )


class CreateWorkspaceInvitationActionType(ActionType):
    type = "create_group_invitation"
    description = ActionTypeDescription(
        _("Create group invitation"),
        _(
            'Group invitation created for "%(email)s" to join '
            '"%(group_name)s" (%(group_id)s) as %(permissions)s.'
        ),
    )
    analytics_params = [
        "permissions",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        email: str
        permissions: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        email: str,
        permissions: str,
        base_url: str,
        message: str = "",
    ) -> WorkspaceInvitation:
        """
        Creates a new workspace invitation for the given email address and sends out an
        email containing the invitation.
        Look into baserow.core.handler.CoreHandler.create_workspace_invitation for
        further details.


        """

        workspace_invitation = CoreHandler().create_workspace_invitation(
            user, workspace, email, permissions, base_url, message
        )

        cls.register_action(
            user=user,
            params=cls.Params(email, permissions, workspace.id, workspace.name),
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_invitation

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class DeleteWorkspaceInvitationActionType(ActionType):
    type = "delete_group_invitation"
    description = ActionTypeDescription(
        _("Delete group invitation"),
        _(
            'Group invitation (%(invitation_id)s) deleted for "%(email)s" '
            'to join "%(group_name)s" (%(group_id)s) as %(permissions)s.'
        ),
    )
    analytics_params = [
        "invitation_id",
        "permissions",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        invitation_id: int
        email: str
        permissions: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace_invitation: WorkspaceInvitation,
    ):
        """
        Deletes an existing workspace invitation.
        Look into baserow.core.handler.CoreHandler.delete_workspace_invitation
        for further details.


        """

        workspace = workspace_invitation.workspace
        params = cls.Params(
            workspace_invitation.id,
            workspace_invitation.email,
            workspace_invitation.permissions,
            workspace.id,
            workspace.name,
        )
        CoreHandler().delete_workspace_invitation(user, workspace_invitation)

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_invitation

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class AcceptWorkspaceInvitationActionType(ActionType):
    type = "accept_group_invitation"
    description = ActionTypeDescription(
        _("Accept group invitation"),
        _(
            'Invitation (%(invitation_id)s) sent by "%(sender)s" to join '
            '"%(group_name)s" (%(group_id)s) as %(permissions)s was accepted.'
        ),
    )
    analytics_params = [
        "invitation_id",
        "permissions",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        invitation_id: int
        sender: str
        permissions: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace_invitation: WorkspaceInvitation,
    ) -> WorkspaceUser:
        """
        Accepts an existing workspace invitation.
        Look into baserow.core.handler.CoreHandler.accept_workspace_invitation for
        further details.
        """

        workspace = workspace_invitation.workspace
        params = cls.Params(
            workspace_invitation.id,
            workspace_invitation.invited_by.email,
            workspace_invitation.permissions,
            workspace.id,
            workspace.name,
        )
        workspace_user = CoreHandler().accept_workspace_invitation(
            user, workspace_invitation
        )

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class RejectWorkspaceInvitationActionType(ActionType):
    type = "reject_group_invitation"
    description = ActionTypeDescription(
        _("Reject group invitation"),
        _(
            'Invitation (%(invitation_id)s) sent by "%(sender)s" to join '
            '"%(group_name)s" (%(group_id)s) as %(permissions)s was rejected.'
        ),
    )
    analytics_params = [
        "invitation_id",
        "permissions",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        invitation_id: int
        sender: str
        permissions: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace_invitation: WorkspaceInvitation,
    ) -> WorkspaceUser:
        """
        Accepts an existing workspace invitation.
        Look into baserow.core.handler.CoreHandler.reject_workspace_invitation for
        further details.
        """

        workspace = workspace_invitation.workspace
        params = cls.Params(
            workspace_invitation.id,
            workspace_invitation.invited_by.email,
            workspace_invitation.permissions,
            workspace.id,
            workspace.name,
        )
        workspace_user = CoreHandler().reject_workspace_invitation(
            user, workspace_invitation
        )

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class UpdateWorkspaceInvitationActionType(ActionType):
    type = "update_group_invitation_permissions"
    description = ActionTypeDescription(
        _("Update group invitation permissions"),
        _(
            "Invitation (%(invitation_id)s) permissions changed from "
            "%(original_permissions)s to %(permissions)s for %(email)s "
            ' on group "%(group_name)s" (%(group_id)s).'
        ),
    )
    analytics_params = [
        "invitation_id",
        "permissions",
        "workspace_id",
        "original_permissions",
    ]

    @dataclasses.dataclass
    class Params:
        invitation_id: int
        email: str
        permissions: str
        workspace_id: int
        workspace_name: str
        original_permissions: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace_invitation: WorkspaceInvitation,
        permissions: str,
    ) -> WorkspaceInvitation:
        """
        Updates an existing workspace invitation permissions.
        Look into baserow.core.handler.CoreHandler.update_workspace_invitation for
        further details.
        """

        workspace = workspace_invitation.workspace
        params = cls.Params(
            workspace_invitation.id,
            workspace_invitation.email,
            permissions,
            workspace.id,
            workspace.name,
            original_permissions=workspace_invitation.permissions,
        )
        workspace_invitation = CoreHandler().update_workspace_invitation(
            user, workspace_invitation, permissions
        )

        cls.register_action(
            user=user,
            params=params,
            scope=cls.scope(),
            workspace=workspace,
        )
        return workspace_invitation

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class LeaveWorkspaceActionType(ActionType):
    type = "leave_group"
    description = ActionTypeDescription(
        _("Leave group"),
        _('Group "%(group_name)s" (%(group_id)s) left.'),
    )
    analytics_params = [
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, workspace: Workspace):
        """
        Leaves an existing workspace.
        Look into baserow.core.handler.CoreHandler.leave_workspace for further details.
        """

        CoreHandler().leave_workspace(user, workspace)

        cls.register_action(
            user=user,
            params=cls.Params(workspace.id, workspace.name),
            scope=cls.scope(),
            workspace=workspace,
        )

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class CreateInitialWorkspaceActionType(ActionType):
    type = "create_initial_workspace"
    description = ActionTypeDescription(
        _("Create initial workspace"),
        _("Initial workspace created"),
    )
    analytics_params = []

    @dataclasses.dataclass
    class Params:
        pass

    @classmethod
    def do(cls, user: AbstractUser) -> WorkspaceUser:
        workspace_user = CoreHandler().create_initial_workspace(user)

        cls.register_action(
            user=user,
            params=cls.Params(),
            scope=cls.scope(),
            workspace=workspace_user.workspace,
        )
        return workspace_user

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()


class ExportApplicationsActionType(ActionType):
    type = "export_applications"
    description = ActionTypeDescription(
        _("Export applications"),
        _('Applications "%(application_names)s" (%(application_ids)s) exported'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "application_ids",
        "resource_id",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_ids: List[int]
        application_names: List[str]
        resource_id: str
        resource_file_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        applications: List[Application],
        only_structure: bool = False,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> ImportExportResource:
        """
        Export provided Applications set from the given workspace.
        This action is readonly and is not undoable.

        :param user: The user on whose behalf the application is exported.
        :param workspace: Workspace instance from which applications are exported.
        :param applications: List of application instances to be exported
        :param only_structure: If True, only the structure of the applications
            will be exported.
        :param progress_builder: A progress builder instance that can be used to
            track the progress of the export.
        :return: The created ImportExportResource instance.
        """

        cli_import_export_config = ImportExportConfig(
            include_permission_data=False,
            reduce_disk_space_usage=False,
            only_structure=only_structure,
        )

        resource = ImportExportHandler().export_workspace_applications(
            applications=applications,
            import_export_config=cli_import_export_config,
            progress_builder=progress_builder,
        )

        params = cls.Params(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            application_ids=[application.id for application in applications],
            application_names=[application.name for application in applications],
            resource_id=str(resource.uuid),
            resource_file_name=resource.get_archive_name(),
        )

        cls.register_action(user, params, cls.scope(workspace.id), workspace=workspace)
        return resource

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class ImportApplicationsActionType(ActionType):
    type = "import_applications"
    description = ActionTypeDescription(
        _("Import applications"),
        _('Applications "%(application_names)s" (%(application_ids)s) imported'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "workspace_id",
        "resource_id",
        "application_ids",
    ]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        resource_id: int
        resource_file_name: str
        application_ids: List[int]
        application_names: List[str]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        resource: ImportExportResource,
        application_ids: Optional[List[int]] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Imports applications from the provided file into the specified workspace.

        This method handles the import process, including reading the file,
        validating its contents, and creating the necessary application instances
        within the workspace. The import process can be tracked using the optional
        progress builder.

        :param user: The user performing the import.
        :param workspace: The workspace where the applications will be imported.
        :param resource: The resource containing the applications to import.
        :param application_ids: Optional list of application IDs to import from the
            resource. If not provided, all applications in the resource will be
            imported.
        :param progress_builder: An optional progress builder to track the import
            progress.
        :return: A list of the imported Application instances.
        """

        applications = ImportExportHandler().import_workspace_applications(
            user=user,
            workspace=workspace,
            resource=resource,
            application_ids=application_ids,
            progress_builder=progress_builder,
        )

        params = cls.Params(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            application_ids=[app.id for app in applications],
            application_names=[app.name for app in applications],
            resource_id=resource.id,
            resource_file_name=resource.get_archive_name(),
        )

        cls.register_action(user, params, cls.scope(workspace.id), workspace=workspace)
        return applications

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)

import hashlib
import json
import os
import re
from dataclasses import dataclass
from io import BufferedReader, BytesIO
from pathlib import Path
from typing import IO, Any, Callable, Dict, List, NewType, Optional, Tuple, Union, cast
from urllib.parse import urljoin, urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.core.files.storage import Storage
from django.db import OperationalError, transaction
from django.db.models import Count, Model, Prefetch, Q, QuerySet
from django.utils import translation
from django.utils.translation import gettext as _

import zipstream
from itsdangerous import URLSafeSerializer
from loguru import logger
from opentelemetry import trace
from tqdm import tqdm

from baserow.core.db import specific_queryset
from baserow.core.registries import plugin_registry
from baserow.core.user.utils import normalize_email_address

from .context import clear_current_workspace_id, set_current_workspace_id
from .emails import WorkspaceInvitationEmail
from .exceptions import (
    ApplicationDoesNotExist,
    ApplicationNotInWorkspace,
    BaseURLHostnameNotAllowed,
    CannotDeleteYourselfFromWorkspace,
    DuplicateApplicationMaxLocksExceededException,
    InvalidPermissionContext,
    LastAdminOfWorkspace,
    MaxNumberOfPendingWorkspaceInvitesReached,
    PermissionDenied,
    PermissionException,
    TemplateDoesNotExist,
    TemplateFileDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
    WorkspaceInvitationDoesNotExist,
    WorkspaceInvitationEmailMismatch,
    WorkspaceUserAlreadyExists,
    WorkspaceUserDoesNotExist,
    WorkspaceUserIsLastAdmin,
    is_max_lock_exceeded_exception,
)
from .models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    WORKSPACE_USER_PERMISSION_MEMBER,
    Application,
    Settings,
    Template,
    TemplateCategory,
    Workspace,
    WorkspaceInvitation,
    WorkspaceUser,
)
from .operations import (
    CreateApplicationsWorkspaceOperationType,
    CreateInvitationsWorkspaceOperationType,
    CreateWorkspaceOperationType,
    DeleteApplicationOperationType,
    DeleteWorkspaceInvitationOperationType,
    DeleteWorkspaceOperationType,
    DeleteWorkspaceUserOperationType,
    DuplicateApplicationOperationType,
    OrderApplicationsOperationType,
    ReadApplicationOperationType,
    UpdateApplicationOperationType,
    UpdateSettingsOperationType,
    UpdateWorkspaceInvitationType,
    UpdateWorkspaceOperationType,
    UpdateWorkspaceUserOperationType,
)
from .registries import (
    ImportExportConfig,
    application_type_registry,
    object_scope_type_registry,
    operation_type_registry,
    permission_manager_type_registry,
)
from .signals import (
    application_created,
    application_deleted,
    application_imported,
    application_updated,
    applications_reordered,
    before_workspace_deleted,
    before_workspace_user_deleted,
    before_workspace_user_updated,
    workspace_created,
    workspace_deleted,
    workspace_invitation_accepted,
    workspace_invitation_rejected,
    workspace_invitation_updated_or_created,
    workspace_updated,
    workspace_user_added,
    workspace_user_deleted,
    workspace_user_updated,
    workspaces_reordered,
)
from .storage import get_default_storage
from .telemetry.utils import baserow_trace_methods, disable_instrumentation
from .trash.handler import TrashHandler
from .types import (
    Actor,
    ContextObject,
    Email,
    PermissionCheck,
    PermissionObjectResult,
    UserEmailMapping,
)
from .utils import (
    ChildProgressBuilder,
    atomic_if_not_already,
    extract_allowed,
    find_unused_name,
    set_allowed_attrs,
)

User = get_user_model()

WorkspaceForUpdate = NewType("WorkspaceForUpdate", Workspace)

tracer = trace.get_tracer(__name__)


@dataclass
class ApplicationUpdatedResult:
    updated_application_instance: Application
    original_app_allowed_values: Dict[str, Any]
    updated_app_allowed_values: Dict[str, Any]


class CoreHandler(metaclass=baserow_trace_methods(tracer)):
    default_create_allowed_fields = ["name", "init_with_data"]
    default_update_allowed_fields = ["name"]

    def clear_context(self):
        """
        Clears the context of the current request. This is useful when the CoreHandler
        needs to set a context for a specific request, but it should be cleared after
        the request is done.
        """

        clear_current_workspace_id()

    def get_settings(self):
        """
        Returns a settings model instance containing all the admin configured settings.

        :return: The settings instance.
        :rtype: Settings
        """

        try:
            return Settings.objects.all().select_related("co_branding_logo")[:1].get()
        except Settings.DoesNotExist:
            return Settings.objects.create()

    def update_settings(self, user, settings_instance=None, **kwargs):
        """
        Updates one or more setting values if the user has staff permissions.

        :param user: The user on whose behalf the settings are updated.
        :type user: User
        :param settings_instance: If already fetched, the settings instance can be
            provided to avoid fetching the values for a second time.
        :type settings_instance: Settings
        :param kwargs: An dict containing the settings that need to be updated.
        :type kwargs: dict
        :return: The update settings instance.
        :rtype: Settings
        """

        CoreHandler().check_permissions(
            user, UpdateSettingsOperationType.type, context=settings_instance
        )

        if not settings_instance:
            settings_instance = self.get_settings()

        settings_instance = set_allowed_attrs(
            kwargs,
            [
                "allow_new_signups",
                "allow_signups_via_workspace_invitations",
                "allow_reset_password",
                "allow_global_workspace_creation",
                "account_deletion_grace_delay",
                "track_workspace_usage",
                "show_baserow_help_request",
                "co_branding_logo",
                "email_verification",
                "verify_import_signature",
            ],
            settings_instance,
        )

        settings_instance.save()
        return settings_instance

    def check_multiple_permissions(
        self,
        checks: List[PermissionCheck],
        workspace: Optional[Workspace] = None,
        include_trash: bool = False,
        return_permissions_exceptions: bool = False,
    ) -> Dict[PermissionCheck, Union[bool, PermissionException]]:
        """
        Given a list of permission to check, returns True for each check for which the
        triplet (actor, permission_name, scope) is allowed.

        When we check the permissions, all permission managers listed in
        `settings.PERMISSION_MANAGERS` are called successively to determine the policy
        for each given check.

        For each check, each permission manager can answer with `True` if the operation
        is permitted, False operation is disallowed and return `None` if it can't take
        a definitive answer.

        If None of the permission managers replied with a final answer for a check,
        the operation is denied by default for this check.

        :param checks: The list of checks to do. Each check is a triplet of
            (actor, permission_name, scope).
        :param workspace: The optional workspace in which the operations take place.
        :param include_trash: If true, then also checks if the given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :param return_permissions_exceptions: Raise an exception when the permission is
            disallowed when `True`. Return `False` instead when `False`.
            `False` by default.
        :return: A dictionary with one entry for each check of the parameter as key and
            whether the operation is allowed or not as value.
        """

        result = {}
        undetermined_checks = set(checks)

        for permission_manager_name in settings.PERMISSION_MANAGERS:
            if not undetermined_checks:
                break

            permission_manager_type = permission_manager_type_registry.get(
                permission_manager_name
            )
            supported_checks = [
                c
                for c in undetermined_checks
                if permission_manager_type.actor_is_supported(c.actor)
            ]

            manager_result = permission_manager_type.check_multiple_permissions(
                supported_checks,
                workspace=workspace,
                include_trash=include_trash,
            )

            for check, check_result in manager_result.items():
                if check_result is not None:
                    if (
                        isinstance(check_result, PermissionException)
                        and not return_permissions_exceptions
                    ):
                        result[check] = False
                    else:
                        result[check] = check_result

                    undetermined_checks.remove(check)

        # Permission denied by default to all non handled check
        for undetermined_check in undetermined_checks:
            result[undetermined_check] = (
                PermissionDenied(undetermined_check.actor)
                if return_permissions_exceptions
                else False
            )

        return result

    def check_permission_for_multiple_actors(
        self,
        actors: List[Actor],
        operation_name: str,
        workspace: Optional[Workspace] = None,
        context: Optional[ContextObject] = None,
        include_trash: bool = False,
    ) -> List[Actor]:
        """
        Helper method for a common use case with multiple permission checking when you
        want to check the same permission for multiple users at once.

        :param actor: The actor who wants to execute the operation. Generally a `User`,
            but can be a `Token`.
        :param operation_name: The operation name the actor wants to execute.
        :param workspace: The optional workspace in which  the operation takes place.
        :param context: The optional object affected by the operation. For instance
            if you are updating a `Table` object, the context is this `Table` object.
        :param include_trash: If true then also checks if the given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :return: The list of allowed actors.
        """

        checks = [PermissionCheck(actor, operation_name, context) for actor in actors]
        checked = self.check_multiple_permissions(
            checks, workspace, include_trash=include_trash
        )

        return [actor for (actor, _, _), result in checked.items() if result is True]

    def check_permissions(
        self,
        actor: Actor,
        operation_name: str,
        workspace: Optional[Workspace] = None,
        context: Optional[ContextObject] = None,
        include_trash: bool = False,
        raise_permission_exceptions: bool = True,
    ) -> bool:
        """
        Checks whether a specific Actor has the Permission to execute an Operation
        on the given Context.

        When we check a permission, all permission managers listed in
        `settings.PERMISSION_MANAGERS` are called successively until one
        gives a final answer (permitted or disallowed).

        Each permission manager can answer with `True` if the operation is permitted,
        raise a PermissionDenied subclass exception if the operation is disallowed and
        return `None` if it can't take a definitive answer.

        If None of the permission manager replied with a final answer, the operation is
        denied by default.

        :param actor: The actor who wants to execute the operation. Generally a `User`,
            but can be a `Token`.
        :param operation_name: The operation name the actor wants to execute.
        :param workspace: The optional workspace in which  the operation takes place.
        :param context: The optional object affected by the operation. For instance
            if you are updating a `Table` object, the context is this `Table` object.
        :param include_trash: If true then also checks if the given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :param raise_permission_exceptions: Raise an exception when the permission is
            disallowed when `True`. Return `False` instead when `False`.
            `True` by default.
        :raise PermissionException: If the operation is disallowed.
        :return: `True` if the operation is permitted or `False` if the operation is
            disallowed AND raise_permission_exceptions is `False`.
        """

        if settings.DEBUG or settings.TESTS:
            self._ensure_context_matches_operation(context, operation_name)

        check = PermissionCheck(actor, operation_name, context)

        allowed = self.check_multiple_permissions(
            [check],
            workspace,
            include_trash=include_trash,
            return_permissions_exceptions=True,
        ).get(check, None)

        if allowed is True:
            # FIXME: Temporarily setting the current workspace ID for URL generation in
            # storage backends, enabling permission checks at download time.
            if workspace:
                set_current_workspace_id(workspace.id)
            return True

        if isinstance(allowed, PermissionException):
            if raise_permission_exceptions:
                raise allowed
            else:
                return False

        # If we get there, the result of the check is probably None so it should be
        # denied.
        if raise_permission_exceptions:
            raise PermissionDenied(actor=actor)
        else:
            return False

    def _ensure_context_matches_operation(self, context, operation_name):
        context_types = {
            t.type
            for t in object_scope_type_registry.get_all_by_model_isinstance(context)
        }
        expected_operation_context_type = operation_type_registry.get(
            operation_name
        ).context_scope_name
        if expected_operation_context_type not in context_types:
            raise InvalidPermissionContext(
                f"Incorrect context object {context} matching {context_types} provided "
                "to check_permissions call. Was expected instead one of type "
                f"{expected_operation_context_type} based on the operation type of "
                f"{operation_name}."
            )

    def get_permissions(
        self, actor: Actor, workspace: Optional[Workspace] = None
    ) -> List[PermissionObjectResult]:
        """
        Generates the object sent to a client to easily check the actor permissions over
        the given workspace.

        This object is generated by going over all permission managers listed in
        `settings.PERMISSION_MANAGERS` and aggregating the results in a list of dict
        containing permission manager type name and the value returned from the
        permission manager. For example:

        ```python
        [
            {
                "name": "core",
                "permissions": ["perm1", "perm2"]
            },
            {
                "name": "staff"
                "permissions": {
                    "staff_only_permissions": ["perm3", "perm4"],
                    "is_staff": True
                }
            },
            ...
        ]
        ```

        If the permission manager return value is None, it's ignored and not included
        in the final result. This permission will therefore not be checked on the
        frontend side at all.

        :param actor: The actor whom we want to compute the permission object for.
        :param workspace: The optional workspace into which we want to compute the
            permission object.
        :return: The full permission object.
        """

        result = []
        for permission_manager_name in settings.PERMISSION_MANAGERS:
            permission_manager_type = permission_manager_type_registry.get(
                permission_manager_name
            )

            perms = permission_manager_type.get_permissions_object(
                actor, workspace=workspace
            )
            if perms is not None:
                result.append(
                    PermissionObjectResult(
                        name=permission_manager_name, permissions=perms
                    )
                )

        return result

    def filter_queryset(
        self,
        actor: Actor,
        operation_name: str,
        queryset: QuerySet,
        workspace: Optional[Workspace] = None,
    ) -> QuerySet:
        """
        filters a given queryset accordingly to the actor permissions in the specified
        context.

        All permission managers listed in `settings.PERMISSION_MANAGERS` are called
        to let them the opportunity to filter the queryset if it's relevant for them.

        :param actor: The actor whom we want to filter the queryset for.
        :param operation_name: The list operation name we want the queryset to be
            filtered for.
        :param queryset: The queryset we want to filter. The queryset should contains
            object that are in the same `ObjectScopeType` as the one described in the
            `OperationType` corresponding to the given `operation_name`.
        :param workspace: An optional workspace into which the operation occurs.
        :return: The queryset, potentially filtered.
        """

        if actor is None:
            actor = AnonymousUser

        for permission_manager_name in settings.PERMISSION_MANAGERS:
            permission_manager_type = permission_manager_type_registry.get(
                permission_manager_name
            )
            if not permission_manager_type.actor_is_supported(actor):
                continue

            filtered_queryset = permission_manager_type.filter_queryset(
                actor, operation_name, queryset, workspace=workspace
            )

            if filtered_queryset is None:
                continue

            # a permission can return a tuple in which case the second value
            # indicate whether it should be the last permission manager to be applied.
            # If True, then no other permission manager are applied and the queryset
            # is returned.
            if isinstance(filtered_queryset, tuple):
                queryset, stop = filtered_queryset
                if stop:
                    break
            else:
                queryset = filtered_queryset

        return queryset

    def get_workspace_for_update(self, workspace_id: int) -> WorkspaceForUpdate:
        return cast(
            WorkspaceForUpdate,
            self.get_workspace(
                workspace_id,
                base_queryset=Workspace.objects.select_for_update(of=("self",)),
            ),
        )

    def list_user_workspaces(
        self, user: AbstractUser, base_queryset: QuerySet[Workspace] = None
    ) -> QuerySet[Workspace]:
        """
        Returns a queryset of all workspaces the user is in.

        :param user: The user for which to get the workspaces.
        :param base_queryset: The base queryset from where to select the workspaces
            object. This can for example be used to do a `prefetch_related`.
        :return: A queryset of all workspaces the user is in.
        """

        workspace_qs = self.get_enhanced_workspace_queryset(base_queryset)
        return workspace_qs.filter(workspaceuser__user=user)

    def get_enhanced_workspace_queryset(
        self, queryset: QuerySet[Workspace] | None = None
    ) -> QuerySet[Workspace]:
        """
        Enhances the workspace queryset with additional prefetches and filters based on
        the plugins registered in the plugin registry.

        :param queryset: The Workspace queryset to enhance.
        :return: The enhanced queryset.
        """

        if queryset is None:
            queryset = Workspace.objects.all()

        queryset = queryset.prefetch_related("workspaceuser_set", "template_set")

        for plugin in plugin_registry.registry.values():
            queryset = plugin.enhance_workspace_queryset(queryset)
        return queryset

    def get_workspace(
        self, workspace_id: int, base_queryset: QuerySet = None
    ) -> Workspace:
        """
        Selects a workspace with a given id from the database.

        :param workspace_id: The identifier of the workspace that must be returned.
        :param base_queryset: The base queryset from where to select the workspace
            object. This can for example be used to do a `prefetch_related`.
        :raises WorkspaceDoesNotExist: When the workspace with the
            provided id does not exist.
        :return: The requested workspace instance of the provided id.
        """

        workspace_qs = self.get_enhanced_workspace_queryset(base_queryset)

        try:
            workspace = workspace_qs.get(id=workspace_id)
        except Workspace.DoesNotExist:
            raise WorkspaceDoesNotExist(
                f"The workspace with id {workspace_id} does not exist."
            )

        return workspace

    def get_workspaceuser_workspace_queryset(self) -> QuerySet[WorkspaceUser]:
        """
        Returns WorkspaceUser queryset that will prefetch workspaces and their users.
        """

        workspaceusers_with_user_and_profile = WorkspaceUser.objects.select_related(
            "user"
        ).select_related("user__profile")
        workspaceuser_workspaces = WorkspaceUser.objects.select_related(
            "workspace"
        ).prefetch_related(
            Prefetch(
                "workspace__workspaceuser_set",
                queryset=workspaceusers_with_user_and_profile,
            )
        )
        return workspaceuser_workspaces

    def create_workspace(self, user: User, name: str) -> WorkspaceUser:
        """
        Creates a new workspace for an existing user.

        :param user: The user that must be in the workspace.
        :param name: The name of the workspace.
        :return: The newly created WorkspaceUser object
        """

        CoreHandler().check_permissions(user, CreateWorkspaceOperationType.type)

        workspace = Workspace.objects.create(name=name)

        last_order = WorkspaceUser.get_last_order(user)
        workspace_user = WorkspaceUser.objects.create(
            workspace=workspace,
            user=user,
            order=last_order,
            permissions=WORKSPACE_USER_PERMISSION_ADMIN,
        )

        workspace_created.send(self, workspace=workspace, user=user)

        return workspace_user

    def update_workspace(
        self,
        user: AbstractUser,
        workspace: WorkspaceForUpdate,
        name: Optional[str] = None,
        generative_ai_models_settings: Optional[Dict[str, Any]] = None,
    ) -> Workspace:
        """
        Updates the values of a workspace if the user has admin
        permissions to the workspace.

        :param user: The user on whose behalf the change is made.
        :param workspace: The workspace instance that must be updated.
        :param name: The new name to give the workspace.
        :raises ValueError: If one of the provided parameters is invalid.
        :return: The updated workspace
        """

        if not isinstance(workspace, Workspace):
            raise ValueError("The workspace is not an instance of Workspace.")
        elif name is None and generative_ai_models_settings is None:
            raise ValueError("Nothing to update.")

        CoreHandler().check_permissions(
            user,
            UpdateWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        updated_fields = []
        if name is not None:
            workspace.name = name
            updated_fields.append("name")
        if generative_ai_models_settings is not None:
            workspace.generative_ai_models_settings = generative_ai_models_settings
            updated_fields.append("generative_ai_models_settings")

        workspace.save(update_fields=updated_fields)
        workspace_updated.send(self, workspace=workspace, user=user)

        return workspace

    def leave_workspace(self, user, workspace):
        """
        Called when a user of workspace wants to leave a workspace.

        :param user: The user that wants to leave the workspace.
        :type user: User
        :param workspace: The workspace that the user wants to leave.
        :type workspace: Workspace
        """

        if not isinstance(workspace, Workspace):
            raise ValueError("The workspace is not an instance of Workspace.")

        try:
            workspace_user = WorkspaceUser.objects.get(user=user, workspace=workspace)
        except WorkspaceUser.DoesNotExist:
            raise UserNotInWorkspace(user, self)

        # If the current user is an admin and they are the last admin left, they are not
        # allowed to leave the workspace otherwise no one will have control over it.
        # They need to give someone else admin permissions first or they must
        # leave the workspace.
        if (
            workspace_user.permissions == WORKSPACE_USER_PERMISSION_ADMIN
            and WorkspaceUser.objects.filter(
                workspace=workspace, permissions=WORKSPACE_USER_PERMISSION_ADMIN
            )
            .exclude(user__profile__to_be_deleted=True)
            .count()
            == 1
        ):
            raise WorkspaceUserIsLastAdmin(
                "The user is the last admin left in the workspace and "
                "can therefore not leave it."
            )

        before_workspace_user_deleted.send(
            self, user=user, workspace=workspace, workspace_user=workspace_user
        )

        # If the user is not the last admin, we can safely delete the user from the
        # workspace.
        workspace_user_id = workspace_user.id
        workspace_user.delete()
        workspace_user_deleted.send(
            self,
            workspace_user_id=workspace_user_id,
            workspace_user=workspace_user,
            user=user,
        )

    def delete_workspace_by_id(self, user: AbstractUser, workspace_id: int):
        """
        Deletes a workspace by id and it's related applications instead of using an
        instance. Only if the user has admin permissions for the workspace.

        :param user: The user on whose behalf the delete is done.
        :param workspace_id: The workspace id that must be deleted.
        :raises ValueError: If one of the provided parameters is invalid.
        """

        locked_workspace = self.get_workspace_for_update(workspace_id)
        self.delete_workspace(user, locked_workspace)

    def delete_workspace(self, user: AbstractUser, workspace: WorkspaceForUpdate):
        """
        Deletes an existing workspace and related applications if the user has admin
        permissions for the workspace. The workspace can be restored after deletion
        using the trash handler.

        :param user: The user on whose behalf the delete is done.
        :type: user: User
        :param workspace: The workspace instance that must be deleted.
        :type: workspace: Workspace
        :raises ValueError: If one of the provided parameters is invalid.
        """

        if not isinstance(workspace, Workspace):
            raise ValueError("The workspace is not an instance of Workspace.")

        CoreHandler().check_permissions(
            user,
            DeleteWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        # Load the workspace users before the workspace is deleted so that we can
        # pass those along with the signal.
        workspace_id = workspace.id
        workspace_users = list(workspace.users.all())

        before_workspace_deleted.send(
            self,
            workspace_id=workspace_id,
            workspace=workspace,
            workspace_users=workspace_users,
            user=user,
        )

        TrashHandler.trash(user, workspace, None, workspace)

        workspace_deleted.send(
            self,
            workspace_id=workspace_id,
            workspace=workspace,
            workspace_users=workspace_users,
            user=user,
        )

    def order_workspaces(self, user: AbstractUser, workspace_ids: List[int]):
        """
        Changes the order of workspaces for a user.

        :param user: The user on whose behalf the ordering is done.
        :param workspace_ids: A list of workspace ids ordered the way they
            need to be ordered.
        """

        for index, workspace_id in enumerate(workspace_ids):
            WorkspaceUser.objects.filter(user=user, workspace_id=workspace_id).update(
                order=index + 1
            )
        workspaces_reordered.send(self, user=user, workspace_ids=workspace_ids)

    def get_workspaces_order(self, user: AbstractUser) -> List[int]:
        """
        Returns the order of workspaces for a user.

        :param user: The user on whose behalf the ordering is done.
        :return: A list of workspace ids ordered the way they need to be ordered.
        """

        return [
            workspace_user.workspace_id
            for workspace_user in WorkspaceUser.objects.filter(user=user).order_by(
                "order"
            )
        ]

    def get_workspace_user(self, workspace_user_id, base_queryset=None):
        """
        Fetches a workspace user object related to the provided id from the database.

        :param workspace_user_id: The identifier of the workspace user that
            must be returned.
        :type workspace_user_id: int
        :param base_queryset: The base queryset from where to select the workspace user
            object. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises WorkspaceDoesNotExist: When the workspace with the provided
            id does not exist.
        :return: The requested workspace user instance of the provided workspace_id.
        :rtype: WorkspaceUser
        """

        if base_queryset is None:
            base_queryset = WorkspaceUser.objects

        try:
            workspace_user = base_queryset.select_related("workspace").get(
                id=workspace_user_id
            )
        except WorkspaceUser.DoesNotExist:
            raise WorkspaceUserDoesNotExist(
                f"The workspace user with id {workspace_user_id} does " f"not exist."
            )

        return workspace_user

    def get_workspace_users(
        self, workspace: Workspace, users: List[User], include_trash: bool = False
    ) -> QuerySet:
        """
        Returns a queryset to get all WorkspaceUser for the given
        workspace for all users.

        :param workspace: The workspace the WorkspaceUser must belong to.
        :param users: The user list we want the WorkspaceUsers for.
        :param include_trash: Whether or not we want to include trashed Workspace
            in the result.
        """

        workspace_user_queryset = (
            WorkspaceUser.objects_and_trash if include_trash else WorkspaceUser.objects
        )
        return workspace_user_queryset.filter(user__in=users, workspace=workspace)

    def get_users_in_workspace(self, workspace: Workspace) -> list[User]:
        wk_users = WorkspaceUser.objects.filter(workspace=workspace).select_related(
            "user"
        )
        return [wk_user.user for wk_user in wk_users]

    def update_workspace_user(
        self,
        user: AbstractUser,
        workspace_user: WorkspaceUser,
        **kwargs,
    ) -> WorkspaceUser:
        """
        Updates the values of an existing workspace user.

        :param user: The user on whose behalf the workspace user is deleted.
        :param workspace_user: The workspace user that must be updated.
        :return: The updated workspace user instance.
        """

        if not isinstance(workspace_user, WorkspaceUser):
            raise ValueError("The workspace user is not an instance of WorkspaceUser.")

        CoreHandler().check_permissions(
            user,
            UpdateWorkspaceUserOperationType.type,
            workspace=workspace_user.workspace,
            context=workspace_user,
        )

        return self.force_update_workspace_user(user, workspace_user, **kwargs)

    def force_update_workspace_user(
        self, user: Optional[AbstractUser], workspace_user: WorkspaceUser, **kwargs
    ) -> WorkspaceUser:
        """
        Forcibly updates the workspace users attributes without checking permissions
        whilst sending all the appropriate signals that an update has been done.
        """

        with atomic_if_not_already():
            if kwargs["permissions"] != "ADMIN":
                CoreHandler.raise_if_user_is_last_admin_of_workspace(workspace_user)

            before_workspace_user_updated.send(
                self, workspace_user=workspace_user, **kwargs
            )
            permissions_before = workspace_user.permissions
            workspace_user = set_allowed_attrs(kwargs, ["permissions"], workspace_user)
            workspace_user.save()
            workspace_user_updated.send(
                self,
                workspace_user=workspace_user,
                user=user,
                permissions_before=permissions_before,
            )
            return workspace_user

    def delete_workspace_user(self, user, workspace_user):
        """
        Deletes the provided workspace user.

        :param user: The user on whose behalf the workspace user is deleted.
        :type user: User
        :param workspace_user: The workspace user that must be deleted.
        :type workspace_user: WorkspaceUser
        :raises CannotDeleteYourselfFromWorkspace; If the user tries to delete himself
            from the workspace.
        """

        if not isinstance(workspace_user, WorkspaceUser):
            raise ValueError("The workspace user is not an instance of WorkspaceUser.")

        CoreHandler().check_permissions(
            user,
            DeleteWorkspaceUserOperationType.type,
            workspace=workspace_user.workspace,
            context=workspace_user,
        )

        if user.id == workspace_user.user_id:
            raise CannotDeleteYourselfFromWorkspace(
                "Cannot delete yourself from workspace."
            )

        before_workspace_user_deleted.send(
            self,
            user=workspace_user.user,
            workspace=workspace_user.workspace,
            workspace_user=workspace_user,
        )

        workspace_user_id = workspace_user.id
        workspace_user.delete()

        workspace_user_deleted.send(
            self,
            workspace_user_id=workspace_user_id,
            workspace_user=workspace_user,
            user=user,
        )

    def get_workspace_invitation_signer(self):
        """
        Returns the workspace invitation signer. This is for example used to create
        a url safe signed version of the invitation id which is used when sending a
        public accept link to the user.

        :return: The itsdangerous serializer.
        :rtype: URLSafeSerializer
        """

        return URLSafeSerializer(settings.SECRET_KEY, "workspace-invite")

    def send_workspace_invitation_email(self, invitation, base_url):
        """
        Sends out a workspace invitation email to the user based on the provided
        invitation instance.

        :param invitation: The invitation instance for which the email must be send.
        :type invitation: WorkspaceInvitation
        :param base_url: The base url of the frontend, where the user can accept his
            invitation. The signed invitation id is appended to the URL (base_url +
            '/TOKEN'). Only the PUBLIC_WEB_FRONTEND_HOSTNAME is allowed as domain name.
        :type base_url: str
        :raises BaseURLHostnameNotAllowed: When the host name of the base_url is not
            allowed.
        """

        parsed_base_url = urlparse(base_url)
        if parsed_base_url.hostname not in (
            settings.PUBLIC_WEB_FRONTEND_HOSTNAME,
            settings.BASEROW_EMBEDDED_SHARE_HOSTNAME,
        ):
            raise BaseURLHostnameNotAllowed(
                f"The hostname {parsed_base_url.netloc} is not allowed."
            )

        signer = self.get_workspace_invitation_signer()
        signed_invitation_id = signer.dumps(invitation.id)

        if not base_url.endswith("/"):
            base_url += "/"

        public_accept_url = urljoin(base_url, signed_invitation_id)

        # Send the email in the language of the user that has send the invitation.
        with translation.override(invitation.invited_by.profile.language):
            email = WorkspaceInvitationEmail(
                invitation, public_accept_url, to=[invitation.email]
            )
            email.send()

    def get_workspace_invitation_by_token(self, token, base_queryset=None):
        """
        Returns the workspace invitation instance if a valid signed token of the id is
        provided. It can be signed using the signer returned by the
        `get_workspace_invitation_signer` method.

        :param token: The signed invitation id of related to the workspace invitation
            that must be fetched. Must be signed using the signer returned by the
            `get_workspace_invitation_signer`.
        :type token: str
        :param base_queryset: The base queryset from where to select the invitation.
            This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises BadSignature: When the provided token has a bad signature.
        :raises WorkspaceInvitationDoesNotExist: If the invitation does not exist.
        :return: The requested workspace invitation instance related to the
            provided token.
        :rtype: WorkspaceInvitation
        """

        signer = self.get_workspace_invitation_signer()
        workspace_invitation_id = signer.loads(token)

        if base_queryset is None:
            base_queryset = WorkspaceInvitation.objects

        try:
            workspace_invitation = base_queryset.select_related(
                "workspace", "invited_by"
            ).get(id=workspace_invitation_id)
        except WorkspaceInvitation.DoesNotExist:
            raise WorkspaceInvitationDoesNotExist(
                f"The workspace invitation with id {workspace_invitation_id} "
                "does not exist."
            )

        return workspace_invitation

    def get_workspace_invitation(self, workspace_invitation_id, base_queryset=None):
        """
        Selects a workspace invitation with a given id from the database.

        :param workspace_invitation_id: The identifier of the invitation that must be
            returned.
        :type workspace_invitation_id: int
        :param base_queryset: The base queryset from where to select the invitation.
            This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises WorkspaceInvitationDoesNotExist: If the invitation does not exist.
        :return: The requested field instance of the provided id.
        :rtype: WorkspaceInvitation
        """

        if base_queryset is None:
            base_queryset = WorkspaceInvitation.objects

        try:
            workspace_invitation = base_queryset.select_related(
                "workspace", "invited_by"
            ).get(id=workspace_invitation_id)
        except WorkspaceInvitation.DoesNotExist:
            raise WorkspaceInvitationDoesNotExist(
                f"The workspace invitation with id {workspace_invitation_id} "
                "does not exist."
            )

        return workspace_invitation

    def create_workspace_invitation(
        self, user, workspace, email, permissions, base_url, message=""
    ):
        """
        Creates a new workspace invitation for the given email address and sends out an
        email containing the invitation.

        :param user: The user on whose behalf the invitation is created.
        :type user: User
        :param workspace: The workspace for which the user is invited.
        :type workspace: Workspace
        :param email: The email address of the person that is invited to the workspace.
            Can be an existing or not existing user.
        :type email: str
        :param permissions: The workspace permissions that the user will get once they
            have accepted the invitation.
        :type permissions: str
        :param base_url: The base url of the frontend, where the user can accept his
            invitation. The signed invitation id is appended to the URL (base_url +
            '/TOKEN'). Only the PUBLIC_WEB_FRONTEND_HOSTNAME is allowed as domain name.
        :type base_url: str
        :param message: A custom message that will be included in the invitation email.
        :type message: Optional[str]
        :raises ValueError: If the provided permissions are not allowed.
        :raises UserInvalidWorkspacePermissionsError: If the user does not belong to the
            workspace or doesn't have right permissions in the workspace.
        :raises MaxNumberOfPendingWorkspaceInvitesReached: When the maximum number of
            pending invites have been reached.
        :return: The created workspace invitation.
        :rtype: WorkspaceInvitation
        """

        CoreHandler().check_permissions(
            user,
            CreateInvitationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        email = normalize_email_address(email)

        if WorkspaceUser.objects.filter(
            workspace=workspace, user__email=email
        ).exists():
            raise WorkspaceUserAlreadyExists(
                f"The user {email} is already part of the workspace."
            )

        max_invites = settings.BASEROW_MAX_PENDING_WORKSPACE_INVITES
        if max_invites > 0 and (
            WorkspaceInvitation.objects.filter(workspace=workspace)
            .exclude(email=email)
            .count()
            >= max_invites
        ):
            raise MaxNumberOfPendingWorkspaceInvitesReached(
                f"The maximum number of pending workspaces invites {max_invites} has "
                f"been reached."
            )

        invitation, created = WorkspaceInvitation.objects.update_or_create(
            workspace=workspace,
            email=email,
            defaults={
                "message": message,
                "permissions": permissions,
                "invited_by": user,
            },
        )

        try:
            invited_user = User.objects.select_related("profile").get(
                email=invitation.email
            )
        except User.DoesNotExist:
            invited_user = None

        workspace_invitation_updated_or_created.send(
            sender=self,
            invitation=invitation,
            invited_user=invited_user,
            created=created,
        )

        self.send_workspace_invitation_email(invitation, base_url)

        return invitation

    def update_workspace_invitation(self, user, invitation, permissions):
        """
        Updates the permissions of an existing invitation if the user has ADMIN
        permissions to the related workspace.

        :param user: The user on whose behalf the invitation is updated.
        :type user: User
        :param invitation: The invitation that must be updated.
        :type invitation: WorkspaceInvitation
        :param permissions: The new permissions of the invitation that the user must
            has after accepting.
        :type permissions: str
        :raises ValueError: If the provided permissions is not allowed.
        :raises UserInvalidWorkspacePermissionsError: If the user does not belong to the
            workspace or doesn't have right permissions in the workspace.
        :return: The updated workspace permissions instance.
        :rtype: WorkspaceInvitation
        """

        CoreHandler().check_permissions(
            user,
            UpdateWorkspaceInvitationType.type,
            workspace=invitation.workspace,
            context=invitation,
        )

        invitation.permissions = permissions
        invitation.save()

        return invitation

    def delete_workspace_invitation(self, user, invitation):
        """
        Deletes an existing workspace invitation if the user has ADMIN permissions to
        the related workspace.

        :param user: The user on whose behalf the invitation is deleted.
        :type user: User
        :param invitation: The invitation that must be deleted.
        :type invitation: WorkspaceInvitation
        :raises UserInvalidWorkspacePermissionsError: If the user does not belong to the
            workspace or doesn't have right permissions in the workspace.
        """

        CoreHandler().check_permissions(
            user,
            DeleteWorkspaceInvitationOperationType.type,
            workspace=invitation.workspace,
            context=invitation,
        )

        invitation.delete()

    def reject_workspace_invitation(self, user, invitation):
        """
        Rejects a workspace invitation by deleting the invitation so that can't be
        reused again. It can only be rejected if the invitation was addressed to the
        email address of the user.

        :param user: The user who wants to reject the invitation.
        :type user: User
        :param invitation: The invitation that must be rejected.
        :type invitation: WorkspaceInvitation
        :raises WorkspaceInvitationEmailMismatch: If the invitation email does not match
            the one of the user.
        """

        if user.username != invitation.email:
            raise WorkspaceInvitationEmailMismatch(
                "The email address of the invitation does not match the one of the "
                "user."
            )

        workspace_invitation_rejected.send(
            sender=self, invitation=invitation, user=user
        )

        invitation.delete()

    def add_user_to_workspace(
        self,
        workspace: Workspace,
        user: AbstractUser,
        permissions: str = WORKSPACE_USER_PERMISSION_MEMBER,
    ) -> WorkspaceUser:
        """
        Adds a user to the workspace by creating the appropriate `WorkspaceUser`.
        If the user is already in the workspace, the permissions field is updated.

        :param workspace: the workspace in which we want to add the user.
        :param user: the user we want to add.
        :param permissions: the permissions of the user in this workspace. 'member' by
            default if not specified.
        :return: The created `WorkspaceUser` object.
        """

        workspace_user, _ = WorkspaceUser.objects.update_or_create(
            user=user,
            workspace=workspace,
            defaults={
                "order": WorkspaceUser.get_last_order(user),
                "permissions": permissions,
            },
        )

        workspace_user_added.send(
            self,
            workspace_user_id=workspace_user.id,
            workspace_user=workspace_user,
            user=user,
        )

        return workspace_user

    def accept_workspace_invitation(
        self, user: User, invitation: WorkspaceInvitation
    ) -> WorkspaceUser:
        """
        Accepts a workspace invitation by adding the user to the correct workspace with
        the right permissions. It can only be accepted if the invitation was
        addressed to the email address of the user. Because the invitation has been
        accepted it can then be deleted. If the user is already a member of the
        workspace then the permissions are updated.

        :param user: The user who has accepted the invitation.
        :param invitation: The invitation that must be accepted.
        :raises WorkspaceInvitationEmailMismatch: If the invitation email does not match
            the one of the user.
        :return: The workspace user relationship related to the invite.
        """

        if user.username != invitation.email:
            raise WorkspaceInvitationEmailMismatch(
                "The email address of the invitation does not match the one of the "
                "user."
            )

        workspace_user = self.add_user_to_workspace(
            invitation.workspace, user, permissions=invitation.permissions
        )

        workspace_invitation_accepted.send(
            sender=self, invitation=invitation, user=user
        )
        invitation.delete()

        return workspace_user

    @classmethod
    def get_user_email_mapping(
        cls, workspace_id: int, only_emails: list[Email]
    ) -> UserEmailMapping:
        workspace_users = WorkspaceUser.objects.filter(
            workspace_id=workspace_id
        ).select_related("user")

        if only_emails:
            workspace_users = workspace_users.filter(user__email__in=only_emails)

        return {
            workspace_user.user.email: workspace_user.user
            for workspace_user in workspace_users
        }

    def get_application(
        self,
        application_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> Application:
        """
        Selects an application with a given id from the database.

        :param application_id: The identifier of the application that must be returned.
        :param base_queryset: The base queryset from where to select the application
            object. This can for example be used to do a `select_related`.
        :raises ApplicationDoesNotExist: When the application with the provided id
            does not exist.
        :return: The requested application instance of the provided id.
        """

        if base_queryset is None:
            base_queryset = Application.objects

        try:
            application = (
                base_queryset.select_related("workspace")
                .exclude(workspace__trashed=True)
                .get(id=application_id)
            )
        except Application.DoesNotExist as e:
            raise ApplicationDoesNotExist(
                f"The application with id {application_id} does not exist."
            ) from e

        return application

    def get_application_for_url(self, url) -> Application | None:
        """
        Returns the application instance related to the given URL if any.

        :param url: the url to search the application for.
        """

        for app_type in application_type_registry.get_all():
            if found_id := app_type.get_application_id_for_url(url):
                return self.get_application(found_id)

        return None

    def list_applications_in_workspace(
        self,
        workspace: Workspace,
        base_queryset: Optional[QuerySet] = None,
    ) -> QuerySet[Application]:
        """
        Return a list of applications in a workspace.

        :param workspace_id: The workspace to list the applications from.
        :param base_queryset: The base queryset from where to select the application
        :return: A list of applications in the workspace.
        """

        if base_queryset is None:
            base_queryset = Application.objects

        return (
            base_queryset.filter(workspace=workspace, workspace__trashed=False)
            .select_related("workspace")
            .order_by("order", "id")
        )

    def filter_specific_applications(
        self,
        queryset: QuerySet[Application],
        per_content_type_queryset_hook: Optional[
            Callable[[Model, QuerySet], QuerySet]
        ] = None,
    ) -> QuerySet[Application]:
        if per_content_type_queryset_hook is None:
            per_content_type_queryset_hook = (
                lambda model, qs: application_type_registry.get_by_model(
                    model
                ).enhance_queryset(qs)
            )
        return specific_queryset(queryset, per_content_type_queryset_hook)

    def create_application(
        self,
        user: AbstractUser,
        workspace: Workspace,
        type_name: str,
        init_with_data: bool = False,
        **kwargs,
    ) -> Application:
        """
        Creates a new application based on the provided type.

        :param user: The user on whose behalf the application is created.
        :param workspace: The workspace that the application instance belongs to.
        :param type_name: The type name of the application. ApplicationType can be
            registered via the ApplicationTypeRegistry.
        :param init_with_data: Whether the application should be initialized with
            some default data. Defaults to False.
        :param kwargs: Additional parameters to pass to the application creation.
        :return: The created application instance.
        """

        CoreHandler().check_permissions(
            user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        application_type = application_type_registry.get(type_name)
        allowed_values = extract_allowed(
            kwargs, self.default_create_allowed_fields + application_type.allowed_fields
        )
        prepared_values = application_type.prepare_value_for_db(allowed_values)

        application = application_type.create_application(
            user, workspace, init_with_data=init_with_data, **prepared_values
        )

        application_type.after_create(application, kwargs)

        application_created.send(self, application=application, user=user)
        return application

    def find_unused_application_name(
        self, workspace_id: int, proposed_name: str
    ) -> str:
        """
        Finds an unused name for an application.

        :param workspace_id: The workspace id that the application belongs to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        existing_applications_names = Application.objects.filter(
            workspace_id=workspace_id, workspace__trashed=False
        ).values_list("name", flat=True)
        return find_unused_name(
            [proposed_name], existing_applications_names, max_length=255
        )

    def update_application(
        self, user: AbstractUser, application: Application, **kwargs
    ) -> ApplicationUpdatedResult:
        """
        Updates an existing application instance.

        :param user: The user on whose behalf the application is updated.
        :param application: The application instance that needs to be updated.
        :param kwargs: Additional parameters to pass to the application update.
        :return: The updated application instance.
        """

        CoreHandler().check_permissions(
            user,
            UpdateApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        application_type = application_type_registry.get_by_model(application)
        allowed_values = extract_allowed(
            kwargs, self.default_update_allowed_fields + application_type.allowed_fields
        )
        prepared_values = application_type.prepare_value_for_db(
            allowed_values, application
        )

        original_allowed_values = {
            allowed_value: getattr(application, allowed_value)
            for allowed_value in prepared_values
        }

        for key, value in prepared_values.items():
            setattr(application, key, value)

        application.save()

        application_type.after_update(application, kwargs)

        application_updated.send(self, application=application, user=user)

        return ApplicationUpdatedResult(
            updated_application_instance=application,
            original_app_allowed_values=original_allowed_values,
            updated_app_allowed_values=allowed_values,
        )

    def duplicate_application(
        self,
        user: AbstractUser,
        application: Application,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Application:
        """
        Duplicates an existing application instance.

        :param user: The user on whose behalf the application is duplicated.
        :param application: The application instance that needs to be duplicated.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :return: The new (duplicated) application instance.
        """

        workspace = application.workspace

        CoreHandler().check_permissions(
            user,
            DuplicateApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        start_progress, export_progress, import_progress = 10, 30, 60
        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        progress.increment(by=start_progress)

        duplicate_import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )
        # export the application
        specific_application = application.specific
        application_type = application_type_registry.get_by_model(specific_application)
        try:
            serialized = application_type.export_serialized(
                specific_application, duplicate_import_export_config
            )
        except OperationalError as e:
            # Detect if this `OperationalError` is due to us exceeding the
            # lock count in `max_locks_per_transaction`. If it is, we'll
            # raise a different exception so that we can catch this scenario.

            if is_max_lock_exceeded_exception(e):
                raise DuplicateApplicationMaxLocksExceededException()
            raise e

        progress.increment(by=export_progress)

        # Set a new unique name for the new application
        serialized["name"] = self.find_unused_application_name(
            workspace.id, serialized["name"]
        )
        serialized["order"] = application_type.model_class.get_last_order(workspace)

        # import it back as a new application
        id_mapping: Dict[str, Any] = {}
        new_application_clone = application_type.import_serialized(
            workspace,
            serialized,
            duplicate_import_export_config,
            id_mapping,
            progress_builder=progress.create_child_builder(
                represents_progress=import_progress
            ),
        )

        # broadcast the application_created signal
        application_created.send(
            self,
            application=new_application_clone,
            user=user,
            type_name=application_type.type,
        )

        return new_application_clone

    def order_applications(
        self, user: AbstractUser, workspace: Workspace, order: List[int]
    ) -> List[int]:
        """
        Updates the order of the applications in the given workspace. The order of the
        applications that are not in the `order` parameter set to `0`.

        :param user: The user on whose behalf the tables are ordered.
        :param workspace: The workspace of which the applications must be updated.
        :param order: A list containing the application ids in the desired order.
        :raises ApplicationNotInWorkspace: If one of the applications ids in the order
            does not belong to the database.
        :return: The old order of application ids.
        """

        CoreHandler().check_permissions(
            user,
            OrderApplicationsOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        all_applications = Application.objects.filter(
            workspace_id=workspace.id
        ).order_by("order")

        users_applications = CoreHandler().filter_queryset(
            user,
            ReadApplicationOperationType.type,
            all_applications,
            workspace=workspace,
        )

        users_application_ids = list(users_applications.values_list("id", flat=True))

        # Check that all ordered ids can be ordered by the user
        for application_id in order:
            if application_id not in users_application_ids:
                raise ApplicationNotInWorkspace(application_id)

        new_order = Application.order_objects(all_applications, order)

        applications_reordered.send(
            self, workspace=workspace, order=new_order, user=user
        )

        return users_application_ids

    def delete_application(self, user: AbstractUser, application: Application):
        """
        Deletes an existing application instance if the user has access to the
        related workspace. The `application_deleted` signal is also called.

        :param user: The user on whose behalf the application is deleted.
        :param application: The application instance that needs to be deleted.
        :raises ValueError: If one of the provided parameters is invalid.
        """

        if not isinstance(application, Application):
            raise ValueError("The application is not an instance of Application")

        CoreHandler().check_permissions(
            user,
            DeleteApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        application_id = application.id
        TrashHandler.trash(
            user, application.workspace, application, application.specific
        )

        application_deleted.send(
            self, application_id=application_id, application=application, user=user
        )

    def export_workspace_applications(
        self,
        workspace,
        files_buffer,
        import_export_config: ImportExportConfig,
        storage=None,
    ):
        """
        Exports the applications of a workspace to a list. They can later be imported
        via the `import_applications_to_workspace` method. The result can be
        serialized to JSON.

        @TODO look into speed optimizations by streaming to a JSON file instead of
            generating the entire file in memory.

        :param workspace: The workspace of which the applications must be exported.
        :type workspace: Workspace
        :param files_buffer: A file buffer where the files must be written to in ZIP
            format.
        :type files_buffer: IOBase
        :param storage: The storage where the files can be loaded from.
        :type storage: Storage or None
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :return: A list containing the exported applications.
        :rtype: list
        """

        storage = storage or get_default_storage()
        zip_stream = zipstream.ZipStream(
            compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
            compress_type=zipstream.ZIP_DEFLATED,
        )

        exported_applications = []
        applications = workspace.application_set.all()
        for a in applications:
            application = a.specific
            application_type = application_type_registry.get_by_model(application)
            with application_type.export_safe_transaction_context(application):
                exported_application = application_type.export_serialized(
                    application, import_export_config, zip_stream, storage
                )
            exported_applications.append(exported_application)

        for chunk in zip_stream:
            files_buffer.write(chunk)

        return exported_applications

    def import_applications_to_workspace(
        self,
        workspace: Workspace,
        exported_applications: List[Dict[str, Any]],
        files_buffer: IO[bytes],
        import_export_config: ImportExportConfig,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Tuple[List[Application], Dict[str, Any]]:
        """
        Imports multiple exported applications into the given workspace. It is
        compatible with an export of the `export_workspace_applications` method.

        @TODO look into speed optimizations by streaming from a JSON file instead of
            loading the entire file into memory.

        :param workspace: The workspace that the applications must be imported to.
        :param exported_applications: A list containing the applications generated by
            the `export_workspace_applications` method.
        :param files_buffer: A file buffer containing the exported files in ZIP format.
        :param storage: The storage where the files can be copied to.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :return: The newly created applications based on the import and a dict
            containing a mapping of old ids to new ids.
        """

        progress = ChildProgressBuilder.build(
            progress_builder, len(exported_applications) * 1000
        )

        storage = storage or get_default_storage()

        # Sort the serialized applications so that we import:
        # Database first
        # Applications second
        # Everything else after that.
        def application_priority_sort(application_to_sort):
            return application_type_registry.get(
                application_to_sort["type"]
            ).import_application_priority

        prioritized_applications = sorted(
            exported_applications, key=application_priority_sort, reverse=True
        )

        # If files_buffer is a bytes object, decompress it. Otherwise, use it directly
        # as a file-like object. This can be used when files are not saved in a zip
        # file, but the object provides a way to download and used them on the fly.
        if isinstance(
            files_buffer, (bytes, bytearray, memoryview, BytesIO, BufferedReader)
        ):
            files_zip = ZipFile(files_buffer, "a", ZIP_DEFLATED, False)
        else:
            files_zip = files_buffer
        try:
            id_mapping: Dict[str, Any] = {}
            imported_applications = []
            next_application_order_value = Application.get_last_order(workspace)
            for application in prioritized_applications:
                application_type = application_type_registry.get(application["type"])
                imported_application = application_type.import_serialized(
                    workspace,
                    application,
                    import_export_config,
                    id_mapping,
                    files_zip,
                    storage,
                    progress_builder=progress.create_child_builder(
                        represents_progress=1000
                    ),
                )
                imported_application.order = next_application_order_value
                next_application_order_value += 1
                imported_applications.append(imported_application)
            Application.objects.bulk_update(imported_applications, ["order"])
        finally:
            files_zip.close()

        return imported_applications, id_mapping

    def get_template(self, template_id, base_queryset=None):
        """
        Selects a template with the given id from the database.

        :param template_id: The identifier of the template that must be returned.
        :type template_id: int
        :param base_queryset: The base queryset from where to select the workspace
            object. This can for example be used to do a `prefetch_related`.
        :type base_queryset: Queryset
        :raises TemplateDoesNotExist: When the workspace with the provided id does not
            exist.
        :return: The requested template instance related to the provided id.
        :rtype: Template
        """

        if base_queryset is None:
            base_queryset = Template.objects

        try:
            template = base_queryset.get(id=template_id)
        except Template.DoesNotExist:
            raise TemplateDoesNotExist(
                f"The template with id {template_id} does not " f"exist."
            )

        return template

    # This single function generates a huge number of spans and events, we know it
    # is slow, and so we disable instrumenting it to save significant resources in
    # telemetry platforms receiving the instrumentation.
    @disable_instrumentation
    def sync_templates(
        self, storage=None, pattern: str | None = None, force: bool = False
    ):
        """
        Synchronizes the JSON template files with the templates stored in the database.
        We need to have a copy in the database so that the user can live preview a
        template before installing. It will also make sure that the right categories
        exist and that old ones are deleted.

        If the template doesn't exist, a workspace can be created and we can import the
        export in that workspace. If the template already exists we check if the
        `export_hash` has changed, if so it means the export has changed. Because we
        don't have updating capability, we delete the old workspace and create a new one
        where we can import the export into.

        :param storage: Storage to use to get the files.
        :param pattern: A regular expression to match names to sync. If None then
            all found templates will be synced.
        :param force: Force template sync even if they already exist.
        """

        clean_templates = False
        if pattern is None:
            # We clean the template list only if we have the full list of templates
            clean_templates = True

        installed_templates = (
            Template.objects.all()
            .prefetch_related("categories")
            .select_related("workspace")
        )
        installed_categories = list(TemplateCategory.objects.all())

        sync_templates_import_export_config = ImportExportConfig(
            include_permission_data=False,
            # Without reducing disk space usage Baserow after first time install
            # takes up over 1GB of disk space.
            reduce_disk_space_usage=True,
        )

        # Loop over the JSON template files in the directory to see which database
        # templates need to be created or updated.
        template_files_paths = [
            p
            for p in Path(settings.APPLICATION_TEMPLATES_DIR).glob("*.json")
            if pattern is None or re.search(pattern, p.stem)
        ]

        for template_file_path in tqdm(
            template_files_paths,
            desc="Syncing Baserow templates. Disable by setting "
            "BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION=false.",
        ):
            with transaction.atomic():
                self._sync_template(
                    template_file_path,
                    sync_templates_import_export_config,
                    installed_templates,
                    installed_categories,
                    storage,
                    force=force,
                )

        if clean_templates:
            # Delete all the installed templates that were installed, but don't exist in
            # the template directory anymore.
            logger.info(
                "Deleting templates that were installed but no longer exist in the "
                "templates dir..."
            )

            slugs = [
                ".".join(template_file_path.name.split(".")[:-1])
                for template_file_path in template_files_paths
            ]

            for template in Template.objects.filter(~Q(slug__in=slugs)):
                with transaction.atomic():
                    TrashHandler.permanently_delete(template.workspace)
                    template.delete()

            # Delete all the categories that don't have any templates anymore.
            TemplateCategory.objects.annotate(num_templates=Count("templates")).filter(
                num_templates=0
            ).delete()

    def _sync_template(
        self,
        template_file_path,
        config,
        installed_templates,
        installed_categories,
        storage,
        force: bool = False,
    ):
        """
        Sync a specific template to the database.

        :param template_file_path: Path of the template that should be synced.
        :type template_file_path: Path
        :param config: Configuration to use when syncing the template.
        :type config: ImportExportConfig
        :param installed_templates: List of installed Templates.
        :type installed_templates: List[Template]
        :param installed_categories: List of installed Template Categories.
        :type installed_categories: List[TemplateCategory]
        :param storage: The storage where the files can be loaded from.
        :type storage: Storage or None
        :param force: Force template sync even if they already exist.
        :return: None
        """

        content = Path(template_file_path).read_text()
        parsed_json = json.loads(content)

        if "baserow_template_version" not in parsed_json:
            return

        slug = ".".join(template_file_path.name.split(".")[:-1])

        logger.info(f"Importing template {slug}")

        installed_template = next(
            (t for t in installed_templates if t.slug == slug), None
        )
        hash_json = json.dumps(parsed_json["export"])
        export_hash = hashlib.sha256(hash_json.encode("utf-8")).hexdigest()
        keywords = (
            ",".join(parsed_json["keywords"]) if "keywords" in parsed_json else ""
        )

        # If the installed template and workspace exist, and if there is a hash
        # mismatch, we need to delete the old workspace and all the related
        # applications in it. This is because a new workspace will be created.
        if (
            installed_template
            and installed_template.workspace
            and (installed_template.export_hash != export_hash or force)
        ):
            TrashHandler.permanently_delete(installed_template.workspace)

        # If the installed template does not yet exist or if there is a export
        # hash mismatch, which means the workspace has already been deleted, we can
        # create a new workspace and import the exported applications into that
        # workspace.
        imported_id_mapping = None
        if (
            not installed_template
            or installed_template.export_hash != export_hash
            or force
        ):
            # It is optionally possible for a template to have additional files.
            # They are stored in a ZIP file and are generated when the template
            # is exported. They for example contain file field files.
            try:
                files_file_path = f"{os.path.splitext(template_file_path)[0]}.zip"
                files_buffer = open(files_file_path, "rb")
            except FileNotFoundError:
                # If the file is not found, we provide a BytesIO buffer to
                # maintain backward compatibility and to not brake anything.
                files_buffer = BytesIO()

            workspace = Workspace.objects.create(name=parsed_json["name"])
            _, id_mapping = self.import_applications_to_workspace(
                workspace,
                parsed_json["export"],
                files_buffer=files_buffer,
                import_export_config=config,
                storage=storage,
            )
            imported_id_mapping = id_mapping

            if files_buffer:
                files_buffer.close()
        else:
            workspace = installed_template.workspace
            workspace.name = parsed_json["name"]
            workspace.save()

        kwargs = {
            "name": parsed_json["name"],
            "icon": parsed_json["icon"],
            "export_hash": export_hash,
            "keywords": keywords,
            "workspace": workspace,
        }

        # If the template was imported, then we'll map the desired open_application
        # id to the actually imported application id.
        if "open_application" in parsed_json and imported_id_mapping is not None:
            kwargs["open_application"] = imported_id_mapping["applications"].get(
                parsed_json["open_application"], None
            )

        if not installed_template:
            installed_template = Template.objects.create(slug=slug, **kwargs)
        else:
            # If the installed template already exists, we only need to update the
            # values to the latest version according to the JSON template.
            for key, value in kwargs.items():
                setattr(installed_template, key, value)
            installed_template.save()

        # Loop over the categories related to the template and check which ones
        # already exist and which need to be created. Based on that we can create
        # a list of category ids that we can set for the template.
        template_category_ids = []
        for category_name in parsed_json["categories"]:
            installed_category = next(
                (c for c in installed_categories if c.name == category_name), None
            )
            if not installed_category:
                installed_category = TemplateCategory.objects.create(name=category_name)
                installed_categories.append(installed_category)
            template_category_ids.append(installed_category.id)

        installed_template.categories.set(template_category_ids)

    def get_valid_template_path_or_raise(self, template):
        file_name = f"{template.slug}.json"
        template_path = Path(
            os.path.join(settings.APPLICATION_TEMPLATES_DIR, file_name)
        )

        if not template_path.exists():
            raise TemplateFileDoesNotExist(
                f"The template with file name {file_name} does not exist. You might "
                f"need to run the `sync_templates` management command."
            )
        return template_path

    def install_template(
        self,
        user: AbstractUser,
        workspace: Workspace,
        template: Template,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Tuple[List[Application], Dict[str, Any]]:
        """
        Installs the exported applications of a template into the given workspace if the
        provided user has access to that workspace.

        :param user: The user on whose behalf the template installed.
        :param workspace: The workspace where the template applications must be
            imported into.
        :param template: The template that must be installed.
        :param storage: The storage where the files can be copied to.
        :return: The imported applications.
        """

        CoreHandler().check_permissions(
            user,
            CreateApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        template_path = self.get_valid_template_path_or_raise(template)

        content = template_path.read_text()
        parsed_json = json.loads(content)

        # It is optionally possible for a template to have additional files. They are
        # stored in a ZIP file and are generated when the template is exported. They
        # for example contain file field files.
        try:
            files_path = f"{os.path.splitext(template_path)[0]}.zip"
            files_buffer = open(files_path, "rb")
        except FileNotFoundError:
            # If the file is not found, we provide a BytesIO buffer to
            # maintain backward compatibility and to not brake anything.
            files_buffer = BytesIO()

        applications, id_mapping = self.import_applications_to_workspace(
            workspace,
            parsed_json["export"],
            files_buffer=files_buffer,
            import_export_config=ImportExportConfig(
                include_permission_data=False,
                reduce_disk_space_usage=False,
                is_duplicate=True,
            ),
            storage=storage,
            progress_builder=progress_builder,
        )

        if files_buffer:
            files_buffer.close()

        # Because a user has initiated the creation of applications, we need to
        # call the `application_created` signal for each created application.
        #
        # The `application_imported` signal is sent to ensure that any
        # post-import logic is executed, e.g. configuring integrations.
        for application in applications:
            application_type = application_type_registry.get_by_model(application)
            application.installed_from_template = template
            for signal in [application_created, application_imported]:
                signal.send(
                    self,
                    application=application,
                    user=user,
                    type_name=application_type.type,
                )

        Application.objects.bulk_update(applications, ["installed_from_template"])

        return applications, id_mapping

    @classmethod
    def raise_if_user_is_last_admin_of_workspace(cls, workspace_user: WorkspaceUser):
        """
        Checks if a user that's about to be removed is the last admin of the workspace.

        :param workspace_user: The workspace user we are checking for
        :return:
        """

        admins_in_workspace_count = len(
            WorkspaceUser.objects.filter(
                workspace=workspace_user.workspace, permissions="ADMIN"
            ).select_for_update(of=("self",))
        )

        is_subject_admin = workspace_user.permissions == "ADMIN"
        is_subject_last_admin = is_subject_admin and admins_in_workspace_count == 1

        if is_subject_last_admin:
            raise LastAdminOfWorkspace()

    def create_initial_workspace(self, user: AbstractUser) -> Workspace:
        """
        Creates an initial workspace with example data.

        :param user: The user for whom the workspace must be created.
        :return: The newly created workspace.
        """

        with translation.override(user.profile.language):
            workspace_user = self.create_workspace(
                user=user, name=_("%(name)s's workspace") % {"name": user.first_name}
            )

        for plugin in plugin_registry.registry.values():
            plugin.create_initial_workspace(user, workspace_user.workspace)

        return workspace_user

    @staticmethod
    def is_max_lock_exceeded_exception(exception: OperationalError) -> bool:
        """
        Returns whether the `OperationalError` which we've been given
        is due to `max_locks_per_transaction` being exceeded.
        """

        return (
            "You might need to increase max_locks_per_transaction" in exception.args[0]
        )

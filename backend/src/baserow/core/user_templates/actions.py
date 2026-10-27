import dataclasses
from typing import Callable, Iterable, List, Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    RootActionScopeType,
    WorkspaceActionScopeType,
)
from baserow.core.models import Template, Workspace
from baserow.core.user_templates.exceptions import TemplateChangedDuringUpdate
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.service import UserTemplateService
from baserow.core.utils import ChildProgressBuilder


class CreateUserTemplateActionType(ActionType):
    type = "create_user_template"
    description = ActionTypeDescription(
        _("Create template"),
        _(
            'Template "%(template_name)s" (%(template_id)s) created from '
            "applications %(application_ids)s"
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "template_id",
        "workspace_id",
        "application_ids",
    ]

    @dataclasses.dataclass
    class Params:
        template_id: int
        template_name: str
        workspace_id: int
        workspace_name: str
        application_ids: List[int]

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        application_ids: List[int],
        *,
        name: str,
        description: str,
        icon: str,
        category_ids: Iterable[int],
        progress_builder: Optional[ChildProgressBuilder] = None,
        track_content: Optional[Callable[..., None]] = None,
        before_commit: Optional[Callable[[Template], None]] = None,
    ) -> Template:
        """
        Creates a private user template from applications of the workspace. This
        action is not undoable.

        The applications are copied first, in transactions of their own, see
        `UserTemplateHandler.copy_applications`. The template and the action are
        then created in one transaction, which a cancellation of the job noticed
        before it commits rolls back.

        :param user: The user creating the template.
        :param workspace: The workspace the applications are copied from.
        :param application_ids: The ids of the selected applications.
        :param name: The name of the template.
        :param description: The description of the template.
        :param icon: The icon class name, an iconoir class.
        :param category_ids: The ids of the existing categories of the template.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :param track_content: Called with the content created so far.
        :param before_commit: Called with the template as the last step of its
            transaction, and can still roll it back by raising.
        :return: The created template.
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        template_workspace = UserTemplateService().copy_applications(
            user,
            workspace,
            application_ids,
            name=name,
            progress_builder=progress.create_child_builder(represents_progress=99),
            track_content=track_content,
        )

        with transaction.atomic():
            template = UserTemplateHandler().create_template_root(
                owner=user,
                name=name,
                description=description,
                icon=icon,
                category_ids=category_ids,
                workspace=template_workspace,
                # A copy has no archive, see `UserTemplateHandler.copy_applications`.
                archive="",
                metadata=UserTemplateHandler().build_template_metadata(
                    workspace, application_ids
                ),
            )
            params = cls.Params(
                template_id=template.id,
                template_name=template.name,
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                application_ids=list(application_ids),
            )
            cls.register_action(
                user, params, cls.scope(workspace.id), workspace=workspace
            )
            progress.increment()
            if before_commit is not None:
                before_commit(template)

        return template

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateUserTemplateActionType(ActionType):
    type = "update_user_template"
    # A details-only update has no workspace, so the description has no workspace
    # context.
    description = ActionTypeDescription(
        _("Update template"),
        _('Template "%(template_name)s" (%(template_id)s) updated'),
    )
    analytics_params = [
        "template_id",
        "revision_id",
        "version",
        "workspace_id",
        "application_ids",
    ]

    @dataclasses.dataclass
    class Params:
        template_id: int
        template_name: str
        revision_id: int
        version: int
        # Only set when the content is copied from a workspace.
        workspace_id: Optional[int] = None
        workspace_name: Optional[str] = None
        application_ids: Optional[List[int]] = None

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        root: Template,
        base_revision: Optional[Template],
        source_workspace: Optional[Workspace],
        application_ids: List[int],
        *,
        name: str,
        description: str,
        icon: str,
        category_ids: Iterable[int],
        progress_builder: Optional[ChildProgressBuilder] = None,
        track_content: Optional[Callable[..., None]] = None,
        before_commit: Optional[Callable[[Template], None]] = None,
    ) -> Template:
        """
        Creates the next revision of a user template owned by the user. With a
        source workspace, the content is copied from its applications. Otherwise
        the revision shares the content of `base_revision`, so that only the
        details change. This action is not undoable.

        Copied content is copied first, in transactions of its own, see
        `UserTemplateHandler.copy_applications`. The revision and the action are
        then created in one transaction, which a cancellation of the job noticed
        before it commits rolls back.

        :param user: The user updating the template.
        :param root: The root of the template.
        :param base_revision: The latest revision when the update was scheduled.
        :param source_workspace: The workspace the applications are copied from,
            or None to share the content of `base_revision`.
        :param application_ids: The ids of the selected applications of the
            source workspace.
        :param name: The name of the revision.
        :param description: The description of the revision.
        :param icon: The icon class name, an iconoir class.
        :param category_ids: The ids of the existing categories of the revision.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :param track_content: Called with the content copied so far. Shared
            content isn't tracked, so that the cleanup of the job never deletes
            it.
        :param before_commit: Called with the revision as the last step of its
            transaction, and can still roll it back by raising.
        :raises TemplateChangedDuringUpdate: If the template got a new revision
            since `base_revision`.
        :return: The created revision.
        """

        if base_revision is None:
            raise TemplateChangedDuringUpdate(
                "The template was changed while it was being updated."
            )

        handler = UserTemplateHandler()
        service = UserTemplateService()
        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        if source_workspace is not None:
            # A copy has no archive, see `UserTemplateHandler.copy_applications`.
            archive_name = ""
            template_workspace = service.copy_applications(
                user,
                source_workspace,
                application_ids,
                name=name,
                progress_builder=progress.create_child_builder(represents_progress=99),
                track_content=track_content,
            )
            metadata = handler.build_template_metadata(
                source_workspace, application_ids
            )
        else:
            template_workspace, archive_name = service.get_template_content(
                base_revision
            )
            metadata = handler.get_source_metadata(base_revision)
            progress.increment(by=99)

        with transaction.atomic():
            revision = handler.create_template_revision(
                user=user,
                root=root,
                base_revision=base_revision,
                name=name,
                description=description,
                icon=icon,
                category_ids=category_ids,
                workspace=template_workspace,
                archive=archive_name,
                metadata=metadata,
            )
            params = cls.Params(
                template_id=root.id,
                template_name=revision.name,
                revision_id=revision.id,
                version=revision.version,
            )
            if source_workspace is not None:
                params.workspace_id = source_workspace.id
                params.workspace_name = source_workspace.name
                params.application_ids = list(application_ids)
            # A details-only update isn't related to any workspace of the user.
            cls.register_action(
                user,
                params,
                cls.scope(params.workspace_id),
                workspace=source_workspace,
            )
            progress.increment()
            if before_commit is not None:
                before_commit(revision)

        return revision

    @classmethod
    def scope(cls, workspace_id: Optional[int] = None) -> ActionScopeStr:
        if workspace_id is None:
            return RootActionScopeType.value()
        return WorkspaceActionScopeType.value(workspace_id)


class DeleteUserTemplateActionType(ActionType):
    type = "delete_user_template"
    description = ActionTypeDescription(
        _("Delete template"),
        _('Template "%(template_name)s" (%(template_id)s) deleted'),
    )
    analytics_params = ["template_id", "owner_id"]

    @dataclasses.dataclass
    class Params:
        template_id: int
        template_name: str
        owner_id: Optional[int]
        owner_email: Optional[str]

    @classmethod
    def do(cls, user: AbstractUser, template_id: int) -> Template:
        """
        Deletes a user template, by its owner or by an instance admin. It's gone
        for everybody right away and removed later. This action is not undoable.

        :param user: The user deleting the template.
        :param template_id: The id of the template, which is its root.
        :return: The root of the template, marked for deletion.
        """

        with transaction.atomic():
            root = UserTemplateService().delete_template(user, template_id)
            # The name of the template is the name of its latest revision.
            latest_revision = UserTemplateHandler().get_latest_revision(root)
            owner = root.owner
            params = cls.Params(
                template_id=root.id,
                template_name=latest_revision.name,
                owner_id=owner.id if owner else None,
                owner_email=owner.email if owner else None,
            )
            cls.register_action(user, params, cls.scope())

        return root

    @classmethod
    def scope(cls) -> ActionScopeStr:
        return RootActionScopeType.value()

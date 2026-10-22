from typing import Callable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import PermissionDenied
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Application, Template, Workspace
from baserow.core.user_templates.exceptions import (
    NoApplicationsSelected,
    TemplateHasNoContent,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.utils import ChildProgressBuilder


class UserTemplateService:
    def get_exportable_applications(
        self, user: AbstractUser, workspace: Workspace, application_ids: List[int]
    ) -> List[Application]:
        """
        Returns the applications the user can copy into a template. Copying needs
        the same permission as exporting the workspace.

        :param user: The user creating the template.
        :param workspace: The workspace the applications are copied from.
        :param application_ids: The ids of the selected applications.
        :raises NoApplicationsSelected: If no application is selected.
        :raises PermissionDenied: If the user can't export the workspace, the
            workspace holds a template, or one of the applications doesn't exist
            or isn't visible to the user.
        :return: The selected applications.
        """

        if not application_ids:
            raise NoApplicationsSelected("At least one application must be selected.")

        applications = job_type_registry.get(
            ExportApplicationsJobType.type
        ).fetch_applications(user, workspace, list(set(application_ids)))

        if workspace.has_template():
            raise PermissionDenied("A template can't be created from a template.")

        return list(applications)

    def copy_applications(
        self,
        user: AbstractUser,
        workspace: Workspace,
        application_ids: List[int],
        *,
        name: str,
        progress_builder: Optional[ChildProgressBuilder] = None,
        track_content: Optional[Callable[..., None]] = None,
    ) -> Tuple[Workspace, str]:
        """
        Copies applications of the workspace into the content of a new user
        template. See `UserTemplateHandler.copy_applications` for further details.

        :param user: The user creating the template.
        :param workspace: The workspace the applications are copied from.
        :param application_ids: The ids of the selected applications.
        :param name: The name of the template.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :param track_content: Called with the content created so far.
        :raises NoApplicationsSelected: If no application is selected.
        :raises PermissionDenied: If the user can't copy the applications.
        :return: The workspace holding the copy and the name of the stored archive.
        """

        applications = self.get_exportable_applications(
            user, workspace, application_ids
        )
        return UserTemplateHandler().copy_applications(
            user,
            applications,
            name=name,
            progress_builder=progress_builder,
            track_content=track_content,
        )

    def get_own_template(self, user: AbstractUser, template_id: int) -> Template:
        """
        Returns a user template the user owns, so that they can manage it. See
        `UserTemplateHandler.get_own_template` for further details.

        :param user: The user who must own the template.
        :param template_id: The id of the template, which is its root.
        :raises TemplateDoesNotExist: If the user doesn't own the template.
        :return: The root of the template.
        """

        return UserTemplateHandler().get_own_template(user, template_id)

    def get_template_content(
        self, base_revision: Template
    ) -> Tuple[Workspace, Optional[str]]:
        """
        Returns the content of a revision of a user template, which its next
        revision reuses when only the details change. The revisions then share the
        workspace and the archive, so that a details-only update is cheap and can
        be told apart from a content change. The ownership of the template is
        checked by the caller.

        :param base_revision: The revision whose content is reused.
        :raises TemplateHasNoContent: If the content of the revision was removed.
        :return: The workspace and the name of the archive of the revision.
        """

        if not base_revision.has_content:
            raise TemplateHasNoContent("The template has no content anymore.")

        return base_revision.workspace, base_revision.archive.name or None

    def delete_template(self, user: AbstractUser, template_id: int) -> Template:
        """
        Marks a user template for deletion, so that it's gone for everybody right
        away and removed later. See `UserTemplateHandler.get_template_for_deletion`
        for who can delete it. Must run in a transaction.

        :param user: The user who deletes the template, its owner or an instance
            admin.
        :param template_id: The id of the template, which is its root.
        :raises TemplateDoesNotExist: If the user can't delete the template.
        :return: The marked root of the template.
        """

        handler = UserTemplateHandler()
        root = handler.get_template_for_deletion(user, template_id)
        handler.mark_template_for_deletion(root)
        return root

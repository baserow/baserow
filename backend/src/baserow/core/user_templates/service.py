from typing import Callable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import PermissionDenied
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Application, Template, UserTemplateState, Workspace
from baserow.core.user_templates.exceptions import (
    NoApplicationsSelected,
    TemplateBlocked,
    TemplateHasNoContent,
    UserTemplatePublicListingConsentRequired,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import CreateUserTemplateJob
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
    ) -> Workspace:
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
        :return: The workspace holding the copy.
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

    def update_visibility(
        self,
        user: AbstractUser,
        template_id: int,
        make_public: bool,
        public_listing_consent: bool,
        job_id: Optional[int] = None,
    ) -> Tuple[Template, Optional[int], Optional[UserTemplateState]]:
        """
        Makes a user template public or private. Must run in a transaction.

        :param user: The owner of the template.
        :param template_id: The id of the template, which is its root.
        :param make_public: Whether the template is made public, else private.
        :param public_listing_consent: Whether the user agreed that the template
            and their name are listed for everybody on the instance.
        :param job_id: The id of the create user template job making the template
            public, which it only does while the job still asks for it.
        :raises TemplateDoesNotExist: If the user doesn't own the template.
        :raises TemplateBlocked: If the template is blocked.
        :raises UserTemplatePublicListingConsentRequired: If the template is made
            public without the consent.
        :raises TemplateHasNoContent: If the latest revision has no content.
        :return: The latest revision, the id of the revision that was listed,
            submitted or unlisted, otherwise the one withdrawn, and the state of
            the template after the change: public, in review or private. Both None
            if nothing changed.
        """

        handler = UserTemplateHandler()
        # Read before the root is locked.
        require_approval = make_public and handler.read_require_approval()
        root = self._get_own_unblocked_root(user, template_id)
        if make_public and not public_listing_consent:
            raise UserTemplatePublicListingConsentRequired(
                "Making a template public needs the consent of its author."
            )

        revision = handler.get_latest_revision_of_locked_root(root)

        if not make_public:
            changed_revision_id = handler.make_template_private(root)
            if changed_revision_id is None:
                return revision, None, None
            return revision, changed_revision_id, UserTemplateState.PRIVATE

        # Read under the lock of the root, after which a make private clears it.
        if (
            job_id is not None
            and not CreateUserTemplateJob.objects.filter(
                id=job_id, make_public=True
            ).exists()
        ):
            return revision, None, None

        self.get_template_content(revision)
        if not handler.make_public_submits(revision):
            return revision, None, None
        if handler.submit_revision(root, revision, require_approval=require_approval):
            return revision, revision.id, UserTemplateState.PUBLIC
        return revision, revision.id, UserTemplateState.IN_REVIEW

    def update_private_link(
        self, user: AbstractUser, template_id: int, enabled: bool
    ) -> Tuple[Template, bool]:
        """
        Creates or turns off the private link of a user template owned by the
        user, see `UserTemplateHandler.set_private_link`. Must run in a
        transaction.

        :param user: The owner of the template.
        :param template_id: The id of the template, which is its root.
        :param enabled: Whether the template must have a private link.
        :raises TemplateDoesNotExist: If the user doesn't own the template.
        :raises TemplateBlocked: If the template is blocked.
        :return: The latest revision, and whether the link changed.
        """

        root = self._get_own_unblocked_root(user, template_id)
        handler = UserTemplateHandler()
        changed = handler.set_private_link(root, enabled)
        return handler.get_latest_revision_of_locked_root(root), changed

    def rotate_private_link(
        self, user: AbstractUser, template_id: int
    ) -> Tuple[Template, bool]:
        """
        Replaces the token of the private link of a user template owned by the
        user, see `UserTemplateHandler.rotate_private_link`. Must run in a
        transaction.

        :param user: The owner of the template.
        :param template_id: The id of the template, which is its root.
        :raises TemplateDoesNotExist: If the user doesn't own the template.
        :raises TemplateBlocked: If the template is blocked.
        :return: The latest revision, and whether the token was replaced.
        """

        root = self._get_own_unblocked_root(user, template_id)
        handler = UserTemplateHandler()
        rotated = handler.rotate_private_link(root)
        return handler.get_latest_revision_of_locked_root(root), rotated

    def _get_own_unblocked_root(self, user: AbstractUser, template_id: int) -> Template:
        """
        Locks the root of a template owned by the user, if it isn't blocked.
        """

        root = UserTemplateHandler().get_own_template(
            user, template_id, for_update=True
        )
        if root.blocked_at is not None:
            raise TemplateBlocked(f"The template {root.id} is blocked.")
        return root

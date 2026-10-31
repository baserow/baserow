from typing import Callable, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import PermissionDenied
from baserow.core.job_types import ExportApplicationsJobType
from baserow.core.jobs.registries import job_type_registry
from baserow.core.models import Application, Template, Workspace
from baserow.core.user_templates.constants import UserTemplateState
from baserow.core.user_templates.exceptions import (
    NoApplicationsSelected,
    TemplateHasNoContent,
    TemplateUpdated,
    UserTemplatePublicListingConsentRequired,
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
        listed: bool,
        public_listing_consent: bool,
        revision_id: Optional[int] = None,
    ) -> Tuple[Template, Optional[int], Optional[UserTemplateState]]:
        """
        Makes a user template public or private. A public template lists its
        latest revision for everybody on the instance, or waits for the review of
        an admin when approval is required or one rejected it, see
        `UserTemplateHandler.submit_revision`. A private one isn't listed anymore
        and is withdrawn from the review, and only its owner can open it. Asking
        for the visibility it has, or making public a template in review, changes
        nothing, except that making public a listed template whose latest edit was
        rejected submits that edit for review again. Must run in a transaction.

        :param user: The owner of the template.
        :param template_id: The id of the template, which is its root.
        :param listed: Whether the template is made public.
        :param public_listing_consent: Whether the user agreed that the template
            and their name are listed for everybody on the instance.
        :param revision_id: The id of the revision the user was shown, to make
            the template public only if that revision is listed.
        :raises TemplateDoesNotExist: If the user doesn't own the template.
        :raises UserTemplatePublicListingConsentRequired: If the template is made
            public without the consent.
        :raises TemplateUpdated: If the template is made public while another
            revision than `revision_id` is the latest.
        :raises TemplateHasNoContent: If the latest revision has no content.
        :return: The latest revision, the id of the revision that was listed,
            submitted or unlisted, otherwise the one withdrawn, and the state of
            the template after the change: public, in review or private. Both None
            if nothing changed.
        """

        handler = UserTemplateHandler()
        # Read before the root is locked, see `read_require_approval`.
        require_approval = listed and handler.read_require_approval()
        root = handler.get_own_template(user, template_id, for_update=True)
        if listed and not public_listing_consent:
            raise UserTemplatePublicListingConsentRequired(
                "Making a template public needs the consent of its author."
            )

        revision = handler.get_latest_revision(root)
        if revision.id == root.id:
            revision = root
        else:
            # Reads the state of the template from the locked root.
            revision.root = root

        if not listed:
            public_revision_id = root.public_revision_id
            if public_revision_id is not None:
                handler.withdraw_listing(root)
            # Also when it was listed: an edit of it can be in review or rejected.
            withdrawn = handler.withdraw_review(revision)
            if public_revision_id is not None:
                return revision, public_revision_id, UserTemplateState.PRIVATE
            if withdrawn:
                return revision, revision.id, UserTemplateState.PRIVATE
            return revision, None, None

        # The author agreed to list what they were shown, not an update made in
        # another tab since.
        if revision_id is not None and revision_id != revision.id:
            raise TemplateUpdated(
                f"The template {root.id} was updated after revision {revision_id} "
                "was shown."
            )
        self.get_template_content(revision)
        if (
            root.public_revision_id == revision.id
            or revision.review_state == Template.ReviewState.PENDING
        ):
            return revision, None, None
        if handler.submit_revision(root, revision, require_approval=require_approval):
            return revision, revision.id, UserTemplateState.PUBLIC
        return revision, revision.id, UserTemplateState.IN_REVIEW

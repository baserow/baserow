import dataclasses
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.files import File
from django.db import IntegrityError, connection, transaction
from django.db.models import (
    Case,
    CharField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, NullIf
from django.utils import timezone
from django.utils.text import slugify

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from baserow.core.exceptions import IsNotAdminError, TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import JOB_STATES_ENDED, Job
from baserow.core.models import (
    Application,
    InstallTemplateJob,
    Settings,
    Template,
    TemplateCategory,
    UserTemplateState,
    Workspace,
    is_instance_admin,
)
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.storage import get_default_storage
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_templates.archive import (
    delete_template_archive_file,
    delete_template_archives,
    is_valid_template_archive,
    new_template_archive_name,
    template_archive_dir,
)
from baserow.core.user_templates.constants import (
    USER_TEMPLATE_ADMIN_STATES,
    USER_TEMPLATE_DELETION_GRACE_PERIOD,
    USER_TEMPLATE_ICON_MAX_LENGTH,
    USER_TEMPLATE_ICON_REGEX,
    USER_TEMPLATE_PURGE_BATCH_SIZE,
    InstallAccess,
)
from baserow.core.user_templates.exceptions import (
    InvalidTemplateCategory,
    InvalidTemplateIcon,
    TemplateAlreadyApproved,
    TemplateAlreadyRejected,
    TemplateBlocked,
    TemplateBlockReasonRequired,
    TemplateChangedDuringUpdate,
    TemplateHasNoContent,
    TemplateNotReviewable,
    TemplateRejectReasonRequired,
    TemplateSlugGenerationFailed,
    TemplateUpdated,
)
from baserow.core.user_templates.types import TemplateMetadata
from baserow.core.utils import ChildProgressBuilder

User = get_user_model()

SLUG_SUFFIX_LENGTH = 6
SLUG_SUFFIX_ALPHABET = string.ascii_lowercase + string.digits
# Leaves room for the `-` and the suffix within the 50 characters of `Template.slug`.
SLUG_BASE_MAX_LENGTH = 43
SLUG_MAX_ATTEMPTS = 3
UNIQUE_ROOT_SLUG_CONSTRAINT = "core_template_unique_root_slug"


def generate_slug_suffix() -> str:
    """
    Returns 6 random base36 characters with at least one digit, so the suffix never
    reads as a word.
    """

    while True:
        suffix = "".join(
            secrets.choice(SLUG_SUFFIX_ALPHABET) for _ in range(SLUG_SUFFIX_LENGTH)
        )
        if any(char.isdigit() for char in suffix):
            return suffix


def generate_template_slug(name: str) -> str:
    """
    Returns a slug for a user template. The random suffix keeps it apart from the
    official template slugs, which are file names.
    """

    base = slugify(name)[:SLUG_BASE_MAX_LENGTH].strip("-") or "template"
    return f"{base}-{generate_slug_suffix()}"


def user_template_copy_config() -> ImportExportConfig:
    """
    Returns the configuration with which the content of a user template is
    copied, both into the template and out of it when it's installed (the
    install fills in the search data of the copy). The copy is made as if nobody
    were a member of the target workspace, so it drops what belongs to the users
    of the source: personal views, collaborators and sensitive data.
    """

    return ImportExportConfig(
        include_permission_data=False,
        reduce_disk_space_usage=True,
        workspace_for_user_references=None,
        is_duplicate=False,
        is_user_template=True,
        exclude_sensitive_data=True,
    )


def _is_unique_root_slug_violation(error: IntegrityError) -> bool:
    diag = getattr(error.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None) == UNIQUE_ROOT_SLUG_CONSTRAINT


def author_name_expression(author: str) -> Coalesce:
    """
    The first name of the user, or their email when it's empty.

    :param author: The path to the user from the template.
    :return: The expression of the name.
    """

    return Coalesce(
        NullIf(f"{author}__first_name", Value("")),
        f"{author}__email",
        output_field=CharField(),
    )


class UserTemplateHandler:
    def validate_icon_and_categories(
        self, icon: str, category_ids: Iterable[int]
    ) -> list[TemplateCategory]:
        """
        Checks the icon and the categories chosen for a user template.

        :param icon: The icon class name, an iconoir class.
        :param category_ids: The ids of the existing categories, at least one
            unless the instance has none, like one that never synced templates.
        :raises InvalidTemplateIcon: If the icon isn't allowed.
        :raises InvalidTemplateCategory: If no category is given while there are
            some, or one of them doesn't exist.
        :return: The categories.
        """

        if len(
            icon
        ) > USER_TEMPLATE_ICON_MAX_LENGTH or not USER_TEMPLATE_ICON_REGEX.fullmatch(
            icon
        ):
            raise InvalidTemplateIcon(f"The icon {icon} is not allowed.")

        category_ids = set(category_ids)
        if not category_ids:
            if TemplateCategory.objects.exists():
                raise InvalidTemplateCategory("At least one category is required.")
            return []

        categories = list(TemplateCategory.objects.filter(id__in=category_ids))
        if len(categories) != len(category_ids):
            raise InvalidTemplateCategory("The categories are invalid.")

        return categories

    def build_template_metadata(
        self, source_workspace: Workspace, source_application_ids: Iterable[int]
    ) -> TemplateMetadata:
        """
        Returns the private metadata of a revision copied from the applications of
        a workspace.

        :param source_workspace: The workspace the applications are copied from.
        :param source_application_ids: The ids of the copied applications.
        :return: The metadata to store on the revision.
        """

        return TemplateMetadata(
            source_workspace_id=source_workspace.id,
            source_application_ids=list(source_application_ids),
        )

    def get_template_metadata(self, template: Template) -> TemplateMetadata:
        """
        Returns the private metadata of a template revision. Any key can be
        missing.
        """

        return TemplateMetadata(**template.metadata)

    def get_source_metadata(self, template: Template) -> TemplateMetadata:
        """
        Returns the metadata telling where the content of a template revision was
        copied from. A revision copying the content of another one inherits it.
        """

        metadata = self.get_template_metadata(template)
        return TemplateMetadata(
            **{
                key: value
                for key, value in metadata.items()
                if key in ("source_workspace_id", "source_application_ids")
            }
        )

    def create_template_root(
        self,
        *,
        owner: AbstractUser,
        name: str,
        description: str,
        icon: str,
        category_ids: Iterable[int],
        workspace: Workspace,
        archive: Optional[File | str] = None,
        metadata: Optional[TemplateMetadata] = None,
    ) -> Template:
        """
        Creates a private user template, which is a root holding revision 1. This is
        the only place where user templates are created.

        :param owner: The user who creates the template. They become its owner and
            author.
        :param name: The name of the template.
        :param description: The description of the template.
        :param icon: The icon class name, an iconoir class.
        :param category_ids: The ids of the existing categories of the template, at
            least one.
        :param workspace: The workspace holding the content of the template.
        :param archive: The downloadable file of the template, or the name of a
            file already in the storage.
        :param metadata: The private metadata of revision 1, built with
            `build_template_metadata`.
        :raises InvalidTemplateIcon: If the icon isn't allowed.
        :raises InvalidTemplateCategory: If no category is given while there are
            some, or one of them doesn't exist.
        :raises ValidationError: If the template isn't valid.
        :raises TemplateSlugGenerationFailed: If no free slug was found.
        :raises UserNotFound: If the owner was deleted.
        :return: The created template.
        """

        categories = self.validate_icon_and_categories(icon, category_ids)

        template = Template(
            type=Template.Type.USER,
            owner=owner,
            author=owner,
            version=1,
            root=None,
            name=name,
            description=description,
            icon=icon,
            workspace=workspace,
            archive=archive,
            metadata=metadata or {},
        )
        # The slug is generated by us. Its uniqueness is left to the database, so a
        # slug taken in the meantime can be retried below. `open_application` is
        # nullable but not blank, and null opens the first application.
        template.full_clean(exclude=["slug", "open_application"])

        with transaction.atomic():
            if not self._lock_user(owner):
                raise UserNotFound("The owner of the template was deleted.")

            for _ in range(SLUG_MAX_ATTEMPTS):
                template.slug = generate_template_slug(name)
                try:
                    with transaction.atomic():
                        template.save()
                    break
                except IntegrityError as error:
                    if not _is_unique_root_slug_violation(error):
                        raise
            else:
                raise TemplateSlugGenerationFailed(
                    "No free slug was found for the template."
                )

            template.categories.set(categories)
            # The template types of a workspace are cached by `updated_on`, which
            # tells every process that this workspace is a template now.
            workspace.save(update_fields=["updated_on"])

        return template

    def create_template_revision(
        self,
        *,
        user: AbstractUser,
        root: Template,
        base_revision: Optional[Template],
        name: str,
        description: str,
        icon: str,
        category_ids: Iterable[int],
        workspace: Workspace,
        archive: Optional[File | str] = None,
        metadata: Optional[TemplateMetadata] = None,
    ) -> Template:
        """
        Creates the next revision of a user template, whose content is already
        copied. This is the only place where revisions are created.

        Locks the root, so updates of a template commit one after the other. The
        review follows the new revision, see `update_review_step`.

        :param user: The user who updates the template, who must own it.
        :param root: The root of the template.
        :param base_revision: The latest revision when the update was scheduled.
        :param name: The name of the revision.
        :param description: The description of the revision.
        :param icon: The icon class name, an iconoir class.
        :param category_ids: The ids of the existing categories of the revision, at
            least one.
        :param workspace: The workspace holding the content of the revision.
        :param archive: The downloadable file of the revision, or the name of a
            file already in the storage.
        :param metadata: The private metadata of the revision, built with
            `build_template_metadata` or `get_source_metadata`.
        :raises TemplateDoesNotExist: If the user doesn't own the template anymore,
            or it's marked for deletion.
        :raises TemplateChangedDuringUpdate: If the template has a newer revision
            than `base_revision`.
        :raises InvalidTemplateIcon: If the icon isn't allowed.
        :raises InvalidTemplateCategory: If no category is given while there are
            some, or one of them doesn't exist.
        :raises ValidationError: If the revision isn't valid.
        :return: The created revision.
        """

        with transaction.atomic():
            require_approval = self.read_require_approval()
            root = self.get_own_template(user, root.id, for_update=True)
            latest_revision = self.get_latest_revision(root)
            if base_revision is None or latest_revision.id != base_revision.id:
                raise TemplateChangedDuringUpdate(
                    "The template was changed while it was being updated."
                )

            categories = self.validate_icon_and_categories(icon, category_ids)
            revision = Template(
                type=root.type,
                root=root,
                version=latest_revision.version + 1,
                slug="",
                name=name,
                description=description,
                icon=icon,
                workspace=workspace,
                archive=archive,
                metadata=metadata or {},
            )
            revision.full_clean(exclude=["open_application"])
            revision.save()
            revision.categories.set(categories)
            # See `create_template_root`.
            workspace.save(update_fields=["updated_on"])
            step = self.update_review_step(latest_revision)
            if step == "submit":
                self.submit_revision(root, revision, require_approval=require_approval)
            elif step == "move":
                self._move_review(latest_revision, revision)

        return revision

    def serialize_applications(
        self,
        applications: List[Application],
        config: ImportExportConfig,
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict[str, Any]]:
        """
        Serializes the applications in memory, each one in its own consistent
        snapshot, so that they can be imported with
        `CoreHandler.import_applications_to_workspace`. Like a duplicate, the
        copy refers to the same user files, so no file is exported.

        :param applications: The applications to serialize.
        :param config: The configuration of the copy.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :return: The serialized applications.
        """

        progress = ChildProgressBuilder.build(
            progress_builder, child_total=max(len(applications), 1)
        )
        serialized = []
        for application in applications:
            application = application.specific
            application_type = application_type_registry.get_by_model(application)
            with application_type.export_safe_transaction_context(application):
                serialized.append(
                    application_type.export_serialized(application, config)
                )
            progress.increment()
        return serialized

    def copy_applications(
        self,
        owner: AbstractUser,
        applications: List[Application],
        *,
        name: str,
        progress_builder: Optional[ChildProgressBuilder] = None,
        track_content: Optional[Callable[..., None]] = None,
    ) -> Workspace:
        """
        Copies the applications into a new workspace nobody is a member of, which
        becomes the content of a user template.

        Each application is copied in its own transaction, so a failure rolls back
        only the application being copied. `track_content` is called with the
        `template_workspace` as soon as it exists, so that the caller can remove
        it with `delete_content_without_template`.

        :param owner: The user who creates the template.
        :param applications: The applications copied into the template.
        :param name: The name of the template, also given to the workspace.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :param track_content: Called with the content created so far as keyword
            arguments.
        :return: The workspace holding the copy.
        """

        if track_content is None:

            def track_content(**content):
                pass

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        # Nobody is a member of the new workspace, so the import drops what
        # belongs to the users of the source: personal views and collaborators.
        config = user_template_copy_config()

        workspace = Workspace.objects.create(name=name)
        track_content(template_workspace=workspace)

        serialized = self.serialize_applications(
            applications,
            config,
            progress_builder=progress.create_child_builder(represents_progress=50),
        )
        CoreHandler().import_applications_to_workspace(
            workspace,
            serialized,
            None,
            config,
            progress_builder=progress.create_child_builder(represents_progress=50),
            atomic_per_application=True,
        )

        return workspace

    def serialize_template_content(
        self,
        revision: Template,
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Dict[str, Any]]:
        """
        Serializes the applications of a revision of a user template, so that
        they can be installed with `install_template_content`. Each application
        is serialized in its own snapshot, so this must not be called inside an
        atomic block.

        :param revision: The revision to serialize.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :raises TemplateHasNoContent: If the revision has no application to copy.
            An install of nothing would leave no trace that it committed.
        :return: The serialized applications.
        """

        return self.serialize_applications(
            self._get_content_applications(revision),
            user_template_copy_config(),
            progress_builder=progress_builder,
        )

    def _get_content_applications(self, revision: Template) -> List[Application]:
        """
        Returns the applications holding the content of a revision, in their order.

        :param revision: The revision of a user template.
        :raises TemplateHasNoContent: If the revision has no application.
        :return: The applications in the workspace of the revision.
        """

        applications = (
            list(
                Application.objects.filter(workspace_id=revision.workspace_id).order_by(
                    "order", "id"
                )
            )
            if revision.has_content
            else []
        )
        if not applications:
            raise TemplateHasNoContent(
                f"The template {revision.family_id} has no content."
            )
        return applications

    def build_template_archive(
        self,
        revision: Template,
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> None:
        """
        Builds the downloadable archive of a revision of a user template: a zip
        file that can be imported into a workspace, holding what an install of the
        revision would copy. It's stored in the directory of the revision, with a
        name stamped with the current version, see `has_valid_archive`.

        The applications are exported in their own snapshots, so this must not be
        called inside an atomic block.

        :param revision: The revision whose archive is built.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :raises TemplateHasNoContent: If the revision has no application to copy.
        :raises TemplateDoesNotExist: If the revision was deleted meanwhile. The
            archive is deleted then.
        """

        from baserow.core.import_export.handler import ImportExportHandler

        applications = self._get_content_applications(revision)
        name = new_template_archive_name(revision.id)

        try:
            ImportExportHandler().write_applications_archive(
                applications,
                user_template_copy_config(),
                name,
                get_default_storage(),
                progress_builder=progress_builder,
            )
            saved_name = self._save_template_archive_name(revision, name)
        except Exception:
            # Nothing refers to the file yet.
            delete_template_archive_file(name)
            raise

        if saved_name != name:
            # Another build saved a valid archive meanwhile, so nothing refers to
            # this one.
            delete_template_archive_file(name)
        revision.archive.name = saved_name

    def _save_template_archive_name(self, revision: Template, name: str) -> str:
        """
        Saves the name of the archive just built for a revision, unless another
        build saved a valid one meanwhile, and deletes the replaced archive once
        that commits. The revision is locked, so that overlapping builds keep one
        valid archive and never delete each other's files.

        :param revision: The revision the archive was built for.
        :param name: The name of the archive just built.
        :raises TemplateDoesNotExist: If the revision was deleted.
        :return: The name of the archive the revision refers to now, which is
            `name` unless another build saved a valid one first.
        """

        with transaction.atomic():
            current_names = list(
                Template.objects.select_for_update(no_key=True)
                .filter(id=revision.id)
                .values_list("archive", flat=True)
            )
            if not current_names:
                raise TemplateDoesNotExist(
                    f"The template revision {revision.id} does not exist."
                )
            current_name = current_names[0]
            if current_name and is_valid_template_archive(revision.id, current_name):
                return current_name

            # Neither `updated_on`, nor `install_count`, are changed.
            Template.objects.filter(id=revision.id).update(archive=name)
            if current_name:
                # Kept while another template refers to it, like a revision that
                # only changed the details.
                transaction.on_commit(
                    lambda: self.delete_content_without_template(None, current_name),
                    robust=True,
                )
        return name

    def install_template_content(
        self,
        user: AbstractUser,
        workspace: Workspace,
        revision: Template,
        content: List[Dict[str, Any]],
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Installs the serialized content of a revision of a user template into a
        workspace and counts the install on the root of the template. It must be
        called inside an atomic block, so that a failure leaves nothing behind and
        the count is bumped only with a successful install.

        :param user: The user who installs the template.
        :param workspace: The workspace the applications are installed into.
        :param revision: The installed revision, see `serialize_template_content`.
        :param content: The content returned by `serialize_template_content`.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :return: The installed applications.
        """

        # Unlike the copy into the template, the installed tables are used right
        # away, so their search data is filled in like with the official install.
        config = dataclasses.replace(
            user_template_copy_config(), reduce_disk_space_usage=False
        )
        applications, _ = CoreHandler().import_applications_to_workspace(
            workspace,
            content,
            None,
            config,
            progress_builder=progress_builder,
        )

        CoreHandler().mark_applications_installed_from_template(
            user, applications, revision
        )

        # Only user templates count their installs. An update doesn't lose a
        # concurrent install.
        Template.objects.filter(pk=revision.family_id).update(
            install_count=F("install_count") + 1
        )

        return applications

    def get_own_template(
        self, user: AbstractUser, template_id: int, *, for_update: bool = False
    ) -> Template:
        """
        Returns a user template the user owns, so that they can manage it. Instance
        admins don't own the templates of others, and a blocked template can still
        be managed by its owner.

        :param user: The user who must own the template.
        :param template_id: The id of the template, which is its root.
        :param for_update: Locks the root until the end of the transaction.
        :raises TemplateDoesNotExist: If the template doesn't exist, isn't a root,
            isn't owned by the user, or is marked for deletion.
        :return: The root of the template.
        """

        queryset = Template.objects.all()
        if for_update:
            queryset = queryset.select_for_update()

        try:
            # Only the root of a user template has an owner, see the
            # `core_template_row_role` and `core_template_official_no_owner`
            # constraints.
            return queryset.get(
                id=template_id,
                owner=user,
                marked_for_deletion_at__isnull=True,
            )
        except Template.DoesNotExist as exc:
            raise TemplateDoesNotExist(
                f"The template {template_id} does not exist."
            ) from exc

    def get_template_for_deletion(
        self, user: AbstractUser, template_id: int
    ) -> Template:
        """
        Returns a user template the user can delete, locked until the end of the
        transaction. Its owner can delete it in any state, blocked included, and an
        instance admin can delete any user template. This is the rule the admin
        templates page (#6322) reuses.

        :param user: The user who deletes the template.
        :param template_id: The id of the template, which is its root.
        :raises TemplateDoesNotExist: If the template doesn't exist, isn't the root
            of a user template, is marked for deletion already, or the user is
            neither its owner nor an instance admin.
        :return: The locked root of the template.
        """

        return self._get_locked_user_root(
            template_id, owner=None if is_instance_admin(user) else user
        )

    def _get_template_for_moderation(
        self, admin: AbstractUser, template_id: int
    ) -> Template:
        """
        Returns the locked root of a user template to review, block or unblock.

        :param admin: The user who moderates the template.
        :param template_id: The id of the template, which is its root.
        :raises IsNotAdminError: If the user isn't an instance admin.
        :raises TemplateDoesNotExist: If the template doesn't exist, isn't the root
            of a user template or is marked for deletion.
        :return: The locked root of the template.
        """

        if not is_instance_admin(admin):
            raise IsNotAdminError()
        return self._get_locked_user_root(template_id)

    def _get_locked_user_root(
        self, template_id: int, owner: Optional[AbstractUser] = None
    ) -> Template:
        """
        Returns the locked root of a user template not marked for deletion.

        :param template_id: The id of the template, which is its root.
        :param owner: The user who must own the template, if any.
        :raises TemplateDoesNotExist: If there is no such template.
        :return: The locked root.
        """

        queryset = Template.objects.user().filter(
            id=template_id,
            root__isnull=True,
            marked_for_deletion_at__isnull=True,
        )
        if owner is not None:
            queryset = queryset.filter(owner=owner)

        try:
            return queryset.select_for_update().get()
        except Template.DoesNotExist as exc:
            raise TemplateDoesNotExist(
                f"The template {template_id} does not exist."
            ) from exc

    def list_templates_for_admin(self, state: UserTemplateState) -> QuerySet[Template]:
        """
        Returns the annotated rows of a tab of the admin page.

        :param state: The tab, one of `USER_TEMPLATE_ADMIN_STATES`, or the state of
            a template an admin unblocked.
        :return: The rows of the tab.
        """

        queue = Template.objects.review_queue()
        if state == UserTemplateState.PUBLIC:
            in_queue = queue.filter(
                Q(id=OuterRef("family_id")) | Q(root_id=OuterRef("family_id"))
            )
            rows = (
                Template.objects.user()
                .public_revisions()
                .filter_by_root(marked_for_deletion_at__isnull=True)
                .alias(family_id=Coalesce("root_id", "id"))
                .filter(~Exists(in_queue))
                .annotate(can_approve=Value(False), edited_since_submitted=Value(False))
            )
        elif state in [UserTemplateState.IN_REVIEW, UserTemplateState.REJECTED]:
            rows = queue.filter(
                review_state=Template.ReviewState.PENDING
                if state == UserTemplateState.IN_REVIEW
                else Template.ReviewState.REJECTED
            ).with_can_approve()
        else:
            rows = (
                Template.objects.user()
                .filter_by_root(marked_for_deletion_at__isnull=True)
                .latest_revisions()
                .with_template_state()
                .filter(template_state=state)
                .annotate(can_approve=Value(False), edited_since_submitted=Value(False))
            )

        return rows.annotate(
            admin_state=Value(state, output_field=CharField()),
            author_name=Case(
                When(root__isnull=True, then=author_name_expression("author")),
                default=author_name_expression("root__author"),
            ),
            # A revision isn't changed after it's created.
            template_updated_on=F("created_on"),
            template_install_count=Coalesce(
                F("root__install_count"), F("install_count")
            ),
        ).select_related("author", "root__author")

    def count_templates_for_admin(self) -> Dict[str, int]:
        """
        Counts the rows of each tab of the admin page.

        :return: The number of rows of each tab, by state.
        """

        return {
            state: self.list_templates_for_admin(state).count()
            for state in USER_TEMPLATE_ADMIN_STATES
        }

    def mark_template_for_deletion(self, root: Template) -> None:
        """
        Marks a user template for deletion, which hides it from everybody right
        away. The template is removed later. The updates of it that didn't commit
        yet are cancelled, so that none of them runs once the template is gone. A
        job created right before the mark is refused when it commits instead.

        Must run in the transaction that locked the root with
        `get_template_for_deletion`, so that an update can't commit in between.

        :param root: The root of the template, locked.
        """

        from baserow.core.user_templates.models import CreateUserTemplateJob

        root.marked_for_deletion_at = timezone.now()
        Template.objects.filter(id=root.id).update(
            marked_for_deletion_at=root.marked_for_deletion_at
        )

        jobs = CreateUserTemplateJob.objects.filter(
            template=root, revision__isnull=True
        ).is_pending_or_running()
        for job in jobs:
            try:
                JobHandler.cancel_job(job)
            except JobNotCancellable:
                # It ended, or committed, between the query and the lock.
                pass

    def get_user_template_root(self, template_id: int) -> Optional[Template]:
        """
        Returns the root of a user template that isn't marked for deletion, which
        is what the id of a user template refers to when it's installed or
        downloaded. Access isn't checked here.

        :param template_id: The id of the template.
        :return: The root, or None for the id of a revision, of an official
            template, of a template marked for deletion, or an unknown id.
        """

        return self._get_user_template_roots().filter(id=template_id).first()

    def get_user_template_root_by_slug(self, slug: str) -> Optional[Template]:
        """
        Returns the root of a user template that isn't marked for deletion by its
        slug, which only the root of a template has. Access isn't checked here.

        :param slug: The slug of the template.
        :return: The root, or None for the slug of an official template, of a
            template marked for deletion, or an unknown slug.
        """

        return self._get_user_template_roots().filter(slug=slug).first()

    def _get_user_template_roots(self) -> QuerySet[Template]:
        """
        Returns the roots of the user templates that aren't marked for deletion.

        :return: A queryset of the roots.
        """

        return Template.objects.user().filter(
            root__isnull=True, marked_for_deletion_at__isnull=True
        )

    def get_latest_revision(self, root: Template) -> Template:
        """
        Returns the latest revision of a template, which is the root itself until
        the template is updated.

        :param root: The root of the template.
        :return: The revision with the highest version, with its root selected.
        """

        return (
            Template.objects.filter(Q(id=root.id) | Q(root=root))
            .select_related("root")
            .order_by("-version")
            .first()
        )

    def get_latest_revision_of_locked_root(self, root: Template) -> Template:
        """
        Returns the latest revision of a template, with the locked `root` set as
        its root, so that the state read through it is the locked one.

        :param root: The root of the template, locked.
        :return: The latest revision, with `root` as its root.
        """

        revision = self.get_latest_revision(root)
        if revision.id == root.id:
            return root
        revision.root = root
        return revision

    def read_require_approval(self) -> bool:
        """
        Whether user templates need approval. Locks the settings row FOR SHARE
        until the transaction ends, so approval can't be switched off before the
        submit commits. Call it before locking the root: switching approval off
        locks the settings row, then the roots.

        :return: The value of `Settings.user_templates_require_approval`.
        """

        # Raw SQL, as the ORM has no `FOR SHARE`.
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_templates_require_approval FROM core_settings "
                "ORDER BY id LIMIT 1 FOR SHARE"
            )
            row = cursor.fetchone()
        if row is None:
            return Settings._meta.get_field(
                "user_templates_require_approval"
            ).get_default()
        return row[0]

    def submit_revision(
        self, root: Template, revision: Template, *, require_approval: bool
    ) -> bool:
        """
        Lists a revision, or sends it to review. The caller checks the owner and
        the content, and holds the lock of the root.

        :param root: The root of the template, locked.
        :param revision: The revision to submit, the root itself for revision 1.
        :param require_approval: Whether a revision needs the approval of an
            admin, see `read_require_approval`.
        :return: Whether the revision is listed, otherwise it's in review.
        """

        Template.objects.filter(Q(id=root.id) | Q(root=root)).exclude(
            id=revision.id
        ).filter(review_state=Template.ReviewState.PENDING).update(
            review_state=Template.ReviewState.WITHDRAWN
        )
        revision.submitted_on = timezone.now()
        if self.submit_needs_review(revision, require_approval):
            revision.review_state = Template.ReviewState.PENDING
            revision.save(update_fields=["review_state", "submitted_on"])
            return False

        self._approve_revisions(
            [(revision.id, revision.root_id)], None, submitted_on=revision.submitted_on
        )
        return True

    def submit_needs_review(self, revision: Template, require_approval: bool) -> bool:
        """
        Whether a submitted revision waits for review: approval is required, or
        the template was rejected since its last approval.

        :param revision: The revision, see `get_template_state`.
        :param require_approval: Whether approval is required, see
            `read_require_approval`.
        :return: True if the revision waits for review.
        """

        return (
            require_approval
            or self._get_template_state_fields(revision)["has_open_rejection"]
        )

    def _approve_revisions(
        self,
        revisions: List[Tuple[int, Optional[int]]],
        reviewer: Optional[AbstractUser],
        rejected_template_ids: Optional[List[int]] = None,
        **fields: Any,
    ) -> None:
        """
        Approves and lists revisions, at most one per template, in bulk, and
        closes the rejections of those templates. The caller holds the locks of
        the roots.

        :param revisions: The id and the root id of each revision, the root id
            None for revision 1, which is the root.
        :param reviewer: The admin who approves them, None when they need no
            review. A revision approved already, listed again, keeps its review.
        :param rejected_template_ids: The root ids of the templates with a reject
            reason to clear, all of them when None.
        :param fields: Other values to write to the revisions, by field name.
        """

        approved = Q(review_state=Template.ReviewState.APPROVED)
        values = {
            "review_state": Template.ReviewState.APPROVED,
            "reviewed_on": Case(
                When(approved, then=F("reviewed_on")), default=Value(timezone.now())
            ),
            "reviewed_by_id": Case(
                When(approved, then=F("reviewed_by_id")),
                default=Value(reviewer.id if reviewer else None),
            ),
            **fields,
        }
        first_ids = [revision_id for revision_id, root_id in revisions if not root_id]
        edit_ids = [revision_id for revision_id, root_id in revisions if root_id]
        Template.objects.filter(id__in=first_ids).update(
            **values, public_revision_id=F("id")
        )
        Template.objects.filter(id__in=edit_ids).update(**values)
        Template.objects.filter(
            id__in=[root_id for _, root_id in revisions if root_id]
        ).update(
            public_revision_id=Subquery(
                Template.objects.filter(root_id=OuterRef("id"), id__in=edit_ids)
                .order_by()
                .values("id")[:1]
            )
        )
        if rejected_template_ids is None:
            rejected_template_ids = [
                root_id or revision_id for revision_id, root_id in revisions
            ]
        if rejected_template_ids:
            Template.objects.filter(
                Q(id__in=rejected_template_ids) | Q(root_id__in=rejected_template_ids)
            ).exclude(reject_reason="").update(reject_reason="")

    def _get_revision_for_review(
        self,
        admin: AbstractUser,
        template_id: int,
        revision_id: int,
        seen_state: UserTemplateState,
        seen_listed: bool,
        seen_reviewed_on: Optional[datetime],
        can_review: Callable[[UserTemplateState, bool], bool],
    ) -> Template:
        """
        Returns the revision an admin reviews, with its root locked, if the
        template is still as the admin saw it.

        :param admin: The admin who reviews the template.
        :param template_id: The id of the template, which is its root.
        :param revision_id: The id of the revision the admin reviewed.
        :param seen_state: The state of the template the admin reviewed.
        :param seen_listed: Whether the template the admin reviewed was listed.
        :param seen_reviewed_on: When the revision the admin reviewed was last
            reviewed, None if never.
        :param can_review: Whether the review applies to a template in a state,
            listed or not.
        :raises IsNotAdminError: See `_get_template_for_moderation`.
        :raises TemplateDoesNotExist: See `_get_template_for_moderation`.
        :raises TemplateBlocked: If the template is blocked.
        :raises TemplateAlreadyApproved: If the template is public now, while the
            admin saw it in another state.
        :raises TemplateAlreadyRejected: If the template was rejected, or taken
            out of the listing, since.
        :raises TemplateUpdated: If the template isn't in `seen_state` or
            `seen_listed` anymore, its row is another revision now, or the
            revision was reviewed since.
        :raises TemplateNotReviewable: If the review doesn't apply to the template.
        :return: The revision, annotated with `edited_since_submitted` and
            `can_approve`.
        """

        root = self._get_template_for_moderation(admin, template_id)
        if root.blocked_at is not None:
            raise TemplateBlocked(f"The template {template_id} is blocked.")

        state, _ = self.get_template_state(root)
        listed = self.is_listed(root)
        if (state, listed) != (seen_state, seen_listed):
            message = (
                f"The template {template_id} is {state} and listed: {listed}, not "
                f"{seen_state} and listed: {seen_listed}."
            )
            if state == UserTemplateState.PUBLIC:
                raise TemplateAlreadyApproved(message)
            if state == UserTemplateState.REJECTED:
                raise TemplateAlreadyRejected(message)
            raise TemplateUpdated(message)
        if not can_review(state, listed):
            raise TemplateNotReviewable(
                f"The template {template_id} can't be reviewed while {state} and "
                f"listed: {listed}."
            )

        revisions = (
            Template.objects.filter(id=root.public_revision_id)
            if state == UserTemplateState.PUBLIC
            else Template.objects.review_queue().filter_by_root(id=root.id)
        )
        revision = revisions.with_can_approve().get()
        if revision.id != revision_id:
            raise TemplateUpdated(
                f"The revision {revision_id} isn't the one in review of the template "
                f"{template_id}."
            )
        if revision.reviewed_on != seen_reviewed_on:
            raise TemplateUpdated(
                f"The revision {revision_id} of the template {template_id} was "
                "reviewed since."
            )
        if revision.id != root.id:
            revision.root = root
        return revision

    def approve_template(
        self,
        admin: AbstractUser,
        template_id: int,
        revision_id: int,
        seen_state: UserTemplateState,
        seen_listed: bool,
        seen_reviewed_on: Optional[datetime],
    ) -> Template:
        """
        Approves and lists the reviewed revision. Must run in a transaction.

        :param admin: The instance admin who approves the template.
        :param template_id: The id of the template, which is its root.
        :param revision_id: The id of the revision the admin reviewed.
        :param seen_state: The state of the template the admin reviewed.
        :param seen_listed: Whether the template the admin reviewed was listed.
        :param seen_reviewed_on: When the revision the admin reviewed was last
            reviewed, None if never.
        :raises TemplateHasNoContent: If the revision has no content.
        :raises TemplateUpdated: If the template was edited since the revision was
            submitted, see `TemplateQuerySet.with_can_approve`.
        :raises: See `_get_revision_for_review`.
        :return: The approved revision.
        """

        revision = self._get_revision_for_review(
            admin,
            template_id,
            revision_id,
            seen_state,
            seen_listed,
            seen_reviewed_on,
            lambda state, listed: self.approve_applies(state),
        )
        if revision.edited_since_submitted:
            raise TemplateUpdated(
                f"The template {template_id} was edited after revision "
                f"{revision_id} was submitted."
            )
        if not revision.can_approve:
            raise TemplateHasNoContent(f"The template {template_id} has no content.")

        self._approve_revisions([(revision.id, revision.root_id)], admin)
        return revision

    def reject_template(
        self,
        admin: AbstractUser,
        template_id: int,
        revision_id: int,
        reason: str,
        seen_state: UserTemplateState,
        seen_listed: bool,
        seen_reviewed_on: Optional[datetime],
    ) -> tuple[Template, bool]:
        """
        Rejects a user template. Must run in a transaction.

        :param admin: The instance admin who rejects the template.
        :param template_id: The id of the template, which is its root.
        :param revision_id: The id of the revision the admin reviewed.
        :param reason: Why the template is rejected.
        :param seen_state: The state of the template the admin reviewed.
        :param seen_listed: Whether the template the admin reviewed was listed.
        :param seen_reviewed_on: When the revision the admin reviewed was last
            reviewed, None if never.
        :raises TemplateRejectReasonRequired: If the reason is blank.
        :raises: See `_get_revision_for_review`.
        :return: The rejected revision, and whether the template was taken out of
            the listing.
        """

        if not reason.strip():
            raise TemplateRejectReasonRequired("A reject reason is required.")

        revision = self._get_revision_for_review(
            admin,
            template_id,
            revision_id,
            seen_state,
            seen_listed,
            seen_reviewed_on,
            self.reject_applies,
        )
        unlisted = self.reject_unlists(seen_state, seen_listed)
        if unlisted:
            self.withdraw_listing(revision.get_root())

        revision.review_state = Template.ReviewState.REJECTED
        revision.reject_reason = reason
        revision.reviewed_by = admin
        revision.reviewed_on = timezone.now()
        revision.save(
            update_fields=[
                "review_state",
                "reject_reason",
                "reviewed_by",
                "reviewed_on",
            ]
        )
        return revision, unlisted

    def approve_pending_revisions(self, admin: AbstractUser) -> int:
        """
        Approves the pending revisions an admin could approve, except on templates
        rejected since their last approval, when approval is switched off. Must run
        in the transaction that updated the settings row, see
        `read_require_approval`.

        :param admin: The instance admin who switched approval off.
        :return: The number of approved revisions.
        """

        pending = (
            Template.objects.review_queue()
            .approvable()
            .filter(review_state=Template.ReviewState.PENDING)
            .with_template_state()
            .filter(has_open_rejection=False)
        )
        # Locked before the pending revisions are read, so they can't change until
        # approved. None joins the queue meanwhile: submits hold the settings row
        # FOR SHARE, which this transaction updated.
        list(
            Template.objects.filter(
                id__in=pending.annotate(
                    pending_root_id=Coalesce("root_id", "id")
                ).values("pending_root_id")
            )
            .order_by("id")
            .select_for_update()
            .values_list("id", flat=True)
        )
        has_reject_reason = Exists(
            Template.objects.filter(
                Q(id=OuterRef("family_id")) | Q(root_id=OuterRef("family_id"))
            ).exclude(reject_reason="")
        )
        rows = list(
            pending.annotate(has_reject_reason=has_reject_reason).values_list(
                "id", "root_id", "has_reject_reason"
            )
        )
        self._approve_revisions(
            [(revision_id, root_id) for revision_id, root_id, _ in rows],
            admin,
            rejected_template_ids=[
                root_id or revision_id
                for revision_id, root_id, rejected in rows
                if rejected
            ],
        )
        return len(rows)

    def withdraw_review(self, root: Template) -> Optional[Template]:
        """
        Withdraws the open review of a user template, keeping a reject reason.
        When the root is the revision withdrawn, only `root` is changed and the
        caller saves it. The caller checks the user, unlists it, and holds the
        lock of the root.

        :param root: The root of the template, locked.
        :return: The withdrawn revision, or None if none was in review or rejected.
        """

        revision = Template.objects.open_reviews().filter_by_root(id=root.id).first()
        if revision is None:
            return None
        if revision.id == root.id:
            root.review_state = Template.ReviewState.WITHDRAWN
            return root
        revision.review_state = Template.ReviewState.WITHDRAWN
        revision.save(update_fields=["review_state"])
        return revision

    def _move_review(self, previous: Template, revision: Template) -> None:
        """
        Moves the review to the new revision. Runs under the lock of the root.

        :param previous: The revision in review.
        :param revision: The new revision.
        """

        previous.review_state = Template.ReviewState.WITHDRAWN
        previous.save(update_fields=["review_state"])
        revision.review_state = Template.ReviewState.PENDING
        revision.submitted_on = timezone.now()
        revision.save(update_fields=["review_state", "submitted_on"])

    def withdraw_listing(self, root: Template) -> None:
        """
        Clears the public revision of a user template. The caller checks the user
        and holds the lock of the root.

        :param root: The root of the template, locked.
        """

        root.public_revision = None
        root.save(update_fields=["public_revision"])

    def make_template_private(
        self, root: Template, update_fields: Iterable[str] = ()
    ) -> Optional[int]:
        """
        Makes a user template private, as its owner does and as unblocking it does.
        A listed revision stays approved. The root is saved once, with the
        `update_fields` the caller changed on it. The caller checks the user and
        holds the lock of the root.

        :param root: The root of the template, locked.
        :param update_fields: The fields of the root the caller changed.
        :return: The id of the revision that was listed, otherwise the id of the
            revision withdrawn from review, otherwise None.
        """

        self.drop_scheduled_make_public(root)
        root_fields = list(update_fields)
        public_revision_id = root.public_revision_id
        if public_revision_id is not None:
            root.public_revision = None
            root_fields.append("public_revision")
        withdrawn = self.withdraw_review(root)
        if withdrawn is root:
            root_fields.append("review_state")
        if root_fields:
            root.save(update_fields=root_fields)

        if public_revision_id is not None:
            return public_revision_id
        return withdrawn.id if withdrawn is not None else None

    def block_template(
        self, admin: AbstractUser, template_id: int, reason: str
    ) -> Template:
        """
        Blocks a user template in any state. Blocking it again changes the reason
        and who blocked it, and keeps when. Must run in a transaction.

        :param admin: The instance admin who blocks the template.
        :param template_id: The id of the template, which is its root.
        :param reason: Why the template is blocked, which its author sees.
        :raises TemplateBlockReasonRequired: If the reason is blank.
        :raises: See `_get_template_for_moderation`.
        :return: The latest revision of the template.
        """

        if not reason.strip():
            raise TemplateBlockReasonRequired("A block reason is required.")

        root = self._get_template_for_moderation(admin, template_id)
        if root.blocked_at is None:
            root.blocked_at = timezone.now()
        root.blocked_by = admin
        root.blocked_reason = reason
        root.save(update_fields=["blocked_at", "blocked_by", "blocked_reason"])
        return self.get_latest_revision_of_locked_root(root)

    def unblock_template(
        self, admin: AbstractUser, template_id: int
    ) -> tuple[Template, bool]:
        """
        Lifts the block of a user template, which makes it private. Must run in a
        transaction.

        :param admin: The instance admin who unblocks the template.
        :param template_id: The id of the template, which is its root.
        :raises: See `_get_template_for_moderation`.
        :return: The latest revision of the template, and whether it was blocked.
        """

        root = self._get_template_for_moderation(admin, template_id)
        latest = self.get_latest_revision_of_locked_root(root)
        if root.blocked_at is None:
            return latest, False

        root.blocked_at = None
        root.blocked_by = None
        root.blocked_reason = ""
        self.make_template_private(
            root, update_fields=["blocked_at", "blocked_by", "blocked_reason"]
        )
        return latest, True

    def drop_scheduled_make_public(self, root: Template) -> None:
        """
        Stops the unfinished create user template jobs of a template from making it
        public once their revision is committed, because its owner made it private
        since. The caller holds the lock of the root, which such a job takes before
        it reads whether it still makes the template public, see
        `UserTemplateService.update_visibility`.

        :param root: The root of the template, locked.
        """

        from baserow.core.user_templates.models import CreateUserTemplateJob

        CreateUserTemplateJob.objects.filter(
            template=root, make_public=True
        ).is_pending_or_running().update(make_public=False)

    def set_private_link(self, root: Template, enabled: bool) -> bool:
        """
        Creates or turns off the private link of a user template. Turning it off
        takes the access away from everybody who has the link. A link that exists
        is kept. The template itself, its slug and its visibility don't change. The
        caller checks the owner and that the template isn't blocked, and holds the
        lock of the root.

        :param root: The root of the template, locked.
        :param enabled: Whether the template must have a private link.
        :return: Whether the link was created or turned off.
        """

        if (root.private_link_token is not None) == enabled:
            return False
        root.private_link_token = secrets.token_hex(32) if enabled else None
        # Not an update of the template, so `updated_on` stays.
        root.save(update_fields=["private_link_token"])
        return True

    def rotate_private_link(self, root: Template) -> bool:
        """
        Replaces the token of the private link of a user template, which takes the
        access away from everybody who has the old link. A template without a link
        keeps having none, so that a link that was just turned off isn't turned on
        again. Like `set_private_link`, nothing else changes, and the caller checks
        the owner and the block and holds the lock.

        :param root: The root of the template, locked.
        :return: Whether the token was replaced.
        """

        if root.private_link_token is None:
            return False
        root.private_link_token = secrets.token_hex(32)
        root.save(update_fields=["private_link_token"])
        return True

    def _get_install_access(
        self,
        user: AbstractUser,
        root: Template,
        private_link_token: Optional[str] = None,
    ) -> Optional[InstallAccess]:
        """
        Why the user may install a user template. The caller checks whether it's
        marked for deletion.

        :param user: The user who installs the template.
        :param root: The root of the template.
        :param private_link_token: The token of the private link the user opened
            the template through, if any.
        :return: None without access.
        """

        if not user.is_active:
            return None
        if root.owner_id == user.id:
            return InstallAccess.OWNER
        if user.is_staff:
            return InstallAccess.INSTANCE_ADMIN
        if self.is_listed(root):
            return InstallAccess.LISTED
        if root.blocked_at is None and self._private_link_matches(
            root, private_link_token
        ):
            return InstallAccess.PRIVATE_LINK
        return None

    def _private_link_matches(self, root: Template, token: Optional[str]) -> bool:
        """
        Whether the token is the one of the private link of a user template.

        :param root: The root of the template.
        :param token: The token sent with the request, if any.
        :return: False if the template has no private link or there's no token.
        """

        return (
            root.private_link_token is not None
            and token is not None
            # Compared as bytes, so that a non-ASCII token is a mismatch too.
            and secrets.compare_digest(token.encode(), root.private_link_token.encode())
        )

    def _check_install_access(
        self,
        user: AbstractUser,
        root: Template,
        latest: bool = False,
        private_link_token: Optional[str] = None,
    ) -> InstallAccess:
        """
        Raises if the user may not install the template: TemplateDoesNotExist
        without access, or when asking for the `latest` revision without owning
        it, before TemplateBlocked for a blocked owner who isn't an instance admin.

        :return: Why the user may install the template.
        """

        access = self._get_install_access(user, root, private_link_token)
        if access is None or (latest and access != InstallAccess.OWNER):
            raise TemplateDoesNotExist(f"The template {root.id} does not exist.")
        if (
            access == InstallAccess.OWNER
            and root.blocked_at is not None
            and not user.is_staff
        ):
            raise TemplateBlocked(f"The template {root.id} is blocked.")
        return access

    def get_installable_revision(
        self,
        user: AbstractUser,
        root: Template,
        latest: bool = False,
        private_link_token: Optional[str] = None,
    ) -> Template:
        """
        Returns the revision of a user template that the user installs: the
        latest one when asked for, which only its owner may, as from "Your
        templates". Otherwise the public revision, the same for everyone, or the
        latest one while it isn't public, for its owner, instance admins and the
        users with the token of its private link.

        :param user: The user who installs the template.
        :param root: The root of a user template that isn't marked for deletion.
        :param latest: Whether the latest revision is installed.
        :param private_link_token: The token of the private link the user opened
            the template through, if any.
        :raises TemplateDoesNotExist: If the user has no access to the template,
            or asks for the latest revision without owning it.
        :raises TemplateBlocked: If the user owns the template and it's blocked,
            unless they're an instance admin.
        :raises TemplateHasNoContent: If the revision has no application to copy.
        :return: The revision to install, with its root selected.
        """

        self._check_install_access(user, root, latest, private_link_token)
        if not latest and self.is_listed(root):
            # Fetched like the latest revision, even when it's the root, so that
            # the request costs the same whichever revision is public.
            revision = Template.objects.select_related("root").get(
                id=root.public_revision_id
            )
        else:
            revision = self.get_latest_revision(root)

        self._check_has_content(revision)
        return revision

    def _check_has_content(self, revision: Template) -> None:
        """
        Checks that a revision of a user template has content to copy.

        :param revision: The revision, with its root selected.
        :raises TemplateHasNoContent: If the revision has no application to copy.
        """

        if (
            not revision.has_content
            or not Application.objects.filter(
                workspace_id=revision.workspace_id
            ).exists()
        ):
            raise TemplateHasNoContent(
                f"The template {revision.family_id} has no content."
            )

    def get_downloadable_revision(
        self,
        user: AbstractUser,
        slug: str,
        revision_id: int,
        private_link_token: Optional[str] = None,
    ) -> Template:
        """
        Returns the revision of a user template whose archive the user downloads,
        which is the revision the user was shown. Its owner and an instance admin
        may download any revision of the template, anyone else only the one install
        picks, with the same access as install, see `get_installable_revision`.

        :param user: The user who downloads the template.
        :param slug: The slug of the template.
        :param revision_id: The id of the revision the user was shown.
        :param private_link_token: The token of the private link the user opened
            the template through, if any.
        :raises TemplateDoesNotExist: If there is no user template with the slug,
            the user may not download it, or its owner or an instance admin asks
            for a revision of another template.
        :raises TemplateBlocked: If the user owns the template and it's blocked,
            unless they're an instance admin.
        :raises TemplateUpdated: If the user neither owns the template nor is an
            instance admin, and the revision isn't the one install picks anymore.
        :raises TemplateHasNoContent: If the revision has no application to copy.
        :return: The revision, with its root selected.
        """

        root = self.get_user_template_root_by_slug(slug)
        if root is None:
            raise TemplateDoesNotExist(f"The template with slug {slug} does not exist.")
        access = self._check_install_access(
            user, root, private_link_token=private_link_token
        )
        revision = None
        if access == InstallAccess.LISTED:
            shown_revision_id = root.public_revision_id
        elif access == InstallAccess.PRIVATE_LINK:
            revision = self.get_latest_revision(root)
            shown_revision_id = revision.id
        else:
            shown_revision_id = revision_id
        if revision_id != shown_revision_id:
            raise TemplateUpdated(
                f"The template {root.id} was updated after revision {revision_id} "
                "was shown."
            )
        if revision is None:
            revision = (
                Template.objects.filter(Q(id=root.id) | Q(root=root), id=revision_id)
                .select_related("root")
                .first()
            )
        if revision is None:
            raise TemplateDoesNotExist(
                f"The revision {revision_id} of the template {root.id} does not exist."
            )
        self._check_has_content(revision)
        return revision

    def recheck_admitted_install_access(
        self, user: AbstractUser, revision: Template
    ) -> None:
        """
        Checks again, when an install or download job admitted earlier runs, that
        the user may still install the pinned revision. How the user was admitted
        isn't kept, so it's checked as if through the current private link:
        rotating the link doesn't stop the job; removing it does, unless the user
        has access otherwise.

        :param user: The user who installs the template.
        :param revision: The pinned revision, with its root selected.
        :raises TemplateDoesNotExist: If the user lost access to the template, or
            it's marked for deletion.
        :raises TemplateBlocked: If the user owns the template and it's blocked,
            unless they're an instance admin.
        """

        root = revision.get_root()
        if root.marked_for_deletion_at is not None:
            raise TemplateDoesNotExist(f"The template {root.id} does not exist.")
        self._check_install_access(
            user, root, private_link_token=root.private_link_token
        )

    def _lock_user(self, user: AbstractUser) -> bool:
        """
        Locks the row of the user until the end of the transaction. Creating a
        template and deleting its owner both lock it, so that a template is either
        committed before the deletion marks it, or not created at all.

        :return: Whether the user still exists.
        """

        return User.objects.select_for_update().filter(id=user.id).exists()

    def mark_owned_templates_for_deletion(self, user: AbstractUser) -> None:
        """
        Marks the user templates owned by the user for deletion. The templates
        themselves are removed later. Must run in the transaction deleting the
        user, see `_lock_user`.
        """

        self._lock_user(user)
        Template.objects.user().filter(
            owner=user, root__isnull=True, marked_for_deletion_at__isnull=True
        ).update(marked_for_deletion_at=timezone.now())

    def _get_template_state_fields(self, template: Template) -> Dict[str, Any]:
        """
        The state of the template of a row, from its annotations or one query.

        :param template: A revision of the template.
        :return: `template_state`, `last_submitted_reason` and
            `has_open_rejection`.
        """

        fields = ("template_state", "last_submitted_reason", "has_open_rejection")
        if hasattr(template, "template_state"):
            return {field: getattr(template, field) for field in fields}
        return (
            Template.objects.filter(id=template.id)
            .with_template_state()
            .values(*fields)
            .get()
        )

    def get_template_state(
        self, template: Template
    ) -> tuple[UserTemplateState, Optional[str]]:
        """
        Returns the state of a user template, with the admin's reason if any.

        :param template: A revision of the template, with its root, see
            `_get_template_state_fields`.
        :return: The state, and the reason if any.
        """

        fields = self._get_template_state_fields(template)
        state = fields["template_state"]
        reason = None
        if state == UserTemplateState.BLOCKED:
            reason = template.get_root().blocked_reason
        elif state == UserTemplateState.REJECTED:
            reason = fields["last_submitted_reason"]
        return state, reason or None

    def is_listed(self, template: Template) -> bool:
        """
        Whether a user template is listed, also while an edit is in review.

        :param template: A revision of the template, with its root.
        :return: True if it has a public revision and isn't blocked.
        """

        root = template.get_root()
        return root.public_revision_id is not None and root.blocked_at is None

    def approve_applies(self, state: UserTemplateState) -> bool:
        """
        Whether approving applies to a user template in a state.

        :param state: The state of the template.
        :return: True if it's in review or rejected.
        """

        return state in [UserTemplateState.IN_REVIEW, UserTemplateState.REJECTED]

    def reject_applies(self, state: UserTemplateState, listed: bool) -> bool:
        """
        Whether an admin can reject a user template in a state, listed or not.

        :param state: The state of the template.
        :param listed: Whether the template is listed, see `is_listed`.
        :return: True if it's in review or listed.
        """

        return state == UserTemplateState.IN_REVIEW or listed

    def reject_unlists(self, state: UserTemplateState, listed: bool) -> bool:
        """
        Whether rejecting a user template unlists it.

        :param state: The state of the template.
        :param listed: Whether the template is listed, see `is_listed`.
        :return: True if it's listed, unless only its edit is in review: then the
            listed revision stays.
        """

        return listed and state != UserTemplateState.IN_REVIEW

    def make_public_submits(self, latest: Template) -> bool:
        """
        Whether making a user template public submits its latest revision.

        :param latest: The latest revision of the template, with its root.
        :return: True if it's submitted, see `submit_revision`.
        """

        root = latest.get_root()
        return (
            root.blocked_at is None
            and root.public_revision_id != latest.id
            and latest.review_state != Template.ReviewState.PENDING
        )

    def make_public_needs_review(
        self, latest: Template, require_approval: bool
    ) -> bool:
        """
        Whether making a user template public sends it to the review of an admin.

        :param latest: The latest revision of the template, see
            `get_template_state`.
        :param require_approval: Whether approval is required, see
            `read_require_approval`.
        :return: True if it's submitted and needs review, see
            `make_public_submits` and `submit_needs_review`.
        """

        return self.make_public_submits(latest) and self.submit_needs_review(
            latest, require_approval
        )

    def update_review_step(self, latest: Template) -> Optional[str]:
        """
        What an update of a user template does to its review. A blocked one
        keeps its review moving until unblocking withdraws it.

        :param latest: The latest revision of the template, with its root.
        :return: "submit", "move", or None when the review is left as it is.
        """

        if self.is_listed(latest):
            return "submit"
        if latest.review_state == Template.ReviewState.PENDING:
            return "move"
        return None

    def update_needs_review(self, latest: Template, require_approval: bool) -> bool:
        """
        Whether an update of a user template sends its new revision to review.
        A blocked one isn't reviewed.

        :param latest: The latest revision of the template, see
            `get_template_state`.
        :param require_approval: Whether approval is required, see
            `read_require_approval`.
        :return: True if the review moves to the new revision, or if it's
            submitted and needs review, see `update_review_step`.
        """

        if latest.get_root().blocked_at is not None:
            return False
        step = self.update_review_step(latest)
        return step == "move" or (
            step == "submit" and self.submit_needs_review(latest, require_approval)
        )

    def delete_content_without_template(
        self, workspace_id: Optional[int], archive_name: str
    ) -> None:
        """
        Permanently deletes the workspace and the archive copied by a job,
        unless a template points at them. A job that didn't commit its revision
        leaves them behind. Deleting twice does nothing.

        :param workspace_id: The id of the workspace holding the copy, if any.
        :param archive_name: The name of the stored archive, if any, or the
            directory of the archives of a revision, see `delete_template_archives`.
        """

        if (
            workspace_id is not None
            and not Template.objects.filter(workspace_id=workspace_id).exists()
        ):
            # It's called from the job hooks and the sweep, which run without a
            # transaction, and the deletion locks rows.
            with transaction.atomic():
                workspace = Workspace.objects_and_trash.filter(id=workspace_id).first()
                if workspace is not None:
                    TrashHandler.permanently_delete(workspace)

        if archive_name.endswith("/"):
            # The directory of the archives of a revision.
            delete_template_archives(archive_name)
        elif (
            archive_name and not Template.objects.filter(archive=archive_name).exists()
        ):
            delete_template_archive_file(archive_name)

    def delete_content_of_deleted_job(
        self, workspace_id: Optional[int], archive_name: str
    ) -> None:
        """
        Deletes the workspace and the archive of a job that is deleted, once
        the transaction deleting it commits. They're kept track of until then, and
        until their deletion succeeds, so that the sweep retries a failed one.

        :param workspace_id: The id of the workspace holding the copy, if any.
        :param archive_name: The name of the stored archive, if any.
        """

        from baserow.core.user_templates.models import UserTemplateContentToDelete

        if workspace_id is None and not archive_name:
            return

        content = UserTemplateContentToDelete.objects.create(
            workspace_id=workspace_id, archive_name=archive_name
        )
        transaction.on_commit(lambda: self._delete_tracked_content(content))

    def _delete_tracked_content(self, content) -> None:
        """
        Deletes the content a `UserTemplateContentToDelete` keeps track of, and the
        row once it's gone. A failure is logged, so that it doesn't stop deleting
        the rest, and the row is kept for the next sweep.
        """

        try:
            self.delete_content_without_template(
                content.workspace_id, content.archive_name
            )
        except SoftTimeLimitExceeded:
            raise
        except Exception:
            logger.exception(f"Deleting the user template content {content.id} failed.")
            return
        content.delete()

    def delete_marked_templates(self) -> None:
        """
        Permanently removes the user templates marked for deletion longer than
        `USER_TEMPLATE_DELETION_GRACE_PERIOD` ago, with their revisions, their
        ended jobs, and then their workspaces and archives. It runs whether or not
        user templates are enabled, because the templates of deleted users are
        marked too.

        At most `USER_TEMPLATE_PURGE_BATCH_SIZE` templates are removed per call,
        the ones deleted first first, so that the sweep running after it isn't
        starved. A template with a pending or running job is left out until the
        job ends. One that fails goes to the back, and is tried again after
        another grace period, so that it doesn't hold up the others.
        """

        from baserow.core.user_templates.models import (
            CreateUserTemplateJob,
            DownloadUserTemplateJob,
        )

        # Only leaves out what `_delete_marked_template` would skip, which checks
        # the jobs again once they're locked. The families with a pending or
        # running job are read once, rather than per template.
        create_jobs = CreateUserTemplateJob.objects.is_pending_or_running()
        install_jobs = InstallTemplateJob.objects.is_pending_or_running()
        download_jobs = DownloadUserTemplateJob.objects.is_pending_or_running()
        busy_root_ids = (
            Template.objects.filter(
                Q(id__in=create_jobs.values("template_id"))
                | Q(id__in=create_jobs.values("base_revision_id"))
                | Q(id__in=create_jobs.values("revision_id"))
                | Q(id__in=install_jobs.values("template_id"))
                | Q(id__in=download_jobs.values("revision_id"))
            )
            .annotate(family_id=Coalesce("root_id", "id"))
            .values("family_id")
        )
        cutoff = timezone.now() - USER_TEMPLATE_DELETION_GRACE_PERIOD
        root_ids = list(
            Template.objects.user()
            .filter(root__isnull=True, marked_for_deletion_at__lte=cutoff)
            .exclude(id__in=busy_root_ids)
            .order_by("marked_for_deletion_at", "id")
            .values_list("id", flat=True)[:USER_TEMPLATE_PURGE_BATCH_SIZE]
        )
        for root_id in root_ids:
            # One template that can't be removed must not block the others, but
            # running out of time must stop the task.
            try:
                self._delete_marked_template(root_id)
            except SoftTimeLimitExceeded:
                raise
            except Exception:
                logger.exception(f"Deleting the user template {root_id} failed.")
                Template.objects.filter(
                    id=root_id, marked_for_deletion_at__isnull=False
                ).update(marked_for_deletion_at=timezone.now())

    def _delete_marked_template(self, root_id: int) -> bool:
        """
        Permanently removes one user template marked for deletion longer than the
        grace period ago, in one transaction: its root, its revisions and the jobs
        that created, updated or installed any of them. Its workspaces and
        archives are deleted once that commits, and kept track of until their
        deletion succeeds, so that the sweep retries a failed one.

        The template is kept while one of its jobs is pending or running, so that
        an install, an update or a download finishes first, and while another
        transaction holds its root. The download jobs are kept, without their
        revision.

        :param root_id: The id of the root of the template.
        :return: Whether the template was removed.
        """

        from baserow.core.user_templates.models import (
            CreateUserTemplateJob,
            DownloadUserTemplateJob,
            UserTemplateContentToDelete,
        )

        cutoff = timezone.now() - USER_TEMPLATE_DELETION_GRACE_PERIOD
        with transaction.atomic():
            root = (
                Template.objects.user()
                .select_for_update(skip_locked=True)
                .filter(
                    id=root_id,
                    root__isnull=True,
                    marked_for_deletion_at__lte=cutoff,
                )
                .first()
            )
            if root is None:
                return False

            family = list(
                Template.objects.filter(Q(id=root.id) | Q(root=root)).values_list(
                    "id", "workspace_id", "archive"
                )
            )
            family_ids = [template_id for template_id, _, _ in family]
            create_job_ids = list(
                CreateUserTemplateJob.objects.filter(
                    Q(template_id__in=family_ids)
                    | Q(base_revision_id__in=family_ids)
                    | Q(revision_id__in=family_ids)
                ).values_list("id", flat=True)
            )
            install_job_ids = list(
                InstallTemplateJob.objects.filter(
                    template_id__in=family_ids
                ).values_list("id", flat=True)
            )
            # The download jobs are kept without their revision, see
            # `DownloadUserTemplateJob.revision`.
            download_job_ids = list(
                DownloadUserTemplateJob.objects.filter(
                    revision_id__in=family_ids
                ).values_list("id", flat=True)
            )
            job_ids = create_job_ids + install_job_ids + download_job_ids

            # The states are read from the locked rows, because a job that was
            # failed can still be started by its late task until it's locked.
            job_states = (
                Job._base_manager.select_for_update()
                .filter(id__in=job_ids)
                .order_by("id")
                .values_list("state", flat=True)
            )
            if any(state not in JOB_STATES_ENDED for state in job_states):
                return False

            # Deleted one by one, so that what an unfinished job left is tracked by
            # its `pre_delete` receiver, and before the template, so that a late
            # task of an update finds no job instead of running as a create.
            CreateUserTemplateJob.objects.filter(id__in=create_job_ids).delete()

            # The protected revisions can only be deleted once nothing points at
            # them.
            Template.objects.filter(id=root.id).update(
                public_revision=None, shared_revision=None
            )

            # Revisions that only differ in their details share their content.
            distinct_contents = {
                (workspace_id, archive_name or "")
                for _, workspace_id, archive_name in family
                if workspace_id is not None or archive_name
            }
            # Each revision builds its own archives, see `build_template_archive`.
            distinct_contents |= {
                (None, template_archive_dir(template_id)) for template_id in family_ids
            }
            contents = UserTemplateContentToDelete.objects.bulk_create(
                [
                    UserTemplateContentToDelete(
                        workspace_id=workspace_id, archive_name=archive_name
                    )
                    for workspace_id, archive_name in distinct_contents
                ]
            )

            # Deletes the revisions and the install jobs too, and unsets
            # `installed_from_template` of the installed applications.
            root.delete()

            def delete_content():
                # The jobs were deleted without `JobHandler.delete_job`. First,
                # because the outbox retries the content, but not this.
                try:
                    cache.delete_many([job_progress_key(job_id) for job_id in job_ids])
                except SoftTimeLimitExceeded:
                    raise
                except Exception:
                    logger.exception(
                        f"Clearing the job cache of the user template {root_id} failed."
                    )
                for content in contents:
                    self._delete_tracked_content(content)

            transaction.on_commit(delete_content)

        return True

    def delete_content_of_unfinished_jobs(self) -> None:
        """
        Deletes what the failed and cancelled create and update jobs left behind. It
        covers a job that was failed after its worker was killed, which no job hook
        sees.

        A cancelled job is only cleaned up once its worker can't be running anymore,
        because the worker notices the cancellation late and cleans up itself.
        """

        from baserow.core.user_templates.models import (
            CreateUserTemplateJob,
            UserTemplateContentToDelete,
        )

        # The worker of a job is killed at the latest after the hard time limit of
        # `run_async_job`, which started before the job was cancelled.
        cancelled_before = timezone.now() - timedelta(
            seconds=settings.BASEROW_JOB_SOFT_TIME_LIMIT + 30
        )
        jobs = (
            CreateUserTemplateJob.objects.filter(
                Q(state=JOB_FAILED)
                | Q(state=JOB_CANCELLED, updated_on__lt=cancelled_before)
            )
            .exclude(template_workspace__isnull=True, archive_name="")
            # What a job that failed after its commit left is the template's. An
            # update job has its template from the start, the commit sets its
            # revision.
            .exclude(revision__isnull=False)
            .only("id", "template_workspace_id", "archive_name")
        )
        for job in jobs.iterator():
            # One job that can't be cleaned up must not block the others.
            try:
                self.delete_content_without_template(
                    job.template_workspace_id, job.archive_name
                )
            except Exception:
                logger.exception(
                    f"Deleting the content of create user template job {job.id} failed."
                )
                continue
            # The workspace is unset by the deletion, the archive name isn't.
            CreateUserTemplateJob.objects.filter(id=job.id).update(archive_name="")

        for content in UserTemplateContentToDelete.objects.iterator():
            self._delete_tracked_content(content)

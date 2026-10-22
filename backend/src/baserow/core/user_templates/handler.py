import dataclasses
import secrets
import string
from contextlib import contextmanager
from datetime import timedelta
from typing import Callable, Iterable, Iterator, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.files import File
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.text import slugify

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.import_export.handler import ImportExportHandler
from baserow.core.jobs.cache import job_progress_key
from baserow.core.jobs.constants import JOB_CANCELLED, JOB_FAILED
from baserow.core.jobs.exceptions import JobNotCancellable
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import JOB_STATES_ENDED, Job
from baserow.core.models import (
    Application,
    ImportExportResource,
    InstallTemplateJob,
    Template,
    TemplateCategory,
    Workspace,
    template_archive_upload_to,
)
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.signals import application_created, application_imported
from baserow.core.storage import get_default_storage
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_templates.constants import (
    USER_TEMPLATE_DELETION_GRACE_PERIOD,
    USER_TEMPLATE_ICON_MAX_LENGTH,
    USER_TEMPLATE_ICON_REGEX,
    USER_TEMPLATE_PURGE_BATCH_SIZE,
    UserTemplateState,
)
from baserow.core.user_templates.exceptions import (
    InvalidTemplateCategory,
    InvalidTemplateIcon,
    TemplateBlocked,
    TemplateChangedDuringUpdate,
    TemplateHasNoContent,
    TemplateSlugGenerationFailed,
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


def _mark_resource_for_deletion(resource: ImportExportResource) -> None:
    resource.marked_for_deletion = True
    resource.save(update_fields=["marked_for_deletion"])


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

        The root is locked first, so that updates of the same template commit one
        after the other. The revision is only created while the user still owns
        the template and `base_revision` is still its latest revision.

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
            # Moves the template to the top of the list of its owner.
            root.save(update_fields=["updated_on"])

        return revision

    def copy_applications(
        self,
        owner: AbstractUser,
        applications: List[Application],
        *,
        name: str,
        progress_builder: Optional[ChildProgressBuilder] = None,
        track_content: Optional[Callable[..., None]] = None,
    ) -> Tuple[Workspace, str]:
        """
        Copies the applications into a new workspace nobody is a member of and
        stores an archive of the copy, which together become the content of a user
        template.

        The export and the import run their own transactions, so nothing is rolled
        back if it fails. `track_content` is called with the `template_workspace`
        and then with the `archive_name` as soon as they exist, so that the caller
        can remove them with `delete_content_without_template`.

        :param owner: The user who creates the template.
        :param applications: The applications copied into the template.
        :param name: The name of the template, also given to the workspace.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :param track_content: Called with the content created so far as keyword
            arguments.
        :return: The workspace holding the copy and the name of the stored archive.
        """

        if track_content is None:

            def track_content(**content):
                pass

        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        storage = get_default_storage()
        import_export_handler = ImportExportHandler()
        # Nobody is a member of the new workspace, so the import drops what
        # belongs to the users of the source: personal views and collaborators.
        config = user_template_copy_config()

        workspace = Workspace.objects.create(name=name)
        track_content(template_workspace=workspace)

        resource = import_export_handler.export_workspace_applications(
            applications,
            config,
            storage=storage,
            progress_builder=progress.create_child_builder(represents_progress=40),
        )
        try:
            import_export_handler.import_applications_from_export(
                owner,
                workspace,
                resource,
                config,
                storage=storage,
                progress_builder=progress.create_child_builder(represents_progress=40),
            )
        finally:
            _mark_resource_for_deletion(resource)

        archive_resource = import_export_handler.export_workspace_applications(
            list(workspace.application_set.all()),
            config,
            storage=storage,
            progress_builder=progress.create_child_builder(represents_progress=20),
        )
        try:
            archive_name = self._store_archive(archive_resource, storage, track_content)
        finally:
            _mark_resource_for_deletion(archive_resource)

        return workspace, archive_name

    @contextmanager
    def export_template_content(
        self,
        revision: Template,
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> Iterator[ImportExportResource]:
        """
        Exports the applications of a revision of a user template, so that they can
        be installed. The export runs its own transactions, so it must not be
        called inside an atomic block. The resource is marked for deletion when
        the context exits.

        :param revision: The revision to export.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :raises TemplateHasNoContent: If the revision has no application to copy.
            An install of nothing would leave no trace that it committed.
        :return: The resource holding the export.
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

        resource = ImportExportHandler().export_workspace_applications(
            applications,
            user_template_copy_config(),
            storage=get_default_storage(),
            progress_builder=progress_builder,
        )
        try:
            yield resource
        finally:
            _mark_resource_for_deletion(resource)

    def install_template_content(
        self,
        user: AbstractUser,
        workspace: Workspace,
        revision: Template,
        resource: ImportExportResource,
        *,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> List[Application]:
        """
        Installs the export of a revision of a user template into a workspace and
        counts the install on the root of the template. It must be called inside
        an atomic block, so that a failure leaves nothing behind and the count is
        bumped only with a successful install.

        :param user: The user who installs the template.
        :param workspace: The workspace the applications are installed into.
        :param revision: The installed revision, see `export_template_content`.
        :param resource: The export made by `export_template_content`.
        :param progress_builder: A progress builder that allows for publishing
            progress.
        :return: The installed applications.
        """

        # Unlike the copy into the template, the installed tables are used right
        # away, so their search data is filled in like with the official install.
        config = dataclasses.replace(
            user_template_copy_config(), reduce_disk_space_usage=False
        )
        applications = ImportExportHandler().import_applications_from_export(
            user,
            workspace,
            resource,
            config,
            storage=get_default_storage(),
            progress_builder=progress_builder,
        )

        # Like `CoreHandler.install_template`: the user created the applications,
        # and the import hooks, like setting up the integrations, must run.
        for application in applications:
            application.installed_from_template = revision
            application_type = application_type_registry.get_by_model(application)
            for signal in [application_created, application_imported]:
                signal.send(
                    self,
                    application=application,
                    user=user,
                    type_name=application_type.type,
                )
        Application.objects.bulk_update(applications, ["installed_from_template"])

        # An update keeps the `updated_on` of the root, which orders the lists,
        # and doesn't lose a concurrent install.
        Template.objects.filter(pk=revision.family_id).update(
            install_count=F("install_count") + 1
        )

        return applications

    def _store_archive(
        self,
        resource: ImportExportResource,
        storage,
        track_content: Callable[..., None],
    ) -> str:
        """
        Copies an export to where the template archives are kept. The name is
        tracked before the file is written, so that a failure leaves nothing
        untracked behind.
        """

        export_path = ImportExportHandler().export_file_path(
            resource.get_archive_name()
        )
        archive_name = template_archive_upload_to(None, None)
        track_content(archive_name=archive_name)

        with storage.open(export_path, "rb") as export_file:
            stored_name = storage.save(archive_name, export_file)

        if stored_name != archive_name:
            track_content(archive_name=stored_name)

        return stored_name

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

        queryset = Template.objects.user().filter(
            id=template_id,
            root__isnull=True,
            marked_for_deletion_at__isnull=True,
        )
        if not user.is_staff:
            queryset = queryset.filter(owner=user)

        try:
            return queryset.select_for_update().get()
        except Template.DoesNotExist as exc:
            raise TemplateDoesNotExist(
                f"The template {template_id} does not exist."
            ) from exc

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

    def _is_public(self, root: Template) -> bool:
        """Whether the template has a public revision and isn't blocked."""

        return root.public_revision_id is not None and root.blocked_at is None

    def _get_install_access(self, user: AbstractUser, root: Template) -> Optional[str]:
        """
        Why the user may install a user template: as its owner, even while it's
        blocked, or as anyone signed in while it's public. Whether it's marked for deletion is checked by the caller.

        :param user: The user who installs the template.
        :param root: The root of the template.
        :return: `"owner"`, `"public"`, or None without access.
        """

        if not user.is_active:
            return None
        if root.owner_id == user.id:
            return "owner"
        if self._is_public(root):
            return "public"
        return None

    def _check_install_access(
        self, user: AbstractUser, root: Template, latest: bool = False
    ) -> str:
        """
        Raises if the user may not install the template, in the order of the error
        codes: no access before a blocked owner. Only the owner has access to the
        latest revision.

        :return: The access of the user, see `_get_install_access`.
        """

        access = self._get_install_access(user, root)
        if access is None or (latest and access != "owner"):
            raise TemplateDoesNotExist(f"The template {root.id} does not exist.")
        if access == "owner" and root.blocked_at is not None:
            raise TemplateBlocked(f"The template {root.id} is blocked.")
        return access

    def get_installable_revision(
        self, user: AbstractUser, root: Template, latest: bool = False
    ) -> Template:
        """
        Returns the revision of a user template that the user installs: the
        latest one when asked for, which only its owner may, as from "Your
        templates". Otherwise the public revision, the same for everyone, or the
        latest one for its owner while it isn't public. The installed revision is
        pinned, so that an update of the template in the meantime doesn't change
        what's installed.

        :param user: The user who installs the template.
        :param root: The root of a user template that isn't marked for deletion.
        :param latest: Whether the latest revision is installed.
        :raises TemplateDoesNotExist: If the user has no access to the template,
            or asks for the latest revision without owning it.
        :raises TemplateBlocked: If the user owns the template and it's blocked.
        :raises TemplateHasNoContent: If the revision has no application to copy.
        :return: The revision to install, with its root selected.
        """

        self._check_install_access(user, root, latest)
        if not latest and self._is_public(root):
            # Fetched like the latest revision, even when it's the root, so that
            # the request costs the same whichever revision is public.
            revision = Template.objects.select_related("root").get(
                id=root.public_revision_id
            )
        else:
            revision = self.get_latest_revision(root)

        if (
            not revision.has_content
            or not Application.objects.filter(
                workspace_id=revision.workspace_id
            ).exists()
        ):
            raise TemplateHasNoContent(f"The template {root.id} has no content.")

        return revision

    def check_install_access(self, user: AbstractUser, revision: Template) -> None:
        """
        Checks again, when the install runs, that the user may still install the
        pinned revision of a user template. The revision is installed even if the
        public revision changed since, and even if the template was marked for
        deletion since, so that the installs already running finish.

        :param user: The user who installs the template.
        :param revision: The pinned revision, with its root selected.
        :raises TemplateDoesNotExist: If the user lost access to the template.
        :raises TemplateBlocked: If the user owns the template and it's blocked.
        """

        self._check_install_access(user, revision.get_root())

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

    def get_template_state(
        self, template: Template
    ) -> tuple[UserTemplateState, Optional[str]]:
        """
        Returns the state of a user template as shown to its author, together with
        the reason given by an admin for a rejected or blocked template.

        :param template: The latest revision of the template. Whether it's blocked
            or public is read from its root, the review from the revision itself.
        """

        root = template.get_root()
        if root.blocked_at is not None:
            return UserTemplateState.BLOCKED, root.blocked_reason or None
        if root.public_revision_id is not None:
            return UserTemplateState.PUBLIC, None
        if template.review_state == Template.ReviewState.PENDING:
            return UserTemplateState.IN_REVIEW, None
        if template.review_state == Template.ReviewState.REJECTED:
            return UserTemplateState.REJECTED, template.reject_reason or None
        return UserTemplateState.PRIVATE, None

    def delete_content_without_template(
        self, workspace_id: Optional[int], archive_name: str
    ) -> None:
        """
        Permanently deletes the workspace and the archive copied by a job,
        unless a template points at them. A job that didn't commit its revision
        leaves them behind. Deleting twice does nothing.

        :param workspace_id: The id of the workspace holding the copy, if any.
        :param archive_name: The name of the stored archive, if any.
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

        if archive_name and not Template.objects.filter(archive=archive_name).exists():
            storage = get_default_storage()
            if storage.exists(archive_name):
                storage.delete(archive_name)

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

        from baserow.core.user_templates.models import CreateUserTemplateJob

        # Only leaves out what `_delete_marked_template` would skip, which checks
        # the jobs again once they're locked. The families with a pending or
        # running job are read once, rather than per template.
        create_jobs = CreateUserTemplateJob.objects.is_pending_or_running()
        install_jobs = InstallTemplateJob.objects.is_pending_or_running()
        busy_root_ids = (
            Template.objects.filter(
                Q(id__in=create_jobs.values("template_id"))
                | Q(id__in=create_jobs.values("base_revision_id"))
                | Q(id__in=create_jobs.values("revision_id"))
                | Q(id__in=install_jobs.values("template_id"))
            )
            .annotate(family_root_id=Coalesce("root_id", "id"))
            .values("family_root_id")
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
        an install or an update finishes first, and while another transaction
        holds its root.

        :param root_id: The id of the root of the template.
        :return: Whether the template was removed.
        """

        from baserow.core.user_templates.models import (
            CreateUserTemplateJob,
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
            job_ids = create_job_ids + install_job_ids

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

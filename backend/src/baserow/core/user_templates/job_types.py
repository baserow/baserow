from contextlib import nullcontext
from functools import partial
from typing import Any, Dict, Iterable

from django.contrib.auth.models import AbstractUser

from loguru import logger
from rest_framework import serializers

from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_PERMISSION_DENIED,
    ERROR_USER_NOT_IN_GROUP,
)
from baserow.api.exceptions import RequestBodyValidationException
from baserow.api.templates.errors import (
    ERROR_INVALID_TEMPLATE_CATEGORY,
    ERROR_INVALID_TEMPLATE_ICON,
    ERROR_NO_APPLICATIONS_SELECTED,
    ERROR_TEMPLATE_BLOCKED,
    ERROR_TEMPLATE_DOES_NOT_EXIST,
    ERROR_TEMPLATE_HAS_NO_CONTENT,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import (
    PermissionException,
    TemplateDoesNotExist,
    UserNotInWorkspace,
    WorkspaceDoesNotExist,
)
from baserow.core.feature_flags import FF_USER_TEMPLATES, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import JOB_CANCELLED
from baserow.core.jobs.exceptions import JobCancelled
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.models import JobQuerySet
from baserow.core.jobs.registries import JobType
from baserow.core.models import Template
from baserow.core.user_templates.actions import (
    CreateUserTemplateActionType,
    UpdateUserTemplateActionType,
)
from baserow.core.user_templates.archive import has_valid_archive
from baserow.core.user_templates.constants import (
    USER_TEMPLATE_DESCRIPTION_MAX_LENGTH,
    USER_TEMPLATE_ICON_MAX_LENGTH,
)
from baserow.core.user_templates.exceptions import (
    InvalidTemplateCategory,
    InvalidTemplateIcon,
    NoApplicationsSelected,
    TemplateBlocked,
    TemplateChangedDuringUpdate,
    TemplateHasNoContent,
)
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.core.user_templates.models import (
    CreateUserTemplateJob,
    DownloadUserTemplateJob,
)
from baserow.core.user_templates.service import UserTemplateService
from baserow.core.utils import Progress

CREATE_REQUIRED_FIELDS = [
    "workspace_id",
    "application_ids",
    "name",
    "icon",
    "category_ids",
]
DETAILS_FIELDS = ["name", "description", "icon", "category_ids"]
TEMPLATE_FIELD_NAMES = [
    "workspace_id",
    "application_ids",
    "name",
    "description",
    "icon",
    "category_ids",
]


def _get_id_field_overrides(response: bool) -> Dict[str, serializers.Field]:
    """
    The id fields of the request, which are sent back read-only in the response.
    The other fields of the request are serialized from the model. Which fields a
    request needs depends on its mode, see `_validate_mode`.
    """

    options = {"read_only": True} if response else {"required": False}
    return {
        "workspace_id": serializers.IntegerField(
            **({"source": "source_workspace_id"} if response else {}),
            **options,
            help_text="The ID of the workspace the applications are copied from. "
            "Required when creating a template. When updating one, it's given to "
            "replace the content and left out to only change the details.",
        ),
        "application_ids": serializers.ListField(
            child=serializers.IntegerField(),
            **options,
            **({} if response else {"min_length": 1}),
            help_text="The IDs of the applications copied into the template. "
            "Required with `workspace_id`.",
        ),
        "category_ids": serializers.ListField(
            child=serializers.IntegerField(),
            **options,
            help_text="The IDs of the existing categories of the template, at least "
            "one unless there are none. Required, unless the content of a template "
            "is updated.",
        ),
    }


class CreateUserTemplateJobType(JobType):
    """
    Creates a user template, or updates one when `template_id` is given. An update
    copies the applications of `workspace_id` into the content of the next
    revision, or without it reuses the content of the latest revision, so that
    only the details change.
    """

    type = "create_user_template"
    model_class = CreateUserTemplateJob
    max_count = 1
    # Committing the revision is the point of no return: a cancellation is
    # noticed before it, which rolls the revision and its action back, or refused
    # after it, so that the audit log always matches what's kept.
    lock_on_cancel = True

    api_exceptions_map = {
        UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        InvalidTemplateIcon: ERROR_INVALID_TEMPLATE_ICON,
        InvalidTemplateCategory: ERROR_INVALID_TEMPLATE_CATEGORY,
        NoApplicationsSelected: ERROR_NO_APPLICATIONS_SELECTED,
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
        TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
    }

    job_exceptions_map = {
        # Covers losing access to the workspace after the job was created too.
        PermissionException: ERROR_PERMISSION_DENIED[2],
        WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST[2],
        InvalidTemplateIcon: ERROR_INVALID_TEMPLATE_ICON[2],
        InvalidTemplateCategory: ERROR_INVALID_TEMPLATE_CATEGORY[2],
        NoApplicationsSelected: ERROR_NO_APPLICATIONS_SELECTED[2],
        # Covers losing the template, or its ownership, after the job was created.
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST[2],
        TemplateChangedDuringUpdate: "The template was changed while it was being "
        "updated. Please try again.",
        TemplateHasNoContent: "The content of the template was removed.",
    }

    # Which fields are required depends on the mode, see `_validate_mode`.
    request_serializer_field_names = ["template_id", *TEMPLATE_FIELD_NAMES]
    request_serializer_field_overrides = {
        **_get_id_field_overrides(response=False),
        "template_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The ID of the template to update. A template is created "
            "when it's not given.",
        ),
        "name": serializers.CharField(
            max_length=64,
            required=False,
            help_text="The name of the template. Required, unless the content of a "
            "template is updated.",
        ),
        "description": serializers.CharField(
            max_length=USER_TEMPLATE_DESCRIPTION_MAX_LENGTH,
            allow_blank=True,
            required=False,
            help_text="The description of the template. Required when only the "
            "details of a template are updated.",
        ),
        "icon": serializers.CharField(
            max_length=USER_TEMPLATE_ICON_MAX_LENGTH,
            required=False,
            help_text="The iconoir class name of the icon of the template. Required, "
            "unless the content of a template is updated.",
        ),
    }

    # The request is sent back, so that the wizard can show a running job again.
    serializer_field_names = [*TEMPLATE_FIELD_NAMES, "template", "revision"]
    serializer_field_overrides = {
        **_get_id_field_overrides(response=True),
        "template": serializers.PrimaryKeyRelatedField(
            read_only=True,
            help_text="The ID of the template being updated, or of the created "
            "template.",
        ),
        "revision": serializers.PrimaryKeyRelatedField(
            read_only=True,
            help_text="The ID of the revision the job committed, if any.",
        ),
    }

    def transaction_atomic_context(self, job: CreateUserTemplateJob):
        """
        The export needs its own `repeatable_read` transaction per application and
        the import creates one per application, so the job runs without an outer
        transaction. Whatever was created is removed by `on_error` and
        `on_cancelled` instead of a rollback.
        """

        return nullcontext()

    def _validate_mode(
        self,
        values: Dict[str, Any],
        required: Iterable[str],
        forbidden: Iterable[str] = (),
    ) -> None:
        """
        Checks the fields required and forbidden by the mode of the request, which
        the serializer can't tell apart.
        """

        errors = {}
        for field_name in required:
            if values.get(field_name) is None:
                errors[field_name] = [
                    {"error": "This field is required.", "code": "required"}
                ]
        for field_name in forbidden:
            if values.get(field_name) is not None:
                errors[field_name] = [
                    {
                        "error": "This field can't be given in this mode.",
                        "code": "invalid",
                    }
                ]
        if errors:
            raise RequestBodyValidationException(errors)

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        if values.get("template_id") is not None:
            return self._prepare_update_values(values, user)

        # Only creating a template checks the flag: without one, there's nothing to
        # update or delete.
        feature_flag_is_enabled(FF_USER_TEMPLATES, raise_if_disabled=True)
        self._validate_mode(values, CREATE_REQUIRED_FIELDS)
        workspace = CoreHandler().get_workspace(values["workspace_id"])
        application_ids = values.get("application_ids") or []
        applications = UserTemplateService().get_exportable_applications(
            user, workspace, application_ids
        )
        category_ids = values.get("category_ids") or []
        categories = UserTemplateHandler().validate_icon_and_categories(
            values.get("icon"), category_ids
        )

        return {
            "source_workspace": workspace,
            "application_ids": [application.id for application in applications],
            "name": values["name"],
            "description": values.get("description", ""),
            "icon": values["icon"],
            "category_ids": [category.id for category in categories],
        }

    def _prepare_update_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        handler = UserTemplateHandler()
        service = UserTemplateService()

        if values.get("workspace_id") is not None:
            self._validate_mode(values, ["application_ids"], DETAILS_FIELDS)
        else:
            self._validate_mode(values, DETAILS_FIELDS, ["application_ids"])

        root = service.get_own_template(user, values["template_id"])
        base_revision = handler.get_latest_revision(root)
        update_values = {"template": root, "base_revision": base_revision}

        if values.get("workspace_id") is not None:
            # The content is replaced, the details are kept. They're checked up
            # front, because the commit fails on them after the whole copy, e.g.
            # when every category of the template was deleted.
            workspace = CoreHandler().get_workspace(values["workspace_id"])
            applications = service.get_exportable_applications(
                user, workspace, values["application_ids"]
            )
            categories = handler.validate_icon_and_categories(
                base_revision.icon,
                base_revision.categories.values_list("id", flat=True),
            )
            return update_values | {
                "source_workspace": workspace,
                "application_ids": [application.id for application in applications],
                "name": base_revision.name,
                "description": base_revision.description,
                "icon": base_revision.icon,
                "category_ids": [category.id for category in categories],
            }

        # The content is kept. It's checked up front too, so that a template without
        # content is refused right away instead of failing in the job.
        service.get_template_content(base_revision)
        categories = handler.validate_icon_and_categories(
            values["icon"], values["category_ids"]
        )
        return update_values | {
            "source_workspace": None,
            "application_ids": [],
            "name": values["name"],
            "description": values["description"],
            "icon": values["icon"],
            "category_ids": [category.id for category in categories],
        }

    def run(self, job: CreateUserTemplateJob, progress: Progress):
        is_update = job.template_id is not None
        # An update without applications only changes the details.
        copies_from_workspace = not is_update or bool(job.application_ids)
        if copies_from_workspace and job.source_workspace is None:
            raise WorkspaceDoesNotExist("The source workspace does not exist.")

        kwargs = {
            "name": job.name,
            "description": job.description,
            "icon": job.icon,
            "category_ids": job.category_ids,
            "progress_builder": progress.create_child_builder(
                represents_progress=progress.total
            ),
            "track_content": partial(self._track_content, job),
            "before_commit": partial(self._save_template, job),
        }
        try:
            if not is_update:
                return action_type_registry.get_by_type(
                    CreateUserTemplateActionType
                ).do(job.user, job.source_workspace, job.application_ids, **kwargs)
            return action_type_registry.get_by_type(UpdateUserTemplateActionType).do(
                job.user,
                job.template,
                job.base_revision,
                job.source_workspace if copies_from_workspace else None,
                job.application_ids,
                **kwargs,
            )
        except BaseException:
            try:
                # The revision is only set when its transaction committed, and so
                # is the template of a created one. The template being updated and
                # its base revision can have been deleted in the meantime, which
                # the failed job is saved without.
                job.refresh_from_db(fields=["template", "revision", "base_revision"])
            except CreateUserTemplateJob.DoesNotExist:
                self._delete_content_of_deleted_job(job)
            raise

    def _delete_content_of_deleted_job(self, job: CreateUserTemplateJob) -> None:
        """
        A job deleted while it runs, with its user, can't be saved as failed, so
        `on_error` doesn't run, and its deletion only saw what it tracked by then.
        What it tracked since is still on the instance.
        """

        try:
            UserTemplateHandler().delete_content_of_deleted_job(
                job.template_workspace_id, job.archive_name
            )
        except Exception:
            logger.exception(
                f"Deleting the content of deleted create user template job {job.id} "
                "failed."
            )

    def _save_template(self, job: CreateUserTemplateJob, revision) -> None:
        """
        Sets the revision on the job in the transaction that creates it. The job
        is locked first, so that a cancellation either lands before, and is noticed
        here, or waits for the commit and is refused by `is_cancellable`. The state
        is read from the locked row, because a progress update of this job can
        overwrite the cancelled state in the cache.
        """

        if JobHandler.lock_job(job).state == JOB_CANCELLED:
            raise JobCancelled()
        # The root is revision 1 of a created template.
        job.template_id = revision.root_id or revision.id
        job.revision = revision
        job.save(update_fields=["template", "revision"])

    def is_cancellable(self, job: CreateUserTemplateJob) -> bool:
        # An update job has its template from the start, the commit sets the
        # revision.
        return job.revision_id is None

    def _track_content(self, job: CreateUserTemplateJob, **content) -> None:
        """
        Stores the template workspace on the job as soon as it exists, so that the
        cleanup finds it whatever happens next.
        """

        for field_name, value in content.items():
            setattr(job, field_name, value)
        job.save(update_fields=list(content))

    def on_error(self, job: CreateUserTemplateJob, error: Exception):
        # A revision that was committed is kept with its action, like a
        # cancellation is refused after the commit.
        UserTemplateHandler().delete_content_without_template(
            job.template_workspace_id, job.archive_name
        )

    def on_cancelled(self, job: CreateUserTemplateJob):
        # The revision was rolled back, see `lock_on_cancel`. Whatever can't be
        # deleted here is left to the sweep of unfinished jobs.
        try:
            UserTemplateHandler().delete_content_without_template(
                job.template_workspace_id, job.archive_name
            )
        except Exception:
            logger.exception(
                f"Deleting the content of create user template job {job.id} failed."
            )


class DownloadUserTemplateJobType(JobType):
    """
    Builds the archive of the revision of a user template that the user would
    install, so that it can be imported into another workspace. The archive is
    built on the first download, and reused until Baserow is upgraded, see
    `has_valid_archive`. The download endpoint of the template hands it out, and
    starts this job when there is no valid archive yet.
    """

    type = "download_user_template"
    model_class = DownloadUserTemplateJob
    max_count = 1

    api_exceptions_map = {
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST,
        TemplateBlocked: ERROR_TEMPLATE_BLOCKED,
        TemplateHasNoContent: ERROR_TEMPLATE_HAS_NO_CONTENT,
    }

    job_exceptions_map = {
        # Also lost access before the run, and the revision deleted during the
        # build.
        TemplateDoesNotExist: ERROR_TEMPLATE_DOES_NOT_EXIST[2],
        TemplateBlocked: ERROR_TEMPLATE_BLOCKED[2],
        TemplateHasNoContent: "The content of the template was removed.",
    }

    request_serializer_field_names = ["slug", "latest"]
    request_serializer_field_overrides = {
        "slug": serializers.CharField(
            max_length=50, help_text="The slug of the user template to download."
        ),
        "latest": serializers.BooleanField(
            default=False,
            help_text="Whether to download the latest revision of the user "
            "template, which only its owner may. Otherwise it's the revision the "
            "user would install.",
        ),
    }

    serializer_field_names = ["slug", "latest"]
    serializer_field_overrides = {
        # Null once the template was deleted permanently.
        "slug": serializers.CharField(
            source="revision.get_root.slug",
            read_only=True,
            allow_null=True,
            help_text="The slug of the downloaded user template, to ask for its "
            "archive once the job is finished.",
        ),
    }

    def transaction_atomic_context(self, job: DownloadUserTemplateJob):
        """
        Each application exports in its own `repeatable_read` transaction.
        """

        return nullcontext()

    def prepare_values(
        self, values: Dict[str, Any], user: AbstractUser
    ) -> Dict[str, Any]:
        latest = values.get("latest", False)
        revision = UserTemplateHandler().get_downloadable_revision(
            user, values["slug"], latest=latest
        )
        return {"revision": revision, "latest": latest}

    def run(self, job: DownloadUserTemplateJob, progress: Progress):
        revision = job.revision
        if revision is None:
            raise TemplateDoesNotExist("The template was deleted.")
        # The access may have changed since the job was requested, like install.
        self._check_access(job, revision)
        # A repeated download reuses the archive.
        if has_valid_archive(revision):
            progress.increment(progress.total)
            return
        try:
            UserTemplateHandler().build_template_archive(
                revision,
                progress_builder=progress.create_child_builder(
                    represents_progress=progress.total
                ),
            )
        except TemplateDoesNotExist:
            # Saving the job with the deleted revision would fail.
            job.revision = None
            raise
        # The access may have been lost while the archive was built. The archive
        # stays for later downloads, but this job doesn't hand it out.
        revision.get_root().refresh_from_db(
            fields=["owner", "public_revision", "blocked_at", "marked_for_deletion_at"]
        )
        job.user.refresh_from_db(fields=["is_active"])
        self._check_access(job, revision)

    def _check_access(self, job: DownloadUserTemplateJob, revision: Template):
        """
        Checks the access like install does, but unlike install, a download fails
        once the template is marked for deletion too, so that its archive isn't
        handed out after the owner deleted it.
        """

        if revision.get_root().marked_for_deletion_at is not None:
            raise TemplateDoesNotExist("The template was deleted.")
        UserTemplateHandler().check_install_access(job.user, revision)

    def enhance_queryset(self, queryset: JobQuerySet) -> JobQuerySet:
        return queryset.select_related("revision__root")

import secrets
import uuid
from datetime import datetime, timezone
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import (
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    UniqueConstraint,
)
from django.db.models.functions import Coalesce
from django.db.models.manager import BaseManager

from baserow.core.feature_flags import FF_USER_TEMPLATES, feature_flag_is_enabled
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.user_files.models import UserFile

from .abuse_reports.models import AbuseReport
from .action.models import Action
from .ai_provider.models import (
    AIProviderConfig,
    AIProviderFeatureSetting,
    AIProviderModel,
)
from .chat_runs.models import ChatRun
from .integrations.models import Integration
from .last_viewed.models import UserLastViewedItem
from .mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    ParentWorkspaceTrashableModelMixin,
    PolymorphicContentTypeMixin,
    TrashableModelMixin,
    WithRegistry,
)
from .notifications.models import Notification
from .services.models import Service

__all__ = [
    "ChatRun",
    "Settings",
    "UserLastViewedItem",
    "Workspace",
    "WorkspaceUser",
    "WorkspaceInvitation",
    "Agent",
    "Application",
    "TemplateCategory",
    "Template",
    "UserLogEntry",
    "TrashEntry",
    "UserFile",
    "Action",
    "Snapshot",
    "DuplicateApplicationJob",
    "InstallTemplateJob",
    "Integration",
    "Service",
    "Notification",
    "BlacklistedToken",
    "AIProviderConfig",
    "AIProviderFeatureSetting",
    "AIProviderModel",
    "ExportApplicationsJob",
    "ImportApplicationsJob",
    "ImportExportResource",
    "ImportExportTrustedSource",
    "AbuseReport",
]

from baserow.core.trash.registries import (
    DefaultTrashOperationType,
    TrashOperationType,
    trash_operation_type_registry,
)

User = get_user_model()


# The difference between an admin and member right now is that an admin has
# permissions to update, delete and manage the members of a workspace.
WORKSPACE_USER_PERMISSION_ADMIN = "ADMIN"
WORKSPACE_USER_PERMISSION_MEMBER = "MEMBER"


def get_default_application_content_type():
    return ContentType.objects.get_for_model(Application)


class Operation(models.Model):
    """
    An operation
    """

    name = models.CharField(max_length=255, unique=True)


class Settings(models.Model):
    """
    The settings model represents the application wide settings that only admins can
    change. This table can only contain a single row.
    """

    # Keep these in sync with the web-frontend options in
    # web-frontend/modules/core/enums.js
    class EmailVerificationOptions(models.TextChoices):
        NO_VERIFICATION = "no_verification", "no_verification"
        RECOMMENDED = "recommended", "recommended"
        ENFORCED = "enforced", "enforced"

    instance_id = models.SlugField(default=secrets.token_urlsafe)
    allow_new_signups = models.BooleanField(
        default=True,
        help_text="Indicates whether new users can create a new account when signing "
        "up.",
    )
    allow_signups_via_workspace_invitations = models.BooleanField(
        default=True,
        help_text="Indicates whether invited users can create an account when signing "
        "up, even if allow_new_signups is disabled.",
    )
    allow_reset_password = models.BooleanField(
        default=True,
        help_text="Indicates whether users can request a password reset link.",
    )
    allow_global_workspace_creation = models.BooleanField(
        default=True,
        help_text="Indicates whether all users can create workspaces, or just staff.",
    )
    account_deletion_grace_delay = models.PositiveSmallIntegerField(
        default=30,
        help_text=(
            "Number of days after the last login for an account pending deletion "
            "to be deleted"
        ),
    )
    show_admin_signup_page = models.BooleanField(
        default=True,
        help_text="Indicates that there are no admin users in the database yet, "
        "so in the frontend the signup form will be shown instead of the login page.",
    )
    track_workspace_usage = models.BooleanField(
        default=False,
        help_text="Runs a job once per day which calculates per workspace row counts "
        "and file storage usage, displayed on the admin workspace page.",
    )
    show_baserow_help_request = models.BooleanField(
        default=True,
        help_text=(
            "Indicates whether the `We need your help!` message will be shown on the "
            "dashboard"
        ),
    )
    co_branding_logo = models.ForeignKey(
        UserFile,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Co-branding logo that's placed next to the Baserow logo (176x29).",
    )
    # TODO Remove null=True in a future release.
    email_verification = models.TextField(
        max_length=16,
        null=True,
        choices=EmailVerificationOptions.choices,
        default=EmailVerificationOptions.NO_VERIFICATION,
        help_text="Controls whether user email addresses have to be verified.",
    )
    verify_import_signature = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Indicates whether the signature of imported files should be verified.",
    )
    allow_reporting_abuse = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Indicates whether anonymous visitors can report publicly shared "
        "resources, like views and forms, for abuse.",
    )
    user_templates_require_approval = models.BooleanField(
        default=True,
        db_default=True,
        help_text="Indicates whether a user template must be approved by an admin "
        "before it's publicly listed.",
    )


class UserProfile(models.Model):
    """
    User profile to store user specific information that can't be stored in
    default user model.
    """

    # Keep these in sync with the web-frontend options in
    # web-frontend/modules/core/enums.js
    class EmailNotificationFrequencyOptions(models.TextChoices):
        INSTANT = "instant", "instant"
        DAILY = "daily", "daily"
        WEEKLY = "weekly", "weekly"
        NEVER = "never", "never"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    language = models.TextField(
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        help_text="An ISO 639 language code (with optional variant) "
        "selected by the user. Ex: en-GB.",
    )
    to_be_deleted = models.BooleanField(
        default=False,
        help_text="True if the user is pending deletion. "
        "An automatic task will delete the user after a grace delay.",
    )
    concurrency_limit = models.SmallIntegerField(
        null=True,
        default=None,
        blank=True,
        help_text="An optional per user concurrency limit.",
    )
    timezone = models.CharField(
        max_length=255,
        null=True,
        help_text="The user timezone to use for dates and times.",
    )
    email_notification_frequency = models.TextField(
        max_length=16,
        choices=EmailNotificationFrequencyOptions.choices,
        default=EmailNotificationFrequencyOptions.INSTANT,
    )
    last_notifications_email_sent_at = models.DateTimeField(
        null=True,
        default=None,
        help_text="The last time an email notification was sent to the user.",
    )
    # This property is used to invalidate authentication tokens that were generated
    # before this date.
    last_password_change = models.DateTimeField(
        null=True,
        default=None,
        help_text="Timestamp when the user changed their password.",
    )
    # TODO Remove null=True in a future release.
    email_verified = models.BooleanField(null=True, default=False)
    # TODO Remove null=True in a future release.
    completed_onboarding = models.BooleanField(null=True, default=False)
    completed_guided_tours = ArrayField(
        base_field=models.TextField(),
        default=list,
        blank=True,
        null=True,
    )
    preferences = models.JSONField(
        default=dict,
        db_default={},
        blank=True,
        help_text="Values of the registered user preference types, keyed by type. "
        "Only explicitly changed preferences are stored here.",
    )

    def iat_before_last_password_change(self, iat: int) -> bool:
        """
        Returns whether the iat value of a token was generated before the last
        password. This can be needed to invalidate the token if so.

        :param iat: The unix in unit timestamp format to compare with the
            `last_password_change`.
        :return: Whether the iat was before the last password change.
        """

        if not self.last_password_change:
            return False

        iat = datetime.utcfromtimestamp(iat).replace(tzinfo=timezone.utc)
        # We have to remove the milliseconds because the `iat` doesn't have
        # milliseconds in the timestamp, so that can result in the
        # `last_password_change` being higher, while it was actually done before the
        # `iat` was generated.
        last_password_change = self.last_password_change.replace(microsecond=0)
        return last_password_change > iat

    def is_jwt_token_valid(self, token):
        return not self.iat_before_last_password_change(token["iat"])


class BlacklistedToken(CreatedAndUpdatedOnMixin, models.Model):
    hashed_token = models.CharField(max_length=64, db_index=True, unique=True)
    expires_at = models.DateTimeField()


class _WorkspaceTemplatesCacheKey:
    """
    Caches the template types of a workspace by its id and `updated_on`, and holds
    the instance, so that its prefetched `template_set` is used on a miss. The
    cache keeps the key of a miss, so the instance is dropped after it.
    """

    __slots__ = ("key", "workspace")

    def __init__(self, workspace: "Workspace"):
        self.workspace = workspace
        self.key = (workspace.id, workspace.updated_on)

    def __hash__(self):
        return hash(self.key)

    def __eq__(self, other):
        return isinstance(other, _WorkspaceTemplatesCacheKey) and self.key == other.key


@lru_cache
def _get_workspace_template_types(key: _WorkspaceTemplatesCacheKey) -> frozenset[str]:
    # Iterates `all()`, so that a prefetched `template_set` is used. A null `type`
    # means official.
    template_types = frozenset(
        template.type or Template.Type.OFFICIAL
        for template in key.workspace.template_set.all()
    )
    key.workspace = None
    return template_types


class Workspace(HierarchicalModelMixin, TrashableModelMixin, CreatedAndUpdatedOnMixin):
    name = models.CharField(max_length=165)
    users = models.ManyToManyField(User, through="WorkspaceUser")
    storage_usage = models.IntegerField(null=True)
    storage_usage_updated_at = models.DateTimeField(null=True)
    seats_taken = models.IntegerField(null=True)
    seats_taken_updated_at = models.DateTimeField(null=True)
    now = models.DateTimeField(null=True)
    generative_ai_models_settings = models.JSONField(default=dict, null=True)

    def get_parent(self):
        return None

    def refresh_now(self):
        self.now = datetime.now(tz=timezone.utc)
        self.save(update_fields=["now"])

    def get_now_or_set_if_null(self):
        if self.now is None:
            self.refresh_now()
        return self.now

    def application_set_including_trash(self):
        """
        :return: The applications for this workspace including any trashed applications.
        """

        return self.application_set(manager="objects_and_trash")

    def has_template(self):
        return len(self.get_template_types()) > 0

    def get_template_types(self) -> frozenset[str]:
        """
        The types of the templates in this workspace. Cached in the process, because
        the type of a template never changes. A workspace can get its first template
        after it was checked, so creating a user template updates `updated_on`, which
        is part of the cache key.
        """

        return _get_workspace_template_types(_WorkspaceTemplatesCacheKey(self))

    def has_openable_template(self, actor) -> bool:
        """
        Whether the actor can open this workspace as a template, see
        `Template.is_openable_by`. Prefetch `template_set__root` to check many
        workspaces without a query each.
        """

        template_types = self.get_template_types()
        if Template.Type.OFFICIAL in template_types:
            return True
        if Template.Type.USER not in template_types or not feature_flag_is_enabled(
            FF_USER_TEMPLATES
        ):
            return False
        # Not cached, because the state of a user template changes. The roots of the
        # revisions are selected along when the templates aren't prefetched.
        templates = self.template_set.all()
        if "template_set" not in getattr(self, "_prefetched_objects_cache", {}):
            templates = templates.select_related("root")
        return any(template.is_openable_by(actor) for template in templates)

    def get_workspace_user(
        self, user: User, include_trash: bool = False
    ) -> "WorkspaceUser":
        """
        Return the WorkspaceUser object for this workspace for the specified user.

        :param user: The user we want the workspace user for.
        :param include_trash: Do we want to check trashed workspace user also ?
        :return: The related workspace user instance.
        """

        if include_trash:
            manager = WorkspaceUser.objects_and_trash
        else:
            manager = WorkspaceUser.objects

        return manager.get(user=user, workspace=self)

    def __str__(self):
        return f"<Workspace id={self.id}, name={self.name}>"

    def __repr__(self):
        return f"<Workspace id={self.id}, name={self.name}>"


class WorkspaceUser(
    HierarchicalModelMixin,
    ParentWorkspaceTrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    models.Model,
):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="The user that has access to the workspace.",
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace that the user has access to.",
    )
    order = models.PositiveIntegerField(
        help_text="Unique order that the workspace has for the user."
    )
    permissions = models.CharField(
        default=WORKSPACE_USER_PERMISSION_MEMBER,
        max_length=32,
        help_text="The permissions that the user has within the workspace.",
    )

    def get_parent(self):
        return self.workspace

    class Meta:
        unique_together = [["user", "workspace"]]
        ordering = ("order",)

    @classmethod
    def get_last_order(cls, user):
        queryset = cls.objects.filter(user=user)
        return cls.get_highest_order_of_queryset(queryset) + 1


class Agent(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    """A non-authenticating subject owned by a workspace."""

    workspace = models.ForeignKey(
        Workspace,
        related_name="agents",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=160)
    role_uid = models.CharField(
        max_length=32,
        default=WORKSPACE_USER_PERMISSION_MEMBER,
        db_default=WORKSPACE_USER_PERMISSION_MEMBER,
    )
    last_active = models.DateTimeField(null=True, blank=True, db_default=None)

    def get_parent(self):
        return self.workspace

    class Meta:
        ordering = ("name", "id")


class WorkspaceInvitation(
    HierarchicalModelMixin,
    ParentWorkspaceTrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    models.Model,
):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace that the user will get access to once the invitation "
        "is accepted.",
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        help_text="The user that created the invitation.",
    )
    email = models.EmailField(
        db_index=True,
        help_text="The email address of the user that the invitation is meant for. "
        "Only a user with that email address can accept it.",
    )
    permissions = models.CharField(
        default=WORKSPACE_USER_PERMISSION_MEMBER,
        max_length=32,
        help_text="The permissions that the user is going to get within the workspace "
        "after accepting the invitation.",
    )
    # TODO ZDM: Remove this field in a future migration (no longer used)
    message = models.TextField(
        default="",
        max_length=250,
        help_text="Deprecated legacy field retained for compatibility. This message is not exposed to invitation recipients.",
    )

    def get_parent(self):
        return self.workspace

    class Meta:
        ordering = ("id",)
        unique_together = [["workspace", "email"]]


class Application(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    PolymorphicContentTypeMixin,
    WithRegistry,
    models.Model,
):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=160)
    order = models.PositiveIntegerField()
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="content type",
        related_name="applications",
        on_delete=models.SET(get_default_application_content_type),
    )
    installed_from_template = models.ForeignKey(
        "Template",
        on_delete=models.SET_NULL,
        null=True,
        related_name="installed_applications",
    )

    class Meta:
        ordering = ("order",)

    @staticmethod
    def get_type_registry():
        from .registries import application_type_registry

        return application_type_registry

    @classmethod
    def get_last_order(cls, workspace):
        queryset = Application.objects.filter(workspace=workspace)
        return cls.get_highest_order_of_queryset(queryset) + 1

    def get_parent(self):
        if not self.workspace_id:
            raise ValueError(
                "Cannot call get_parent if workspace is None. Please check your hierarchy."
            )
        return self.workspace

    def get_workspace(self) -> Workspace | None:
        """
        Returns the workspace the application belongs to. A type with published
        copies, which have no workspace of their own, returns the workspace of the
        application it's published from.

        :return: The workspace, if any.
        """

        return self.workspace


class TemplateCategory(models.Model):
    name = models.CharField(max_length=32)

    class Meta:
        ordering = ("name",)


def template_archive_upload_to(instance, filename):
    """
    Stores the archive of a template revision in its own directory, separate from
    the temporary export files that are cleaned up.
    """

    return f"template-revisions/{uuid.uuid4().hex}.zip"


def _official_template_q() -> Q:
    # TODO ZDM: `type` is null for rows inserted by the previous version during
    # the deploy. Drop the null check once `type` is not nullable.
    return Q(type__isnull=True) | Q(type=Template.Type.OFFICIAL)


def _get_user_id(actor) -> int | None:
    return actor.id if isinstance(actor, User) else None


def _root_q(**lookups) -> Q:
    """
    Matches the rows whose root matches the lookups: the root itself, which also
    holds revision 1, and every later revision pointing at it.
    """

    return Q(root__isnull=True, **lookups) | Q(
        root__isnull=False,
        **{f"root__{lookup}": value for lookup, value in lookups.items()},
    )


class TemplateQuerySet(QuerySet):
    def official(self):
        return self.filter(_official_template_q())

    def user(self):
        return self.filter(type=Template.Type.USER)

    def latest_revisions(self):
        """
        The latest revision of every template in this queryset: the row with the
        highest `version` among the rows of the template in this queryset. A
        revision filtered out, like one the actor can't open, is skipped. The root is
        selected too, because it holds the fields of the template as a whole.
        """

        family_id = Coalesce("root_id", "id")
        newer_revision = self.filter(
            Q(id=OuterRef("family_id")) | Q(root_id=OuterRef("family_id")),
            version__gt=OuterRef("version"),
        )
        return (
            self.alias(family_id=family_id)
            .filter(~Exists(newer_revision))
            .select_related("root")
        )

    def filter_by_root(self, **lookups):
        """
        The rows of the templates whose root matches the lookups: the root itself
        and every later revision pointing at it.
        """

        return self.filter(_root_q(**lookups))

    def official_or_owned(self, actor):
        """
        The official templates and every revision of the user templates owned by
        the actor.
        """

        q = _official_template_q()
        if (user_id := _get_user_id(actor)) is not None:
            q |= Q(type=Template.Type.USER) & _root_q(owner_id=user_id)
        return self.filter(q)

    def openable(self, actor):
        """
        The templates the actor can open: every revision of the own ones, only the
        public revision of the others. Matches `Template.is_openable_by`.
        """

        official = _official_template_q()
        if not feature_flag_is_enabled(FF_USER_TEMPLATES):
            return self.filter(official)

        visible = _root_q(
            public_revision=F("id"),
            blocked_at__isnull=True,
            marked_for_deletion_at__isnull=True,
        )
        if (user_id := _get_user_id(actor)) is not None:
            visible |= _root_q(owner_id=user_id, marked_for_deletion_at__isnull=True)
        return self.filter(official | Q(type=Template.Type.USER) & visible)


class Template(models.Model):
    """
    An official or user template revision. A root row (`root` is null) is the
    template itself and also holds revision 1. Every later revision is a new row
    pointing directly at the root. The fields describing the template as a whole
    are only set on the root.
    """

    class Type(models.TextChoices):
        OFFICIAL = "official", "Official"
        USER = "user", "User"

    class ReviewState(models.TextChoices):
        NOT_SUBMITTED = "not_submitted", "Not submitted"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    # TODO ZDM: make this field not nullable in the next version, after re-running
    # both steps of migration 0129 for rows inserted by the previous version during
    # the deploy: set `type` to official, then mark official roots approved and
    # their own public revision.
    type = models.CharField(
        max_length=16,
        null=True,
        choices=Type.choices,
        help_text="Whether this is an official or a user template. Null means "
        "official. Revisions have the same type as their root.",
    )
    root = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="revisions",
        help_text="The template this revision belongs to. Null for the template "
        "itself, which also holds revision 1.",
    )
    version = models.PositiveIntegerField(
        default=1,
        db_default=1,
        help_text="The revision number. 1 for the root, 2 or higher for later "
        "revisions.",
    )
    name = models.CharField(max_length=64)
    slug = models.SlugField(
        blank=True,
        help_text="The permanent address of the template, unique among roots. For "
        "official templates it also matches the JSON file name. Empty for "
        "revisions.",
    )
    description = models.TextField(
        default="",
        db_default="",
        blank=True,
        help_text="The description of this revision.",
    )
    icon = models.CharField(
        max_length=32,
        help_text="The icon class name that can be used for displaying purposes.",
    )
    categories = models.ManyToManyField(TemplateCategory, related_name="templates")
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.SET_NULL,
        null=True,
        help_text="The group containing the applications related to the template. The "
        "read endpoints related to that group are publicly accessible for "
        "preview purposes. Revisions of the same template that only differ in "
        "their details share it.",
    )
    archive = models.FileField(
        upload_to=template_archive_upload_to,
        max_length=255,
        null=True,
        blank=True,
        help_text="The downloadable file of this revision, shared like `workspace`.",
    )
    export_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="The export hash that is used to compare if the exported group "
        "applications have changed when syncing the templates.",
    )
    keywords = models.TextField(
        default="",
        blank=True,
        help_text="Keywords related to the template that can be used for search.",
    )
    open_application = models.IntegerField(
        null=True,
        help_text="The application ID that must be opened when the template is "
        "previewed. If null, then the first will automatically be chosen.",
    )
    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_template_roots",
        help_text="The user who controls a user template. Only set on user roots.",
    )
    author = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="authored_template_roots",
        help_text="The user who created a user template. Only set on user roots.",
    )
    public_revision = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="published_by_roots",
        help_text="The approved revision that is publicly listed. Null means not "
        "listed. Only set on roots, pointing at the root or one of its revisions.",
    )
    shared_revision = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="shared_by_roots",
        help_text="The revision shared through the private link. Only set on roots, "
        "pointing at the root or one of its revisions.",
    )
    private_link_token = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        validators=[RegexValidator(r"\A[0-9a-f]{64}\Z")],
        help_text="The secret token of the private link. Null disables the link. "
        "Only set on user roots and never returned in ordinary responses.",
    )
    blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When an admin blocked the template. Only set on user roots.",
    )
    blocked_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blocked_template_roots",
        help_text="The admin who blocked the template.",
    )
    blocked_reason = models.TextField(
        default="",
        db_default="",
        blank=True,
        help_text="Why the template was blocked, shown to its author.",
    )
    marked_for_deletion_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the template was deleted. It's unavailable from then on and "
        "removed permanently later.",
    )
    install_count = models.PositiveBigIntegerField(
        default=0,
        db_default=0,
        help_text="How many times any revision of the template was installed. Only "
        "counted on roots.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        db_default={},
        help_text="Private, owner-only revision metadata.",
    )
    review_state = models.CharField(
        max_length=16,
        choices=ReviewState.choices,
        default=ReviewState.NOT_SUBMITTED,
        db_default=ReviewState.NOT_SUBMITTED,
        help_text="The review state of this revision. Approval alone doesn't list "
        "it, the root's `public_revision` does.",
    )
    submitted_on = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this revision was last submitted for review.",
    )
    reviewed_on = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this revision was last approved or rejected.",
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_template_revisions",
        help_text="The admin who last approved or rejected this revision.",
    )
    reject_reason = models.TextField(
        default="",
        db_default="",
        blank=True,
        help_text="Why this revision was rejected, shown to the template author.",
    )
    pruned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the workspace and archive of this revision were removed to "
        "save space. The row itself is kept.",
    )
    created_on = models.DateTimeField(
        auto_now_add=True,
        null=True,
        help_text="Null for templates created before this field existed.",
    )
    updated_on = models.DateTimeField(
        auto_now=True,
        null=True,
        help_text="Null for templates not saved since this field existed.",
    )

    objects = TemplateQuerySet.as_manager()

    class Meta:
        ordering = ("name",)
        indexes = [
            models.Index(fields=["type"], name="core_template_type_idx"),
            models.Index(
                fields=["review_state", "submitted_on"],
                name="core_template_review_idx",
            ),
        ]
        constraints = [
            # The root holds the fields of the template as a whole, revisions keep
            # them empty.
            models.CheckConstraint(
                name="core_template_row_role",
                condition=(
                    Q(root__isnull=True, version=1)
                    | Q(
                        root__isnull=False,
                        version__gte=2,
                        slug="",
                        owner__isnull=True,
                        author__isnull=True,
                        public_revision__isnull=True,
                        shared_revision__isnull=True,
                        private_link_token__isnull=True,
                        blocked_at__isnull=True,
                        blocked_by__isnull=True,
                        blocked_reason="",
                        marked_for_deletion_at__isnull=True,
                        install_count=0,
                    )
                ),
            ),
            models.CheckConstraint(
                name="core_template_root_slug",
                condition=Q(root__isnull=False) | ~Q(slug=""),
            ),
            models.CheckConstraint(
                name="core_template_valid_type",
                condition=Q(type__in=["official", "user"]),
            ),
            # Null `type` means official, so it must be checked explicitly. A
            # `type = 'user'` comparison is null for it, which passes a check.
            models.CheckConstraint(
                name="core_template_official_no_owner",
                condition=(
                    (Q(type__isnull=False) & Q(type="user"))
                    | Q(owner__isnull=True, author__isnull=True)
                ),
            ),
            models.CheckConstraint(
                name="core_template_user_owner",
                condition=(
                    Q(root__isnull=False)
                    | Q(type__isnull=True)
                    | Q(type="official")
                    | Q(owner__isnull=False)
                    | Q(marked_for_deletion_at__isnull=False)
                ),
            ),
            models.CheckConstraint(
                name="core_template_nonempty_token",
                condition=Q(private_link_token__isnull=True)
                | ~Q(private_link_token=""),
            ),
            models.UniqueConstraint(
                fields=["root", "version"],
                name="core_template_root_version",
            ),
            models.UniqueConstraint(
                fields=["slug"],
                condition=Q(root__isnull=True),
                name="core_template_unique_root_slug",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def family_id(self):
        return self.root_id if self.root_id is not None else self.pk

    def get_root(self):
        return self.root if self.root_id is not None else self

    def is_openable_by(self, actor) -> bool:
        """
        Whether the actor can open this template: an official one or, while user
        templates are enabled, a revision of a user template not marked for
        deletion that is owned by the actor, or is the public revision of a template
        that isn't blocked. Matches `Template.objects.openable`.
        """

        if self.type in (None, Template.Type.OFFICIAL):
            return True
        root = self.get_root()
        if root.marked_for_deletion_at is not None or not feature_flag_is_enabled(
            FF_USER_TEMPLATES
        ):
            return False
        if root.public_revision_id == self.id and root.blocked_at is None:
            return True
        user_id = _get_user_id(actor)
        return user_id is not None and root.owner_id == user_id

    def clean(self):
        """
        Validates the rules that span multiple rows. `save()` doesn't call this, so
        handlers changing these fields must check them too.
        """

        super().clean()
        errors = {}
        templates = Template.objects.using(self._state.db)

        if self.root_id is not None:
            root = templates.filter(pk=self.root_id).first()
            if root is None or root.root_id is not None:
                errors["root"] = "A revision must point directly at a root."
            elif self.type != root.type:
                errors["type"] = "A revision must have the same type as its root."

        # Only the revisions of one template share their content.
        if self.workspace_id is not None:
            others = templates.filter(workspace_id=self.workspace_id)
            if self.family_id is not None:
                others = others.exclude(
                    Q(pk=self.family_id) | Q(root_id=self.family_id)
                )
            if others.exists():
                errors["workspace"] = "The workspace belongs to another template."

        for field_name in ("public_revision", "shared_revision"):
            revision_id = getattr(self, f"{field_name}_id")
            if revision_id is None:
                continue
            if self.root_id is not None or self.pk is None:
                errors[field_name] = "Only a saved root can select a revision."
                continue

            revision = (
                self
                if revision_id == self.pk
                else templates.filter(pk=revision_id).first()
            )
            if revision is None or self.pk not in (revision.pk, revision.root_id):
                errors[field_name] = "The selected revision must belong to this root."
            elif revision.type != self.type:
                errors[field_name] = "The selected revision must have the root's type."
            elif revision.pruned_at or not revision.workspace_id:
                errors[field_name] = "The selected revision must have content."
            elif (
                field_name == "public_revision"
                and revision.review_state != self.ReviewState.APPROVED
            ):
                errors[field_name] = "A public revision must be approved."

        if errors:
            raise ValidationError(errors)


class UserLogEntry(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=(("SIGNED_IN", "Signed in"),))
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        get_latest_by = "timestamp"
        ordering = ["-timestamp"]


class TrashEntry(models.Model):
    """
    A TrashEntry is a record indicating that another model in Baserow has a trashed
    row. When a user deletes certain things in Baserow they are not actually deleted
    from the database, but instead marked as trashed. Trashed rows can be restored
    or permanently deleted.

    The other model must mixin the TrashableModelMixin and also have a corresponding
    TrashableItemType registered specifying exactly how to delete and restore that
    model.
    """

    # The TrashableItemType.type of the item that is trashed.
    trash_item_type = models.TextField()
    # We need to also store the parent id as for some trashable items the
    # trash_item_type and the trash_item_id is not unique as the items of that type
    # could be spread over multiple tables with the same id.
    parent_trash_item_id = models.PositiveIntegerField(null=True, blank=True)
    # The actual id of the item that is trashed
    trash_item_id = models.PositiveIntegerField()

    trash_item_owner = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="private_trash_entries",
    )

    # If the user who trashed something gets deleted we still wish to preserve this
    # trash record as it is independent of if the user exists or not.
    user_who_trashed = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    # The workspace and application fields are used to workspace trash into
    # separate "bins" which can be viewed and emptied independently of each other.

    # The workspace the item that is trashed is found in, if the trashed item is the
    # workspace itself then this should also be set to that trashed workspace.
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    # The application the item that is trashed is found in, if the trashed item is the
    # application itself then this should also be set to that trashed application.
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, null=True, blank=True
    )

    # When set to true this trash entry will be picked up by a periodic job and the
    # underlying item will be actually permanently deleted along with the entry.
    should_be_permanently_deleted = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(auto_now_add=True)

    # The name, name of the parent and any extra description are cached so lookups
    # of trashed items are simple and do not require joining to many different tables
    # to simply get these details.
    name = models.TextField()
    # If multiple items have been deleted via one trash entry, for example with a
    # batch update, the names can be provided here. The client can then visualize
    # this differently.
    names = ArrayField(base_field=models.TextField(), null=True)
    parent_name = models.TextField(null=True, blank=True)
    extra_description = models.TextField(null=True, blank=True)

    # this permits to trash items together with a single entry
    related_items = models.JSONField(default=dict, null=True)

    # A field to store additional restoration data that can be used by the
    # TrashableItemType.restore method to restore the item in a specific way.
    # For example, if the item was trashed with and related data needs to be
    # restored with a specific state.
    additional_restoration_data = models.JSONField(default=dict, null=True)

    # Optionally store the trash operation type that was used to trash this item.
    trash_operation_type = models.CharField(
        max_length=125,
        null=True,
        blank=True,
        help_text="Optionally provide the trash operation type associated with this "
        "trash entry. The trash operation type gives additional context about how this "
        "trash entry was created, and if it has specific restoration requirements.",
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["trash_item_type", "parent_trash_item_id", "trash_item_id"],
                name="unique_with_parent_trash_item_id",
            ),
            UniqueConstraint(
                fields=["trash_item_type", "trash_item_id"],
                condition=Q(parent_trash_item_id=None),
                name="unique_without_parent_trash_item_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["-trashed_at", "trash_item_type", "workspace", "application"]
            )
        ]

    @property
    def managed(self) -> bool:
        """
        Returns whether this trash entry is managed internally and
        cannot be restored manually.

        :return: True if the trash entry is managed, false otherwise.
        """

        return self.get_operation_type().managed

    def get_operation_type(self) -> TrashOperationType:
        return trash_operation_type_registry.get(
            self.trash_operation_type or DefaultTrashOperationType.type
        )


class DuplicateApplicationJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_application = models.ForeignKey(
        Application,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The Baserow application to duplicate.",
    )
    duplicated_application = models.OneToOneField(
        Application,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated Baserow application.",
    )


class SnapshotManager(BaseManager.from_queryset(QuerySet)):
    def restorable(self) -> QuerySet:
        """
        Returns a queryset with Snapshots that can be restored.

        :return: A queryset with Snapshots that can be restored.
        """

        return self.get_queryset().filter(
            snapshot_to_application__isnull=False, mark_for_deletion=False
        )

    def unusable(self) -> QuerySet:
        """
        Returns a queryset with Snapshots that cannot be restored.

        :returns: A queryset with Snapshots that cannot be restored because they are
            either not associated with an application or are marked for deletion.
        """

        return self.get_queryset().filter(
            Q(snapshot_to_application__isnull=True) | Q(mark_for_deletion=True)
        )


class Snapshot(HierarchicalModelMixin, models.Model):
    name = models.CharField(max_length=160)
    snapshot_from_application = models.ForeignKey(
        Application, on_delete=models.CASCADE, null=False, related_name="snapshot_to"
    )
    snapshot_to_application = models.ForeignKey(
        Application, on_delete=models.CASCADE, null=True, related_name="snapshot_from"
    )
    mark_for_deletion = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_parent(self):
        return self.snapshot_from_application

    objects = SnapshotManager()


class InstallTemplateJob(
    JobWithUserIpAddress,
    JobWithWebsocketId,
    JobWithUndoRedoIds,
    Job,
):
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The group where the template is installed.",
    )
    template = models.ForeignKey(
        Template,
        on_delete=models.CASCADE,
        help_text="The template that is installed.",
    )
    installed_applications = models.JSONField(default=list)


class DefaultImportExportResourceManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(marked_for_deletion=False)


class ImportExportResource(CreatedAndUpdatedOnMixin, models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text=(
            "The UUID of the resource, used in the archive name and as the directory "
            "name for temporary storage before archiving or extraction. "
            "The folder must be checked and deleted before deleting the instance."
        ),
    )
    original_name = models.CharField(
        max_length=255,
        help_text=(
            "The original name of the file. "
            "This is only used in the frontend for uploaded files.",
        ),
    )
    size = models.PositiveBigIntegerField(
        default=0, help_text="The size of the resource in bytes."
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        help_text="The owner of the resource.",
    )
    is_valid = models.BooleanField(
        default=False,
        help_text=(
            "Indicates whether the resource is valid and can be used for import "
            "or export. If it's not valid, the temporary files should be deleted before "
            "deleting the instance.",
        ),
    )
    marked_for_deletion = models.BooleanField(
        default=False,
        help_text=(
            "Indicates whether the resource is marked for deletion. "
            "The temporary files should be deleted before deleting the instance."
        ),
    )

    objects_and_trash = models.Manager()
    objects = DefaultImportExportResourceManager()

    def get_archive_name(self):
        return f"{self.uuid}.zip"

    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = uuid.uuid4()
        super().save(*args, **kwargs)


class ExportApplicationsJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The workspace that the applications are going to be exported from.",
    )
    application_ids = models.JSONField(
        default=list,
        help_text="The list of application ids that are going to be exported.",
    )
    only_structure = models.BooleanField(
        default=False,
        help_text="Indicates if only the structure of the applications should be "
        "exported, without user data.",
    )
    resource = models.ForeignKey(
        ImportExportResource,
        on_delete=models.SET_NULL,
        null=True,
        help_text="The resource that contains the exported applications.",
    )


class ImportApplicationsJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    workspace = models.ForeignKey(
        Workspace,
        null=True,
        on_delete=models.SET_NULL,
        help_text="The workspace id that the applications are going to be imported to.",
    )
    application_ids = models.JSONField(
        default=list,
        help_text=(
            "The list of application IDs that are going to be imported. "
            "These IDs must be available in the resource."
        ),
    )
    only_structure = models.BooleanField(
        default=False,
        help_text="Indicates if only the structure of the applications should be "
        "exported, without user data.",
    )
    resource = models.ForeignKey(
        ImportExportResource,
        on_delete=models.SET_NULL,
        null=True,
        help_text="The resource that contains the applications to import.",
    )


class ImportExportTrustedSource(models.Model):
    name = models.CharField(max_length=255, blank=True)
    private_key = models.TextField(help_text="The private key used to sign the export.")
    public_key = models.TextField(
        help_text="The public key used to verify the signature of the export."
    )
    created_at = models.DateTimeField(auto_now_add=True)


class SchemaOperation(CreatedAndUpdatedOnMixin, models.Model):
    """
    Keeps track of schema operations that have been applied to database tables.

    This is only useful for schema operations that cannot be handled by Django's
    built-in migration framework, that we want to do only once and are somehow dynamic
    or conditional.

    For example, we might want to add a table field or migrate some data only if a
    certain extension is installed in the database (i.e. vector).

    Even if this table is born to add and migrate pgvector fields, it can be used for
    other similar use cases in the future.
    """

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The content type of the model that the operation was applied to.",
    )
    operation = models.CharField(
        max_length=64,
        help_text="A unique identifier for the operation that was applied.",
    )

    class Meta:
        unique_together = [["content_type_id", "operation"]]

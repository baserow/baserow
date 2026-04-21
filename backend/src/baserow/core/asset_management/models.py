import uuid
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from baserow.core.mixins import CreatedAndUpdatedOnMixin, TrashableModelMixin

User = get_user_model()


class AssetCategory(models.Model):
    """Asset category for organizing assets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    workspace = models.ForeignKey(
        "core.Workspace",
        on_delete=models.CASCADE,
        related_name="asset_categories",
    )
    color = models.CharField(max_length=7, default="#3366CC")
    icon = models.CharField(max_length=50, default="folder")
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_category"
        ordering = ("created_on",)

    def __str__(self):
        return self.name


class Asset(CreatedAndUpdatedOnMixin, TrashableModelMixin, models.Model):
    """Main asset model for file management."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    file = models.FileField(upload_to="assets/%Y/%m/%d/")
    file_size = models.BigIntegerField(default=0)
    file_type = models.CharField(max_length=100)
    file_extension = models.CharField(max_length=20)
    mime_type = models.CharField(max_length=100)

    workspace = models.ForeignKey(
        "core.Workspace",
        on_delete=models.CASCADE,
        related_name="assets",
    )
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_assets",
    )

    is_public = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    download_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)

    tags = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "asset"
        ordering = ("-created_on",)
        indexes = [
            models.Index(fields=["workspace", "-created_on"]),
            models.Index(fields=["owner", "-created_on"]),
            models.Index(fields=["category", "-created_on"]),
            models.Index(fields=["is_archived"]),
        ]

    def __str__(self):
        return self.name


class AssetVersion(models.Model):
    """Version history for assets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.IntegerField()
    file = models.FileField(upload_to="asset_versions/%Y/%m/%d/")
    file_size = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="asset_versions_created",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    change_log = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "asset_version"
        ordering = ("-version_number",)
        unique_together = ("asset", "version_number")
        indexes = [
            models.Index(fields=["asset", "-version_number"]),
            models.Index(fields=["created_on"]),
        ]

    def __str__(self):
        return f"{self.asset.name} v{self.version_number}"


class AssetTag(models.Model):
    """Custom tags for assets."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "core.Workspace",
        on_delete=models.CASCADE,
        related_name="asset_tags",
    )
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#3366CC")
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_tag"
        unique_together = ("workspace", "name")
        ordering = ("name",)

    def __str__(self):
        return self.name


class AssetPermission(models.Model):
    """Role-based permissions for assets."""

    ROLE_CHOICES = (
        ("viewer", _("Viewer")),
        ("editor", _("Editor")),
        ("owner", _("Owner")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="permissions",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="asset_permissions",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="granted_asset_permissions",
    )
    granted_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_permission"
        unique_together = ("asset", "user")
        ordering = ("granted_on",)

    def __str__(self):
        return f"{self.asset.name} - {self.user.username} ({self.role})"


class AssetShare(models.Model):
    """Asset sharing links and tokens."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    share_token = models.CharField(max_length=64, unique=True, db_index=True)
    shared_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="asset_shares",
    )
    shared_with_email = models.EmailField(null=True, blank=True)

    access_type = models.CharField(
        max_length=20,
        choices=(
            ("view", _("View Only")),
            ("download", _("Download")),
            ("edit", _("Edit")),
        ),
        default="view",
    )
    is_password_protected = models.BooleanField(default=False)
    password_hash = models.CharField(max_length=255, blank=True, default="")

    expires_on = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "asset_share"
        ordering = ("-created_on",)
        indexes = [
            models.Index(fields=["share_token"]),
            models.Index(fields=["asset", "-created_on"]),
        ]

    def __str__(self):
        return f"Share: {self.asset.name}"


class AssetActivity(models.Model):
    """Activity log for assets."""

    ACTION_CHOICES = (
        ("created", _("Created")),
        ("updated", _("Updated")),
        ("downloaded", _("Downloaded")),
        ("viewed", _("Viewed")),
        ("shared", _("Shared")),
        ("versioned", _("Versioned")),
        ("permission_changed", _("Permission Changed")),
        ("deleted", _("Deleted")),
        ("restored", _("Restored")),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="activities",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="asset_activities",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "asset_activity"
        ordering = ("-created_on",)
        indexes = [
            models.Index(fields=["asset", "-created_on"]),
            models.Index(fields=["user", "-created_on"]),
        ]

    def __str__(self):
        return f"{self.asset.name} - {self.action}"

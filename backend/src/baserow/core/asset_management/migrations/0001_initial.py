# Generated migration for asset management system

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.contrib.postgres.fields import ArrayField


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssetCategory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("color", models.CharField(default="#3366CC", max_length=7)),
                ("icon", models.CharField(default="folder", max_length=50)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_categories",
                        to="core.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "asset_category",
                "ordering": ("created_on",),
            },
        ),
        migrations.CreateModel(
            name="Asset",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("file", models.FileField(upload_to="assets/%Y/%m/%d/")),
                ("file_size", models.BigIntegerField(default=0)),
                ("file_type", models.CharField(max_length=100)),
                ("file_extension", models.CharField(max_length=20)),
                ("mime_type", models.CharField(max_length=100)),
                ("is_public", models.BooleanField(default=False)),
                ("is_archived", models.BooleanField(default=False)),
                ("download_count", models.IntegerField(default=0)),
                ("view_count", models.IntegerField(default=0)),
                ("tags", ArrayField(
                    base_field=models.CharField(max_length=100),
                    blank=True,
                    default=list,
                )),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                ("trashed", models.BooleanField(default=False)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assets",
                        to="asset_management.assetcategory",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owned_assets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assets",
                        to="core.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "asset",
                "ordering": ("-created_on",),
            },
        ),
        migrations.CreateModel(
            name="AssetVersion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("version_number", models.IntegerField()),
                ("file", models.FileField(upload_to="asset_versions/%Y/%m/%d/")),
                ("file_size", models.BigIntegerField()),
                ("mime_type", models.CharField(max_length=100)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("change_log", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="asset_management.asset",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="asset_versions_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "asset_version",
                "ordering": ("-version_number",),
                "unique_together": {("asset", "version_number")},
            },
        ),
        migrations.CreateModel(
            name="AssetTag",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("color", models.CharField(default="#3366CC", max_length=7)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_tags",
                        to="core.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "asset_tag",
                "ordering": ("name",),
                "unique_together": {("workspace", "name")},
            },
        ),
        migrations.CreateModel(
            name="AssetShare",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("share_token", models.CharField(db_index=True, max_length=64, unique=True)),
                ("shared_with_email", models.EmailField(blank=True, max_length=254, null=True)),
                (
                    "access_type",
                    models.CharField(
                        choices=[
                            ("view", "View Only"),
                            ("download", "Download"),
                            ("edit", "Edit"),
                        ],
                        default="view",
                        max_length=20,
                    ),
                ),
                ("is_password_protected", models.BooleanField(default=False)),
                ("password_hash", models.CharField(blank=True, default="", max_length=255)),
                ("expires_on", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to="asset_management.asset",
                    ),
                ),
                (
                    "shared_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_shares",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "asset_share",
                "ordering": ("-created_on",),
            },
        ),
        migrations.CreateModel(
            name="AssetPermission",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("viewer", "Viewer"),
                            ("editor", "Editor"),
                            ("owner", "Owner"),
                        ],
                        default="viewer",
                        max_length=20,
                    ),
                ),
                ("granted_on", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permissions",
                        to="asset_management.asset",
                    ),
                ),
                (
                    "granted_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="granted_asset_permissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asset_permissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "asset_permission",
                "ordering": ("granted_on",),
                "unique_together": {("asset", "user")},
            },
        ),
        migrations.CreateModel(
            name="AssetActivity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("updated", "Updated"),
                            ("downloaded", "Downloaded"),
                            ("viewed", "Viewed"),
                            ("shared", "Shared"),
                            ("versioned", "Versioned"),
                            ("permission_changed", "Permission Changed"),
                            ("deleted", "Deleted"),
                            ("restored", "Restored"),
                        ],
                        max_length=30,
                    ),
                ),
                ("description", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "asset",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activities",
                        to="asset_management.asset",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="asset_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "asset_activity",
                "ordering": ("-created_on",),
            },
        ),
        migrations.AddIndex(
            model_name="assetversion",
            index=models.Index(fields=["asset", "-version_number"], name="asset_versi_asset_id_b5d6e3_idx"),
        ),
        migrations.AddIndex(
            model_name="assetversion",
            index=models.Index(fields=["created_on"], name="asset_versi_created_8c4d2a_idx"),
        ),
        migrations.AddIndex(
            model_name="assetshare",
            index=models.Index(fields=["share_token"], name="asset_share_share_t_7f8d3c_idx"),
        ),
        migrations.AddIndex(
            model_name="assetshare",
            index=models.Index(fields=["asset", "-created_on"], name="asset_share_asset_i_9e5c1b_idx"),
        ),
        migrations.AddIndex(
            model_name="assetactivity",
            index=models.Index(fields=["asset", "-created_on"], name="asset_activ_asset_i_3d2f4e_idx"),
        ),
        migrations.AddIndex(
            model_name="assetactivity",
            index=models.Index(fields=["user", "-created_on"], name="asset_activ_user_id_6a8f2c_idx"),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["workspace", "-created_on"], name="asset_worksp_b7c3d1_idx"),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["owner", "-created_on"], name="asset_owner__5a9e2c_idx"),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["category", "-created_on"], name="asset_categ_3f1d2e_idx"),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=models.Index(fields=["is_archived"], name="asset_is_ar_8b2d4c_idx"),
        ),
    ]

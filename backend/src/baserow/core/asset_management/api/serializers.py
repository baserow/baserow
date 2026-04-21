from django.contrib.auth import get_user_model
from rest_framework import serializers

from ..models import (
    Asset,
    AssetActivity,
    AssetCategory,
    AssetPermission,
    AssetShare,
    AssetTag,
    AssetVersion,
)

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for asset endpoints."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name"]
        read_only_fields = fields


class AssetCategorySerializer(serializers.ModelSerializer):
    """Serializer for AssetCategory model."""

    class Meta:
        model = AssetCategory
        fields = [
            "id",
            "name",
            "description",
            "color",
            "icon",
            "created_on",
            "updated_on",
        ]
        read_only_fields = ["id", "created_on", "updated_on"]


class AssetVersionSerializer(serializers.ModelSerializer):
    """Serializer for AssetVersion model."""

    created_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = AssetVersion
        fields = [
            "id",
            "version_number",
            "file_size",
            "mime_type",
            "created_by",
            "created_on",
            "change_log",
        ]
        read_only_fields = fields


class AssetPermissionSerializer(serializers.ModelSerializer):
    """Serializer for AssetPermission model."""

    user = UserBasicSerializer(read_only=True)
    granted_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = AssetPermission
        fields = ["id", "user", "role", "granted_by", "granted_on"]
        read_only_fields = ["id", "granted_on"]


class AssetShareSerializer(serializers.ModelSerializer):
    """Serializer for AssetShare model."""

    shared_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = AssetShare
        fields = [
            "id",
            "share_token",
            "shared_by",
            "shared_with_email",
            "access_type",
            "is_password_protected",
            "expires_on",
            "is_active",
            "created_on",
        ]
        read_only_fields = [
            "id",
            "share_token",
            "shared_by",
            "created_on",
        ]
        extra_kwargs = {"password_hash": {"write_only": True}}


class AssetActivitySerializer(serializers.ModelSerializer):
    """Serializer for AssetActivity model."""

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = AssetActivity
        fields = ["id", "user", "action", "description", "created_on"]
        read_only_fields = fields


class AssetListSerializer(serializers.ModelSerializer):
    """Serializer for Asset list view."""

    owner = UserBasicSerializer(read_only=True)
    category = AssetCategorySerializer(read_only=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "description",
            "file_size",
            "file_type",
            "file_extension",
            "mime_type",
            "owner",
            "category",
            "is_public",
            "is_archived",
            "download_count",
            "view_count",
            "tags",
            "created_on",
            "updated_on",
        ]
        read_only_fields = [
            "id",
            "file_size",
            "file_type",
            "file_extension",
            "mime_type",
            "owner",
            "download_count",
            "view_count",
            "created_on",
            "updated_on",
        ]


class AssetDetailSerializer(serializers.ModelSerializer):
    """Serializer for Asset detail view."""

    owner = UserBasicSerializer(read_only=True)
    category = AssetCategorySerializer(read_only=True)
    permissions = AssetPermissionSerializer(read_only=True, many=True)
    versions = AssetVersionSerializer(read_only=True, many=True)
    activities = AssetActivitySerializer(read_only=True, many=True)

    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "description",
            "file",
            "file_size",
            "file_type",
            "file_extension",
            "mime_type",
            "owner",
            "category",
            "is_public",
            "is_archived",
            "download_count",
            "view_count",
            "tags",
            "metadata",
            "permissions",
            "versions",
            "activities",
            "created_on",
            "updated_on",
        ]
        read_only_fields = [
            "id",
            "file_size",
            "file_type",
            "file_extension",
            "mime_type",
            "owner",
            "download_count",
            "view_count",
            "created_on",
            "updated_on",
        ]


class AssetCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating assets."""

    class Meta:
        model = Asset
        fields = [
            "name",
            "description",
            "file",
            "category",
            "tags",
            "is_public",
            "metadata",
        ]


class AssetUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating assets."""

    class Meta:
        model = Asset
        fields = [
            "name",
            "description",
            "category",
            "tags",
            "is_public",
            "is_archived",
            "metadata",
        ]

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils.text import slugify

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.models import Workspace

from .exceptions import (
    AssetCategoryDoesNotExist,
    AssetDoesNotExist,
    AssetPermissionDoesNotExist,
    AssetShareDoesNotExist,
    AssetVersionNotFound,
    InvalidAssetShareToken,
    UserCannotAccessAsset,
)
from .models import (
    Asset,
    AssetActivity,
    AssetCategory,
    AssetPermission,
    AssetShare,
    AssetTag,
    AssetVersion,
)

User = get_user_model()


class AssetHandler:
    """Handler for asset management operations."""

    @staticmethod
    def get_assets_for_user(user: User, workspace: Workspace) -> QuerySet:
        """Get all assets accessible by a user in a workspace."""
        if not user.workspaceuser_set.filter(workspace=workspace).exists():
            raise UserNotInWorkspace()

        return Asset.objects.filter(
            Q(workspace=workspace)
            & (Q(owner=user) | Q(permissions__user=user) | Q(is_public=True))
        ).distinct()

    @staticmethod
    def get_asset(asset_id, user: User, workspace: Workspace) -> Asset:
        """Get a specific asset, checking permissions."""
        try:
            asset = Asset.objects.get(id=asset_id, workspace=workspace)
        except Asset.DoesNotExist:
            raise AssetDoesNotExist()

        if not AssetHandler.user_can_access_asset(user, asset):
            raise UserCannotAccessAsset()

        return asset

    @staticmethod
    def user_can_access_asset(user: User, asset: Asset, min_role: str = "viewer"):
        """Check if user has permission to access an asset."""
        if asset.owner == user:
            return True

        if asset.is_public and min_role == "viewer":
            return True

        permission = asset.permissions.filter(user=user).first()
        if not permission:
            return False

        role_hierarchy = {"viewer": 0, "editor": 1, "owner": 2}
        return role_hierarchy.get(permission.role, -1) >= role_hierarchy.get(
            min_role, -1
        )

    @staticmethod
    def create_asset(
        user: User,
        workspace: Workspace,
        name: str,
        file,
        description: str = "",
        category_id: Optional[str] = None,
        tags: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> Asset:
        """Create a new asset."""
        if not user.workspaceuser_set.filter(workspace=workspace).exists():
            raise UserNotInWorkspace()

        category = None
        if category_id:
            try:
                category = AssetCategory.objects.get(
                    id=category_id, workspace=workspace
                )
            except AssetCategory.DoesNotExist:
                raise AssetCategoryDoesNotExist()

        file_name = file.name if hasattr(file, "name") else "file"
        file_extension = os.path.splitext(file_name)[1].lstrip(".")
        mime_type = getattr(file, "content_type", "application/octet-stream")
        file_size = file.size if hasattr(file, "size") else 0

        asset = Asset.objects.create(
            name=name,
            description=description,
            file=file,
            file_size=file_size,
            file_type="file",
            file_extension=file_extension,
            mime_type=mime_type,
            workspace=workspace,
            owner=user,
            category=category,
            tags=tags or [],
            metadata=metadata or {},
        )

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="created",
            description=f"Asset '{asset.name}' created",
        )

        AssetVersion.objects.create(
            asset=asset,
            version_number=1,
            file=asset.file,
            file_size=file_size,
            mime_type=mime_type,
            created_by=user,
        )

        return asset

    @staticmethod
    def update_asset(
        user: User,
        asset: Asset,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category_id: Optional[str] = None,
        tags: Optional[list] = None,
        is_public: Optional[bool] = None,
        is_archived: Optional[bool] = None,
        metadata: Optional[dict] = None,
    ) -> Asset:
        """Update an asset."""
        if not AssetHandler.user_can_access_asset(user, asset, "editor"):
            raise UserCannotAccessAsset()

        if name is not None:
            asset.name = name
        if description is not None:
            asset.description = description
        if tags is not None:
            asset.tags = tags
        if is_public is not None:
            asset.is_public = is_public
        if is_archived is not None:
            asset.is_archived = is_archived
        if metadata is not None:
            asset.metadata = metadata

        if category_id is not None:
            try:
                asset.category = AssetCategory.objects.get(
                    id=category_id, workspace=asset.workspace
                )
            except AssetCategory.DoesNotExist:
                raise AssetCategoryDoesNotExist()

        asset.save()

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="updated",
            description="Asset metadata updated",
        )

        return asset

    @staticmethod
    def delete_asset(user: User, asset: Asset, permanently: bool = False) -> None:
        """Delete or trash an asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        if permanently:
            asset.permanently_delete()
            AssetActivity.objects.create(
                asset=asset,
                user=user,
                action="deleted",
                description="Asset permanently deleted",
            )
        else:
            asset.delete()
            AssetActivity.objects.create(
                asset=asset,
                user=user,
                action="deleted",
                description="Asset moved to trash",
            )

    @staticmethod
    def restore_asset(user: User, asset: Asset) -> Asset:
        """Restore a trashed asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        asset.trashed = False
        asset.save()

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="restored",
            description="Asset restored from trash",
        )

        return asset

    @staticmethod
    def upload_new_version(
        user: User,
        asset: Asset,
        file,
        change_log: str = "",
    ) -> AssetVersion:
        """Upload a new version of an asset."""
        if not AssetHandler.user_can_access_asset(user, asset, "editor"):
            raise UserCannotAccessAsset()

        version_number = asset.versions.count() + 1
        file_size = file.size if hasattr(file, "size") else 0
        mime_type = getattr(file, "content_type", "application/octet-stream")

        version = AssetVersion.objects.create(
            asset=asset,
            version_number=version_number,
            file=file,
            file_size=file_size,
            mime_type=mime_type,
            created_by=user,
            change_log=change_log,
        )

        asset.file = file
        asset.file_size = file_size
        asset.mime_type = mime_type
        asset.save()

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="versioned",
            description=f"New version uploaded (v{version_number})",
        )

        return version

    @staticmethod
    def get_asset_versions(user: User, asset: Asset) -> QuerySet:
        """Get all versions of an asset."""
        if not AssetHandler.user_can_access_asset(user, asset):
            raise UserCannotAccessAsset()

        return asset.versions.all()

    @staticmethod
    def rollback_to_version(
        user: User, asset: Asset, version_id: str
    ) -> AssetVersion:
        """Rollback asset to a specific version."""
        if not AssetHandler.user_can_access_asset(user, asset, "editor"):
            raise UserCannotAccessAsset()

        try:
            version = asset.versions.get(id=version_id)
        except AssetVersion.DoesNotExist:
            raise AssetVersionNotFound()

        new_version = AssetVersion.objects.create(
            asset=asset,
            version_number=asset.versions.count() + 1,
            file=version.file,
            file_size=version.file_size,
            mime_type=version.mime_type,
            created_by=user,
            change_log=f"Rolled back to version {version.version_number}",
        )

        asset.file = version.file
        asset.file_size = version.file_size
        asset.mime_type = version.mime_type
        asset.save()

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="versioned",
            description=f"Rolled back to version {version.version_number}",
        )

        return new_version


class AssetPermissionHandler:
    """Handler for asset permission management."""

    @staticmethod
    def grant_permission(
        user: User,
        asset: Asset,
        target_user: User,
        role: str = "viewer",
    ) -> AssetPermission:
        """Grant permission to a user for an asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        if role not in ["viewer", "editor", "owner"]:
            raise ValueError("Invalid role")

        permission, _ = AssetPermission.objects.update_or_create(
            asset=asset,
            user=target_user,
            defaults={"role": role, "granted_by": user},
        )

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="permission_changed",
            description=f"Granted {role} permission to {target_user.email}",
        )

        return permission

    @staticmethod
    def revoke_permission(user: User, asset: Asset, target_user: User) -> None:
        """Revoke permission for a user."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        try:
            permission = AssetPermission.objects.get(asset=asset, user=target_user)
            permission.delete()

            AssetActivity.objects.create(
                asset=asset,
                user=user,
                action="permission_changed",
                description=f"Revoked permission for {target_user.email}",
            )
        except AssetPermission.DoesNotExist:
            raise AssetPermissionDoesNotExist()

    @staticmethod
    def get_asset_permissions(user: User, asset: Asset) -> QuerySet:
        """Get all permissions for an asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        return asset.permissions.all()


class AssetShareHandler:
    """Handler for asset sharing."""

    @staticmethod
    def create_share(
        user: User,
        asset: Asset,
        access_type: str = "view",
        expires_on: Optional[datetime] = None,
        password: Optional[str] = None,
        shared_with_email: Optional[str] = None,
    ) -> AssetShare:
        """Create a shareable link for an asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        share_token = secrets.token_urlsafe(32)
        password_hash = ""

        if password:
            password_hash = hashlib.sha256(password.encode()).hexdigest()

        share = AssetShare.objects.create(
            asset=asset,
            share_token=share_token,
            shared_by=user,
            shared_with_email=shared_with_email,
            access_type=access_type,
            is_password_protected=bool(password),
            password_hash=password_hash,
            expires_on=expires_on,
        )

        AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="shared",
            description=f"Asset shared with access type: {access_type}",
        )

        return share

    @staticmethod
    def get_share_by_token(token: str, password: Optional[str] = None) -> AssetShare:
        """Get a share by token, validating password if required."""
        try:
            share = AssetShare.objects.get(share_token=token)
        except AssetShare.DoesNotExist:
            raise InvalidAssetShareToken()

        if not share.is_active:
            raise InvalidAssetShareToken()

        if share.expires_on and share.expires_on < datetime.now(timezone.utc):
            raise InvalidAssetShareToken()

        if share.is_password_protected:
            if not password:
                raise InvalidAssetShareToken()

            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash != share.password_hash:
                raise InvalidAssetShareToken()

        return share

    @staticmethod
    def revoke_share(user: User, share: AssetShare) -> None:
        """Revoke a share link."""
        if share.asset.owner != user:
            raise UserCannotAccessAsset()

        share.is_active = False
        share.save()

        AssetActivity.objects.create(
            asset=share.asset,
            user=user,
            action="shared",
            description="Share link revoked",
        )

    @staticmethod
    def get_asset_shares(user: User, asset: Asset) -> QuerySet:
        """Get all shares for an asset."""
        if asset.owner != user:
            raise UserCannotAccessAsset()

        return asset.shares.all()


class AssetCategoryHandler:
    """Handler for asset category management."""

    @staticmethod
    def create_category(
        user: User,
        workspace: Workspace,
        name: str,
        description: str = "",
        color: str = "#3366CC",
        icon: str = "folder",
    ) -> AssetCategory:
        """Create a new asset category."""
        if not user.workspaceuser_set.filter(workspace=workspace).exists():
            raise UserNotInWorkspace()

        category = AssetCategory.objects.create(
            name=name,
            description=description,
            workspace=workspace,
            color=color,
            icon=icon,
        )

        return category

    @staticmethod
    def update_category(
        user: User,
        category: AssetCategory,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> AssetCategory:
        """Update an asset category."""
        if not user.workspaceuser_set.filter(
            workspace=category.workspace
        ).exists():
            raise UserNotInWorkspace()

        if name is not None:
            category.name = name
        if description is not None:
            category.description = description
        if color is not None:
            category.color = color
        if icon is not None:
            category.icon = icon

        category.save()
        return category

    @staticmethod
    def delete_category(user: User, category: AssetCategory) -> None:
        """Delete an asset category."""
        if not user.workspaceuser_set.filter(
            workspace=category.workspace
        ).exists():
            raise UserNotInWorkspace()

        category.delete()

    @staticmethod
    def get_workspace_categories(
        user: User, workspace: Workspace
    ) -> QuerySet:
        """Get all categories in a workspace."""
        if not user.workspaceuser_set.filter(workspace=workspace).exists():
            raise UserNotInWorkspace()

        return AssetCategory.objects.filter(workspace=workspace)


class AssetActivityHandler:
    """Handler for asset activity logging."""

    @staticmethod
    def log_download(user: User, asset: Asset) -> AssetActivity:
        """Log a download action."""
        asset.download_count += 1
        asset.save()

        return AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="downloaded",
            description=f"Asset downloaded",
        )

    @staticmethod
    def log_view(user: Optional[User], asset: Asset) -> AssetActivity:
        """Log a view action."""
        asset.view_count += 1
        asset.save()

        return AssetActivity.objects.create(
            asset=asset,
            user=user,
            action="viewed",
            description="Asset viewed",
        )

    @staticmethod
    def get_asset_activity(
        user: User, asset: Asset, limit: int = 50
    ) -> QuerySet:
        """Get activity log for an asset."""
        if not AssetHandler.user_can_access_asset(user, asset):
            raise UserCannotAccessAsset()

        return asset.activities.all()[:limit]

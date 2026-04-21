from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from baserow.core.models import Workspace
from baserow.core.exceptions import UserNotInWorkspace

from ..exceptions import (
    AssetCategoryDoesNotExist,
    AssetDoesNotExist,
    AssetVersionNotFound,
    InvalidAssetShareToken,
    UserCannotAccessAsset,
)
from ..handlers import (
    AssetActivityHandler,
    AssetCategoryHandler,
    AssetHandler,
    AssetPermissionHandler,
    AssetShareHandler,
)
from ..models import Asset, AssetCategory, AssetShare, AssetVersion
from .serializers import (
    AssetActivitySerializer,
    AssetCategorySerializer,
    AssetCreateSerializer,
    AssetDetailSerializer,
    AssetListSerializer,
    AssetPermissionSerializer,
    AssetShareSerializer,
    AssetUpdateSerializer,
    AssetVersionSerializer,
)


class AssetViewSet(viewsets.ModelViewSet):
    """ViewSet for asset management."""

    parser_classes = (MultiPartParser,)
    permission_classes = []

    def get_serializer_class(self):
        if self.action == "create":
            return AssetCreateSerializer
        elif self.action == "update" or self.action == "partial_update":
            return AssetUpdateSerializer
        elif self.action == "retrieve":
            return AssetDetailSerializer
        else:
            return AssetListSerializer

    def get_queryset(self):
        workspace_id = self.kwargs.get("workspace_id")
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            return AssetHandler.get_assets_for_user(self.request.user, workspace)
        except UserNotInWorkspace:
            raise PermissionDenied()

    def list(self, request, workspace_id=None):
        """List all assets for the user in a workspace."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            queryset = AssetHandler.get_assets_for_user(request.user, workspace)
        except UserNotInWorkspace:
            raise PermissionDenied()

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, workspace_id=None):
        """Create a new asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        if "file" not in request.FILES:
            raise ValidationError({"file": "File is required."})

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            asset = AssetHandler.create_asset(
                user=request.user,
                workspace=workspace,
                name=serializer.validated_data["name"],
                file=request.FILES["file"],
                description=serializer.validated_data.get("description", ""),
                category_id=serializer.validated_data.get("category"),
                tags=serializer.validated_data.get("tags", []),
                metadata=serializer.validated_data.get("metadata", {}),
            )
        except (UserNotInWorkspace, AssetCategoryDoesNotExist) as e:
            raise ValidationError(str(e))

        detail_serializer = AssetDetailSerializer(asset)
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, workspace_id=None, pk=None):
        """Retrieve a specific asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        serializer = self.get_serializer(asset)
        return Response(serializer.data)

    def update(self, request, workspace_id=None, pk=None):
        """Update an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            asset = AssetHandler.update_asset(
                user=request.user,
                asset=asset,
                **serializer.validated_data,
            )
        except (UserCannotAccessAsset, AssetCategoryDoesNotExist) as e:
            raise ValidationError(str(e))

        detail_serializer = AssetDetailSerializer(asset)
        return Response(detail_serializer.data)

    def destroy(self, request, workspace_id=None, pk=None):
        """Delete an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            AssetHandler.delete_asset(request.user, asset)
        except UserCannotAccessAsset:
            raise PermissionDenied()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def restore(self, request, workspace_id=None, pk=None):
        """Restore a trashed asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = Asset.objects.get(id=pk, workspace=workspace)
        except Asset.DoesNotExist:
            raise PermissionDenied()

        try:
            asset = AssetHandler.restore_asset(request.user, asset)
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetDetailSerializer(asset)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def download(self, request, workspace_id=None, pk=None):
        """Download an asset and log the action."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        AssetActivityHandler.log_download(request.user, asset)

        return Response(
            {
                "download_url": asset.file.url,
                "file_name": asset.name,
            }
        )

    @action(detail=True, methods=["get"])
    def versions(self, request, workspace_id=None, pk=None):
        """Get all versions of an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        versions = AssetHandler.get_asset_versions(request.user, asset)
        serializer = AssetVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def upload_version(self, request, workspace_id=None, pk=None):
        """Upload a new version of an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        if "file" not in request.FILES:
            raise ValidationError({"file": "File is required."})

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            version = AssetHandler.upload_new_version(
                user=request.user,
                asset=asset,
                file=request.FILES["file"],
                change_log=request.data.get("change_log", ""),
            )
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetVersionSerializer(version)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def rollback_version(self, request, workspace_id=None, pk=None):
        """Rollback asset to a specific version."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        version_id = request.data.get("version_id")
        if not version_id:
            raise ValidationError({"version_id": "Version ID is required."})

        try:
            asset = AssetHandler.get_asset(pk, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            version = AssetHandler.rollback_to_version(request.user, asset, version_id)
        except (UserCannotAccessAsset, AssetVersionNotFound):
            raise ValidationError("Unable to rollback version.")

        serializer = AssetVersionSerializer(version)
        return Response(serializer.data)


class AssetCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for asset categories."""

    serializer_class = AssetCategorySerializer
    permission_classes = []

    def get_queryset(self):
        workspace_id = self.kwargs.get("workspace_id")
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            return AssetCategoryHandler.get_workspace_categories(
                self.request.user, workspace
            )
        except UserNotInWorkspace:
            raise PermissionDenied()

    def create(self, request, workspace_id=None):
        """Create a new asset category."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            category = AssetCategoryHandler.create_category(
                user=request.user,
                workspace=workspace,
                **serializer.validated_data,
            )
        except UserNotInWorkspace:
            raise PermissionDenied()

        serializer = self.get_serializer(category)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, workspace_id=None, pk=None):
        """Update an asset category."""
        workspace = get_object_or_404(Workspace, id=workspace_id)
        category = get_object_or_404(AssetCategory, id=pk, workspace=workspace)

        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        try:
            category = AssetCategoryHandler.update_category(
                user=request.user,
                category=category,
                **serializer.validated_data,
            )
        except UserNotInWorkspace:
            raise PermissionDenied()

        serializer = self.get_serializer(category)
        return Response(serializer.data)

    def destroy(self, request, workspace_id=None, pk=None):
        """Delete an asset category."""
        workspace = get_object_or_404(Workspace, id=workspace_id)
        category = get_object_or_404(AssetCategory, id=pk, workspace=workspace)

        try:
            AssetCategoryHandler.delete_category(request.user, category)
        except UserNotInWorkspace:
            raise PermissionDenied()

        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetPermissionViewSet(viewsets.ViewSet):
    """ViewSet for asset permissions."""

    permission_classes = []

    @action(detail=False, methods=["get"])
    def list(self, request, workspace_id=None, asset_id=None):
        """Get permissions for an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            permissions = AssetPermissionHandler.get_asset_permissions(
                request.user, asset
            )
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetPermissionSerializer(permissions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def grant(self, request, workspace_id=None, asset_id=None):
        """Grant permission to a user."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        user_id = request.data.get("user_id")
        role = request.data.get("role", "viewer")

        if not user_id or not role:
            raise ValidationError(
                {"detail": "user_id and role are required."}
            )

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({"user_id": "User not found."})

        try:
            permission = AssetPermissionHandler.grant_permission(
                request.user, asset, target_user, role
            )
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetPermissionSerializer(permission)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def revoke(self, request, workspace_id=None, asset_id=None):
        """Revoke permission for a user."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        user_id = request.data.get("user_id")
        if not user_id:
            raise ValidationError({"user_id": "user_id is required."})

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValidationError({"user_id": "User not found."})

        try:
            AssetPermissionHandler.revoke_permission(request.user, asset, target_user)
        except UserCannotAccessAsset:
            raise PermissionDenied()

        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetShareViewSet(viewsets.ViewSet):
    """ViewSet for asset sharing."""

    permission_classes = []

    @action(detail=False, methods=["get"])
    def list(self, request, workspace_id=None, asset_id=None):
        """Get all shares for an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            shares = AssetShareHandler.get_asset_shares(request.user, asset)
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetShareSerializer(shares, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def create_share(self, request, workspace_id=None, asset_id=None):
        """Create a share link for an asset."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
        except (AssetDoesNotExist, UserCannotAccessAsset):
            raise PermissionDenied()

        try:
            share = AssetShareHandler.create_share(
                user=request.user,
                asset=asset,
                access_type=request.data.get("access_type", "view"),
                expires_on=request.data.get("expires_on"),
                password=request.data.get("password"),
                shared_with_email=request.data.get("shared_with_email"),
            )
        except UserCannotAccessAsset:
            raise PermissionDenied()

        serializer = AssetShareSerializer(share)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def revoke_share(self, request, workspace_id=None, asset_id=None):
        """Revoke a share link."""
        workspace = get_object_or_404(Workspace, id=workspace_id)

        share_id = request.data.get("share_id")
        if not share_id:
            raise ValidationError({"share_id": "share_id is required."})

        try:
            asset = AssetHandler.get_asset(asset_id, request.user, workspace)
            share = AssetShare.objects.get(id=share_id, asset=asset)
        except (AssetDoesNotExist, AssetShare.DoesNotExist):
            raise PermissionDenied()

        try:
            AssetShareHandler.revoke_share(request.user, share)
        except UserCannotAccessAsset:
            raise PermissionDenied()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="access")
    def access_shared_asset(self, request):
        """Access an asset via share token."""
        token = request.data.get("token")
        password = request.data.get("password")

        if not token:
            raise ValidationError({"token": "Share token is required."})

        try:
            share = AssetShareHandler.get_share_by_token(token, password)
        except InvalidAssetShareToken:
            raise ValidationError({"token": "Invalid or expired share token."})

        serializer = AssetShareSerializer(share)
        return Response(serializer.data)

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AssetViewSet,
    AssetCategoryViewSet,
    AssetPermissionViewSet,
    AssetShareViewSet,
)

app_name = "asset_management"

router = DefaultRouter()

urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/assets/",
        AssetViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
        name="asset_list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/",
        AssetViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="asset_detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/download/",
        AssetViewSet.as_view({"post": "download"}),
        name="asset_download",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/restore/",
        AssetViewSet.as_view({"post": "restore"}),
        name="asset_restore",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/versions/",
        AssetViewSet.as_view({"get": "versions"}),
        name="asset_versions",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/upload_version/",
        AssetViewSet.as_view({"post": "upload_version"}),
        name="asset_upload_version",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:pk>/rollback_version/",
        AssetViewSet.as_view({"post": "rollback_version"}),
        name="asset_rollback_version",
    ),
    path(
        "workspaces/<uuid:workspace_id>/asset-categories/",
        AssetCategoryViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
        name="asset_category_list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/asset-categories/<uuid:pk>/",
        AssetCategoryViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="asset_category_detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/permissions/",
        AssetPermissionViewSet.as_view({"get": "list"}),
        name="asset_permissions_list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/permissions/grant/",
        AssetPermissionViewSet.as_view({"post": "grant"}),
        name="asset_permissions_grant",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/permissions/revoke/",
        AssetPermissionViewSet.as_view({"post": "revoke"}),
        name="asset_permissions_revoke",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/shares/",
        AssetShareViewSet.as_view({"get": "list"}),
        name="asset_shares_list",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/shares/create_share/",
        AssetShareViewSet.as_view({"post": "create_share"}),
        name="asset_shares_create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/<uuid:asset_id>/shares/revoke_share/",
        AssetShareViewSet.as_view({"post": "revoke_share"}),
        name="asset_shares_revoke",
    ),
    path(
        "workspaces/<uuid:workspace_id>/assets/shares/access/",
        AssetShareViewSet.as_view({"post": "access_shared_asset"}),
        name="asset_shares_access",
    ),
]

from django.http import Http404

from baserow.core.exceptions import InstanceDoesNotExist, UserNotInWorkspace


class AssetDoesNotExist(InstanceDoesNotExist):
    """Raised when an asset does not exist."""

    pass


class AssetCategoryDoesNotExist(InstanceDoesNotExist):
    """Raised when an asset category does not exist."""

    pass


class AssetPermissionDoesNotExist(InstanceDoesNotExist):
    """Raised when an asset permission does not exist."""

    pass


class AssetShareDoesNotExist(InstanceDoesNotExist):
    """Raised when an asset share does not exist."""

    pass


class UserCannotAccessAsset(Exception):
    """Raised when a user does not have permission to access an asset."""

    pass


class InvalidAssetShareToken(Exception):
    """Raised when an asset share token is invalid or expired."""

    pass


class AssetVersionNotFound(InstanceDoesNotExist):
    """Raised when an asset version does not exist."""

    pass

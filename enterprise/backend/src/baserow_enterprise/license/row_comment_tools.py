from baserow.core.models import Workspace
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler


class RowCommentToolLicense:
    """Workspace licence shared by the Kuma and Agent row comment tools."""

    unavailable_reason = "this workspace lacks an Advanced or Enterprise license"

    @staticmethod
    def is_deactivated(workspace: Workspace) -> bool:
        return not LicenseHandler.workspace_has_feature(RBAC, workspace)

    @staticmethod
    def raise_if_deactivated(workspace: Workspace) -> None:
        LicenseHandler.raise_if_workspace_doesnt_have_feature(RBAC, workspace)

from typing import Optional

from django.contrib.auth.models import AbstractUser

from baserow_premium.license.handler import LicenseHandler
from rest_framework.exceptions import PermissionDenied

from baserow.core.handler import CoreHandler
from baserow_enterprise.audit_log.operations import (
    ListWorkspaceAuditLogEntriesOperationType,
)
from baserow_enterprise.features import AUDIT_LOG


def check_for_license_and_permissions_or_raise(
    user: AbstractUser, workspace_id: Optional[int] = None
):
    """
    Check if the user has the feature enabled and has the correct permissions to list
    audit log entries. If not, an exception is raised.
    """

    if workspace_id is not None:
        workspace = CoreHandler().get_workspace(workspace_id)
        LicenseHandler.raise_if_user_doesnt_have_feature(AUDIT_LOG, user, workspace)
        if not user.is_staff:
            CoreHandler().check_permissions(
                user,
                ListWorkspaceAuditLogEntriesOperationType.type,
                workspace=workspace,
                context=workspace,
            )
    else:
        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(AUDIT_LOG, user)
        if not user.is_staff:
            raise PermissionDenied()

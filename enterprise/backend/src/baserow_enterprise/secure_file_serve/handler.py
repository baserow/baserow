from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.signing import BadSignature, SignatureExpired

from baserow.core.handler import CoreHandler
from baserow.core.operations import ReadWorkspaceOperationType
from baserow.core.storage import get_default_storage
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission
from baserow_enterprise.secure_file_serve.exceptions import SecureFileServeException
from baserow_enterprise.secure_file_serve.storage import (
    EnterpriseFileStorage,
    SecureFileServeSignerPayload,
)

User = get_user_model()


@dataclass
class SecureFile:
    name: str
    path: str

    def open(self, mode="rb"):
        storage = get_default_storage()
        return storage.open(self.path, mode)


class SecureFileServeHandler:
    def unsign_data(self, signed_path: str) -> SecureFileServeSignerPayload:
        """
        Unsign the signed data and returns the payload. If the signature is invalid or
        expired, a SecureFileServeException is raised.

        :param signed_path: The signed data to unsign.
        :return: The payload extracted from the signed data.
        :raises SecureFileServeException: If the signature is invalid or expired.
        """

        try:
            unsigned_data = EnterpriseFileStorage.unsign_data(signed_path)
        except SignatureExpired:
            raise SecureFileServeException("File expired")
        except BadSignature:
            raise SecureFileServeException("Invalid signature")
        return unsigned_data

    def raise_if_user_does_not_have_permissions(
        self, user: AbstractUser, data: SecureFileServeSignerPayload
    ):
        if (
            settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION
            == SecureFileServePermission.DISABLED
        ):
            return

        if not user.is_authenticated:
            raise SecureFileServeException("User is not authenticated")

        workspace_id = data.workspace_id
        # Allow staff users to download files without workspace check
        # otherwise they won't be able to access files like audit logs etc
        if user.is_staff and workspace_id is None:
            return

        if (
            settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION
            == SecureFileServePermission.WORKSPACE_ACCESS
        ):
            if not workspace_id:
                raise SecureFileServeException("Workspace id is required")

            workspace = CoreHandler().get_workspace(workspace_id)

            has_permission = CoreHandler().check_permissions(
                user,
                ReadWorkspaceOperationType.type,
                workspace=workspace,
                context=workspace,
                raise_permission_exceptions=False,
            )

            if not has_permission:
                raise SecureFileServeException("Can't access file")

    def get_file_path(self, data: SecureFileServeSignerPayload) -> str:
        storage = get_default_storage()
        file_path = data.name

        if not storage.exists(file_path):
            raise SecureFileServeException("File does not exist")
        return file_path

    def get_file_name(self, file_path: str) -> str:
        if not file_path:
            return ""
        return file_path.split("/")[-1]

    def extract_file_info_or_raise(
        self, user: AbstractUser, signed_data: str
    ) -> SecureFile:
        """
        Extracts the file name and the file path from the signed data or raises an
        exception if the user does not have access to the file or the signature is
        expired or invalid.

        :param user: The user that must be in the workspace.
        :param signed_data: The signed data extracted from the URL.
        :return: The file info object containing the file name and the file path.
        :raises SecureFileServeException: If the user does not have access to the file
            or the signature is expired or invalid.
        """

        unsigned_data = self.unsign_data(signed_data)
        self.raise_if_user_does_not_have_permissions(user, unsigned_data)
        file_path = self.get_file_path(unsigned_data)
        file_name = self.get_file_name(file_path)
        return SecureFile(file_name, file_path)

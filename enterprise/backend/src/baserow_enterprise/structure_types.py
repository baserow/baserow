from typing import TYPE_CHECKING, Any

from django.contrib.contenttypes.models import ContentType

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.views.models import View
from baserow.core.models import Application
from baserow.core.registries import ImportExportConfig, SerializationProcessorType
from baserow.core.types import SerializationProcessorScope
from baserow.core.utils import atomic_if_not_already
from baserow_enterprise.features import RBAC
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.role.types import NewRoleAssignment

if TYPE_CHECKING:
    from baserow.core.models import Workspace


class EnterpriseExportSerializedStructure:
    @staticmethod
    def role_assignment(subject_id, subject_type_id, role_id):
        return {
            "subject_id": subject_id,
            "subject_type_id": subject_type_id,
            "role_id": role_id,
        }


class RoleAssignmentSerializationProcessorType(SerializationProcessorType):
    type = "role_assignment_serialization_processors"
    structure = EnterpriseExportSerializedStructure

    @classmethod
    def import_serialized(
        cls,
        workspace: "Workspace",
        scope: SerializationProcessorScope,
        serialized_scope: dict,
        import_export_config: ImportExportConfig,
    ):
        """
        Responsible for importing any `role_assignments` in `serialized_scope`
        into a newly restored/duplicated scope in `scope`.
        """

        if not import_export_config.include_permission_data:
            # We cannot yet export RBAC roles to another workspace as we would also need
            # to export all subjects to the new workspace also or somehow allow to user
            # to choose how to map subjects.
            return

        # Application subclass scopes can't be passed to
        # the role assignment handler. See #1624.
        if isinstance(scope, Application):
            scope = getattr(scope, "application_ptr", scope)

        # View subclass scopes can't be passed to the role assignment handler because
        # the permissions are stored on the `View` level.
        if isinstance(scope, View):
            scope = getattr(scope, "view_ptr", scope)

        serialized_role_assignments = serialized_scope.get("role_assignments", [])

        with atomic_if_not_already():
            new_role_assignments = []
            for serialized_role_assignment in serialized_role_assignments:
                subject_type = ContentType.objects.get(
                    pk=serialized_role_assignment["subject_type_id"]
                )
                subject = subject_type.model_class().objects.get(
                    pk=serialized_role_assignment["subject_id"]
                )
                role = Role.objects.get(pk=serialized_role_assignment["role_id"])
                new_role_assignments.append(NewRoleAssignment(subject, role, scope))
            RoleAssignmentHandler().assign_role_batch(
                workspace, new_role_assignments, send_signals=False
            )

    @classmethod
    def export_serialized(
        cls,
        workspace: "Workspace",
        scope: SerializationProcessorScope,
        import_export_config: ImportExportConfig,
    ) -> dict[str, Any]:
        """
        Exports the `role_assignments` in `scope` when it is being exported
        by an application type `export_serialized`.
        """

        if not import_export_config.include_permission_data:
            # We cannot yet export RBAC roles to another workspace as we would also need
            # to export all subjects to the new workspace also or somehow allow to user
            # to choose how to map subjects.
            return

        # Do not export anything if the workspace doesn't have RBAC enabled.
        if not LicenseHandler.workspace_has_feature(RBAC, workspace):
            return {}

        # Application subclass scopes can't be passed to
        # the role assignment handler. See #1624.
        if isinstance(scope, Application):
            scope = getattr(scope, "application_ptr", scope)

        # View subclass scopes can't be passed to the role assignment handler because
        # the permissions are stored on the `View` level.
        if isinstance(scope, View):
            scope = getattr(scope, "view_ptr", scope)

        serialized_role_assignments = []
        role_assignments = RoleAssignmentHandler().get_role_assignments(
            workspace, scope
        )
        for role_assignment in role_assignments:
            serialized_role_assignments.append(
                EnterpriseExportSerializedStructure.role_assignment(
                    subject_id=role_assignment.subject_id,
                    subject_type_id=role_assignment.subject_type_id,
                    role_id=role_assignment.role.id,
                )
            )

        return {"role_assignments": serialized_role_assignments}

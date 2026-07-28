from collections import defaultdict
from dataclasses import dataclass
from typing import TypedDict

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
from baserow.core.cache import local_cache
from baserow.core.handler import CoreHandler
from baserow.core.registries import (
    permission_manager_type_registry,
    subject_type_registry,
)
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.exceptions import SubjectNotExist, SubjectUnsupported
from baserow_enterprise.field_permissions.models import (
    FieldPermissions,
    FieldPermissionsRoleEnum,
)
from baserow_enterprise.field_permissions.operations import (
    ReadFieldPermissionsOperationType,
    UpdateFieldPermissionsOperationType,
)
from baserow_enterprise.field_permissions.permission_manager import (
    FieldPermissionManagerType,
)
from baserow_enterprise.role.constants import FIELD_PERMISSION_EDITOR_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import RoleAssignment
from baserow_enterprise.signals import field_permissions_updated
from baserow_enterprise.teams.subjects import TeamSubjectType


class FieldPermissionSubjectIdentifier(TypedDict):
    subject_id: int
    subject_type: str


@dataclass
class FieldPermissionUpdated:
    user: AbstractUser
    field: Field
    role: str
    allow_in_forms: bool
    can_write_values: bool
    subjects: list[RoleAssignment]


class FieldPermissionsHandler:
    allowed_subject_types = {UserSubjectType.type, TeamSubjectType.type}

    @classmethod
    def _check_valid_role_value_or_raise(cls, role: str):
        """
        Validates the provided role and returns the corresponding
        FieldPermissionsRoleEnum.

        :param role: The role to validate.
        :raises ValueError if the role is not valid.
        """

        try:
            FieldPermissionsRoleEnum(role)
        except ValueError:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of {list(FieldPermissionsRoleEnum.__members__.keys())}."
            )

    @classmethod
    def _get_field_permission_subjects(cls, field: Field) -> list[RoleAssignment]:
        """Returns the users and teams explicitly allowed to edit the field."""

        # Field subclasses use multi-table inheritance. Always scope assignments to
        # the base Field model so that the same assignments are found regardless of
        # whether the caller has a specific or base field instance.
        field_content_type = ContentType.objects.get_for_model(Field)
        return list(
            RoleAssignment.objects.filter(
                workspace=field.table.database.workspace,
                scope_id=field.id,
                scope_type=field_content_type,
                role__uid=FIELD_PERMISSION_EDITOR_ROLE_UID,
            )
            .select_related("role", "subject_type")
            .prefetch_related("subject")
            .order_by("subject_type_id", "subject_id")
        )

    @classmethod
    def _get_field_permission_subject_identifiers(
        cls, field: Field
    ) -> list[FieldPermissionSubjectIdentifier]:
        return [
            {
                "subject_id": assignment.subject_id,
                "subject_type": subject_type_registry.get_for_class(
                    assignment.subject_type.model_class()
                ).type,
            }
            for assignment in cls._get_field_permission_subjects(field)
        ]

    @classmethod
    def _resolve_subjects(
        cls,
        workspace,
        subject_identifiers: list[FieldPermissionSubjectIdentifier],
    ):
        identifiers_by_type = defaultdict(set)
        for identifier in subject_identifiers:
            subject_type_name = identifier["subject_type"]
            if subject_type_name not in cls.allowed_subject_types:
                raise SubjectUnsupported()
            identifiers_by_type[subject_type_name].add(identifier["subject_id"])

        subjects_by_identifier = {}
        for subject_type_name, subject_ids in identifiers_by_type.items():
            subject_type = subject_type_registry.get(subject_type_name)
            subjects = list(subject_type.model_class.objects.filter(id__in=subject_ids))
            if len(subjects) != len(subject_ids) or not all(
                subject_type.are_in_workspace(subjects, workspace)
            ):
                raise SubjectNotExist()

            for subject in subjects:
                subjects_by_identifier[(subject_type_name, subject.id)] = subject

        return [
            subjects_by_identifier[(subject_type_name, subject_id)]
            for subject_type_name, subject_id in sorted(subjects_by_identifier)
        ]

    @classmethod
    def _sync_field_permission_subjects(
        cls,
        field: Field,
        subject_identifiers: list[FieldPermissionSubjectIdentifier],
    ) -> list[RoleAssignment]:
        workspace = field.table.database.workspace
        subjects = cls._resolve_subjects(workspace, subject_identifiers)
        field_content_type = ContentType.objects.get_for_model(Field)
        content_types = ContentType.objects.get_for_models(
            *{type(subject) for subject in subjects}
        )
        desired = {
            (content_types[type(subject)].id, subject.id): subject
            for subject in subjects
        }
        existing = list(
            RoleAssignment.objects.filter(
                workspace=workspace,
                scope_id=field.id,
                scope_type=field_content_type,
                role__uid=FIELD_PERMISSION_EDITOR_ROLE_UID,
            )
        )
        existing_keys = {
            (assignment.subject_type_id, assignment.subject_id): assignment
            for assignment in existing
        }

        assignment_ids_to_delete = [
            assignment.id
            for key, assignment in existing_keys.items()
            if key not in desired
        ]
        if assignment_ids_to_delete:
            RoleAssignment.objects.filter(id__in=assignment_ids_to_delete).delete()

        assignments_to_create = [
            subject for key, subject in desired.items() if key not in existing_keys
        ]
        if assignments_to_create:
            marker_role = RoleAssignmentHandler().get_role_by_uid(
                FIELD_PERMISSION_EDITOR_ROLE_UID
            )
            RoleAssignment.objects.bulk_create(
                [
                    RoleAssignment(
                        subject_id=subject.id,
                        subject_type=content_types[type(subject)],
                        role=marker_role,
                        workspace=workspace,
                        scope_id=field.id,
                        scope_type=field_content_type,
                    )
                    for subject in assignments_to_create
                ]
            )
        return cls._get_field_permission_subjects(field)

    @classmethod
    @transaction.atomic
    def update_field_permissions(
        cls,
        user: AbstractUser,
        field: Field,
        role: FieldPermissionsRoleEnum | str,
        allow_in_forms: bool = False,
        subjects: list[FieldPermissionSubjectIdentifier] | None = None,
    ) -> FieldPermissionUpdated:
        """
        Updates the field permissions for a given field, setting the role and whether
        the field can be updated in forms.

        :param user: The user who is updating the field permissions.
        :param field: The field for which the permissions are being updated.
        :param role: The role to set for the field permissions.
        :param allow_in_forms: Whether the field can be updated in forms.
        :param subjects: The users and teams allowed to edit when the role is CUSTOM.
            If omitted while updating an existing CUSTOM permission, the current list
            is preserved.
        :return: A FieldPermissionUpdated object containing the updated permissions and
            wether the user can write values to the field, which requires computing the
            roles on the field.
        :raises: ValueError if the role provided as string is not a valid
            FieldPermissionsRoleEnum.
        """

        if isinstance(role, FieldPermissionsRoleEnum):
            role = role.value
        else:
            cls._check_valid_role_value_or_raise(role)

        CoreHandler().check_permissions(
            user,
            UpdateFieldPermissionsOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        if role == FieldPermissionsRoleEnum.CUSTOM.value:
            if subjects is None:
                subjects = cls._get_field_permission_subject_identifiers(field)
            subject_assignments = cls._sync_field_permission_subjects(field, subjects)
        else:
            cls._sync_field_permission_subjects(field, [])
            subject_assignments = []

        if role == FieldPermissionsRoleEnum.EDITOR.value:
            # The default, meaning we can remove any existing permission for this field.
            FieldPermissions.objects.filter(field=field).delete()
            allow_in_forms = True
        else:
            defaults = {"role": role, "allow_in_forms": allow_in_forms}
            FieldPermissions.objects.update_or_create(field=field, defaults=defaults)

        manager = permission_manager_type_registry.get(FieldPermissionManagerType.type)
        local_cache.clear()
        perm_object = manager.get_permissions_object(
            user, field.table.database.workspace
        )
        can_write_values_policy = perm_object[WriteFieldValuesOperationType.type]
        user_can_write_values = field.id not in can_write_values_policy["exceptions"]

        field_permissions_updated.send(
            cls,
            user=user,
            workspace=field.table.database.workspace,
            field=field,
            role=role,
            allow_in_forms=allow_in_forms,
        )

        return FieldPermissionUpdated(
            user=user,
            field=field,
            role=role,
            allow_in_forms=allow_in_forms,
            can_write_values=user_can_write_values,
            subjects=subject_assignments,
        )

    @classmethod
    def _get_field_permissions(cls, field: Field) -> FieldPermissions:
        """
        Retrieves the permissions for a given field. If none exist, default
        permissions are returned, allowing EDITOR role and enabling the field
        in forms.

        The role defines the minimum required role to update the field's data:
        - "CUSTOM": Allows actor-specific permissions via RoleAssignments.
        - "NOBODY": Blocks all updates.
        - Other roles: Allow updates for users with that role or higher.

        The allow_in_forms flag determines if the field can be updated in forms,
        regardless of other permissions. Useful for fields editable in forms
        but not in table views.

        :param field: The field for which permissions are retrieved.
        :return: The field's permissions.
        """

        try:
            field_permissions = FieldPermissions.objects.get(field=field)
        except FieldPermissions.DoesNotExist:
            # Default permissions if none exist
            field_permissions = FieldPermissions(
                field=field,
                role=FieldPermissionsRoleEnum.EDITOR.value,
                allow_in_forms=True,
            )

        return field_permissions

    @classmethod
    def get_field_permissions(cls, user, field: Field) -> FieldPermissions:
        """
        Check permissions for the user and retrieves the field permissions.
        See _get_field_permissions for more details.

        :param user: The user requesting the field permissions.
        :param field: The field for which permissions are retrieved.
        :return: The field's permissions.
        """

        CoreHandler().check_permissions(
            user,
            ReadFieldPermissionsOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        field_permissions = cls._get_field_permissions(field)
        field_permissions.subjects = (
            cls._get_field_permission_subjects(field)
            if field_permissions.role == FieldPermissionsRoleEnum.CUSTOM.value
            else []
        )
        return field_permissions

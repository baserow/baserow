from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import WriteFieldValuesOperationType
from baserow.core.cache import local_cache
from baserow.core.handler import CoreHandler
from baserow.core.registries import permission_manager_type_registry
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
from baserow_enterprise.signals import field_permissions_updated


@dataclass
class FieldPermissionUpdated:
    user: AbstractUser
    field: Field
    role: str
    allow_in_forms: bool
    can_write_values: bool


class FieldPermissionsHandler:
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
    def update_field_permissions(
        cls,
        user: AbstractUser,
        field: Field,
        role: FieldPermissionsRoleEnum | str,
        allow_in_forms: bool = False,
    ) -> FieldPermissionUpdated:
        """
        Updates the field permissions for a given field, setting the role and whether
        the field can be updated in forms.

        :param user: The user who is updating the field permissions.
        :param field: The field for which the permissions are being updated.
        :param role: The role to set for the field permissions.
        :param allow_in_forms: Whether the field can be updated in forms.
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

        return cls._get_field_permissions(field)
